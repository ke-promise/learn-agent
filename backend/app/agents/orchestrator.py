from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from app.agents.langgraph_runtime import OrchestrationState, build_langgraph_runner
from app.agents.memory_agent import MemoryAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.report_agent import ReportAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.router_agent import RouterAgent
from app.agents.tool_agent import ToolAgent
from app.models.schemas import ChatRequest, ChatResponse, RunMetrics, ToolResult, TraceStep
from app.services.knowledge_service import KnowledgeService
from app.services.memory_service import MemoryService


class Orchestrator:
    """多 Agent 主编排器。

    它是整个后端最核心的文件：
    - 负责决定一条请求要走哪些节点
    - 负责把各节点结果汇总成统一响应
    - 负责记录运行指标与 trace
    """

    def __init__(
        self,
        knowledge_service: KnowledgeService,
        memory_service: MemoryService,
        tool_agent: ToolAgent,
        report_agent: ReportAgent,
    ) -> None:
        self.knowledge_service = knowledge_service
        self.memory_service = memory_service
        self.router = RouterAgent()
        self.planner = PlannerAgent()
        self.retrieval = RetrievalAgent(knowledge_service)
        self.memory = MemoryAgent(memory_service)
        self.tool = tool_agent
        self.report = report_agent

        # 如果环境里安装了 LangGraph，就自动切换到图编排；
        # 否则继续使用内置顺序编排。这样高级能力和可运行性可以兼得。
        self.graph_app = build_langgraph_runner(
            {
                'route': self._route_node,
                'plan': self._plan_node,
                'memory': self._memory_node,
                'retrieval': self._retrieval_node,
                'tool': self._tool_node,
                'compose': self._compose_node,
                'report': self._report_node,
            }
        )

    async def run_chat(self, payload: ChatRequest) -> ChatResponse:
        """执行一轮完整的聊天任务。"""
        start = perf_counter()

        # 先记录用户输入，保证后续无论成功失败，至少会话轨迹是完整的。
        self.memory_service.record_conversation_turn(payload.conversation_id, 'user', payload.message)

        state: OrchestrationState = {
            'user_id': payload.user_id,
            'message': payload.message,
            'intent_type': 'knowledge_query',
            'intent_label': '知识查询',
            'plan': [],
            'memory_hits': [],
            'citations': [],
            'tool_results': [],
            'trace': [],
            'answer': '',
        }

        if self.graph_app is not None:
            final_state = await self.graph_app.ainvoke(state)
            orchestration_mode = 'langgraph'
        else:
            final_state = await self._run_builtin(state)
            orchestration_mode = 'builtin'

        # 任务结束后尝试捕获用户表达过的长期信息，例如“我负责支付系统”。
        self.memory_service.maybe_capture_memory(payload.user_id, payload.message)

        # 最终回答也会记入会话短期记忆。
        self.memory_service.record_conversation_turn(payload.conversation_id, 'assistant', final_state.get('answer', ''))

        metrics = RunMetrics(
            rag_hit=bool(final_state.get('citations')),
            citation_count=len(final_state.get('citations', [])),
            memory_hit_count=len(final_state.get('memory_hits', [])),
            tool_call_count=len(final_state.get('tool_results', [])),
            agent_call_count=len(final_state.get('trace', [])),
            latency_ms=int((perf_counter() - start) * 1000),
        )

        run_payload = {
            'id': self.memory_service.new_id('run'),
            'user_id': payload.user_id,
            'conversation_id': payload.conversation_id,
            'intent_type': final_state.get('intent_type', 'knowledge_query'),
            'intent_label': final_state.get('intent_label', '知识查询'),
            'rag_hit': metrics.rag_hit,
            'citation_count': metrics.citation_count,
            'memory_hit_count': metrics.memory_hit_count,
            'tool_call_count': metrics.tool_call_count,
            'agent_call_count': metrics.agent_call_count,
            'latency_ms': metrics.latency_ms,
            'orchestration_mode': orchestration_mode,
            'created_at': datetime.now(UTC).isoformat(),
        }
        self.memory_service.record_run(run_payload)

        return ChatResponse(
            intent_type=final_state.get('intent_type', 'knowledge_query'),
            intent_label=final_state.get('intent_label', '知识查询'),
            answer=final_state.get('answer', ''),
            citations=final_state.get('citations', []),
            memory_hits=final_state.get('memory_hits', []),
            tool_results=[ToolResult.model_validate(item) for item in final_state.get('tool_results', [])],
            trace=[TraceStep.model_validate(item) for item in final_state.get('trace', [])],
            metrics=metrics,
        )

    async def _run_builtin(self, state: OrchestrationState) -> OrchestrationState:
        """没有 LangGraph 时，按固定顺序顺序执行节点。"""
        current = dict(state)
        for step in [self._route_node, self._plan_node, self._memory_node, self._retrieval_node, self._tool_node, self._compose_node, self._report_node]:
            update = await step(current)
            current.update(update)
        return current

    async def _route_node(self, state: OrchestrationState) -> dict[str, Any]:
        result = self.router.route(state['message'])
        return self._merge_trace(state, result.data, result.trace)

    async def _plan_node(self, state: OrchestrationState) -> dict[str, Any]:
        result = self.planner.plan(state['intent_type'])
        return self._merge_trace(state, result.data, result.trace)

    async def _memory_node(self, state: OrchestrationState) -> dict[str, Any]:
        if 'memory' not in state.get('plan', []):
            return self._skip_trace(state, 'memory', 'memory_skipped')
        result = self.memory.run(state['user_id'], state['message'])
        return self._merge_trace(state, result.data, result.trace)

    async def _retrieval_node(self, state: OrchestrationState) -> dict[str, Any]:
        if 'retrieval' not in state.get('plan', []):
            return self._skip_trace(state, 'retrieval', 'retrieval_skipped')
        result = self.retrieval.run(state['message'])
        return self._merge_trace(state, result.data, result.trace)

    async def _tool_node(self, state: OrchestrationState) -> dict[str, Any]:
        if 'tool' not in state.get('plan', []):
            return self._skip_trace(state, 'tool', 'tool_skipped')
        result = await self.tool.run(state['user_id'], state['message'])
        return self._merge_trace(state, result.data, result.trace)

    async def _compose_node(self, state: OrchestrationState) -> dict[str, Any]:
        """把检索、记忆和工具结果整理成一份标准 Markdown。"""
        answer = self._compose_answer(
            intent_label=state.get('intent_label', '知识查询'),
            message=state['message'],
            citations=state.get('citations', []),
            memory_hits=state.get('memory_hits', []),
            tool_results=state.get('tool_results', []),
        )
        return {'answer': answer, 'trace': state.get('trace', [])}

    async def _report_node(self, state: OrchestrationState) -> dict[str, Any]:
        if 'report' not in state.get('plan', []):
            return self._skip_trace(state, 'report', 'report_skipped')
        facts = {
            'summary': state.get('answer', ''),
            'citations': state.get('citations', []),
            'memory_hits': state.get('memory_hits', []),
            'tool_results': state.get('tool_results', []),
        }
        result = await self.report.run(state['message'], facts)
        return self._merge_trace(state, result.data, result.trace)

    def _compose_answer(
        self,
        intent_label: str,
        message: str,
        citations: list[dict[str, Any]],
        memory_hits: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
    ) -> str:
        """生成前端直接渲染的 Markdown 内容。"""
        lines = [f'# {intent_label}结果', '', '## 用户请求', message, '', '## 结论']
        if citations:
            lines.append('结合知识库命中的文档内容，可以先给出结论，再展开依据和建议动作。')
        elif memory_hits:
            lines.append('当前主要依据用户长期记忆与历史偏好生成回答，建议补充更多知识文档以提升可信度。')
        else:
            lines.append('当前没有命中足够的外部知识或历史记忆，结论更适合作为初步分析。')

        lines.extend(['', '## 知识引用'])
        if citations:
            for item in citations[:4]:
                lines.append(f"- 《{item.get('title', '未命名文档')}》：{item.get('snippet', '')}")
        else:
            lines.append('- 没有检索到直接可引用的知识片段。')

        lines.extend(['', '## Memory 命中'])
        if memory_hits:
            for item in memory_hits[:3]:
                lines.append(f"- {item.get('content', '')}（相关度 {float(item.get('score', 0.0)):.2f}）")
        else:
            lines.append('- 当前没有命中长期记忆。')

        lines.extend(['', '## 工具结果'])
        if tool_results:
            for item in tool_results:
                lines.append(f"- `{item.get('tool_name', 'tool')}`：{self._compact(item.get('result', {}))}")
        else:
            lines.append('- 当前任务未触发额外工具调用。')

        lines.extend([
            '',
            '## 建议动作',
            '- 若这是线上故障，请先确认高等级未关闭工单及相关指标波动。',
            '- 将本次分析沉淀为结构化文档，方便下次复盘直接引用。',
        ])
        return '\n'.join(lines)

    @staticmethod
    def _merge_trace(state: OrchestrationState, data: dict[str, Any], trace_items: list[TraceStep]) -> dict[str, Any]:
        """把新节点 trace 追加进现有状态。"""
        merged_trace = state.get('trace', []) + [item.model_dump(mode='json') for item in trace_items]
        return {**data, 'trace': merged_trace}

    @staticmethod
    def _skip_trace(state: OrchestrationState, agent_name: str, step_name: str) -> dict[str, Any]:
        """给被跳过的节点也留下一条 trace，方便前端说明“为什么没执行”。"""
        trace = state.get('trace', []) + [
            {
                'agent_name': agent_name,
                'step_name': step_name,
                'input_data': {},
                'output_data': {'skipped': True},
                'duration_ms': 0,
                'created_at': datetime.utcnow().isoformat(),
            }
        ]
        return {'trace': trace}

    @staticmethod
    def _compact(payload: Any) -> str:
        text = str(payload)
        return text if len(text) <= 220 else f'{text[:220]}...'