from __future__ import annotations

from typing import Any

from app.agents.langgraph_runtime import langgraph_status
from app.core.config import settings
from app.models.schemas import DocumentRecord, MemoryRecord, OverviewCard, OverviewMetric, OverviewResponse


class DashboardService:
    """聚合首页所需的统计卡片、指标和最近数据。"""

    def __init__(self, store: Any) -> None:
        self.store = store

    def get_overview(self) -> OverviewResponse:
        """计算前端首页展示数据。"""
        documents = [DocumentRecord.model_validate(item) for item in self.store.list_documents()]
        memories = [MemoryRecord.model_validate(item) for item in self.store.list_memories()]
        runs = list(self.store.list_runs()) if hasattr(self.store, 'list_runs') else []

        documents.sort(key=lambda item: item.created_at, reverse=True)
        memories.sort(key=lambda item: item.updated_at, reverse=True)

        # 这些指标不会直接决定业务逻辑，但很适合在演示和排障时快速判断系统状态。
        rag_hit_rate = 0.0
        avg_agent_calls = 0.0
        avg_latency = 0.0
        if runs:
            rag_hit_rate = sum(1 for item in runs if item.get('rag_hit')) / len(runs)
            avg_agent_calls = sum(int(item.get('agent_call_count', 0)) for item in runs) / len(runs)
            avg_latency = sum(int(item.get('latency_ms', 0)) for item in runs) / len(runs)

        cards = [
            OverviewCard(label='主场景', value='故障复盘与汇报助手'),
            OverviewCard(label='编排引擎', value='LangGraph' if langgraph_status() else '内置编排'),
            OverviewCard(label='存储后端', value='PostgreSQL + pgvector' if settings.storage_backend == 'postgres' else 'JSON'),
            OverviewCard(label='文档数量', value=len(documents)),
            OverviewCard(label='记忆数量', value=len(memories)),
            OverviewCard(label='运行次数', value=len(runs)),
        ]
        metrics = [
            OverviewMetric(label='RAG 命中率', value=f'{rag_hit_rate * 100:.0f}%', hint='命中至少一条引用的对话占比'),
            OverviewMetric(label='平均 Agent 调用', value=f'{avg_agent_calls:.1f}', hint='一次任务平均经过的 Agent 节点数'),
            OverviewMetric(label='平均耗时', value=f'{avg_latency:.0f} ms', hint='端到端任务执行的平均延迟'),
        ]
        return OverviewResponse(
            cards=cards,
            metrics=metrics,
            latest_documents=documents[:5],
            latest_memories=memories[:5],
        )