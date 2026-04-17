from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class A2AClient:
    """A2A 风格报告协作客户端。

    当前项目里它承担“主后端调用独立报告服务”的职责，
    体现跨服务部署和专长 Agent 解耦的设计思路。
    """

    def __init__(self) -> None:
        self.remote_url = settings.remote_report_agent_url.strip()

    async def generate_report(self, topic: str, facts: dict[str, Any]) -> str:
        """优先调远程报告服务，失败时回退本地模板。"""
        if self.remote_url:
            endpoint = self.remote_url if self.remote_url.endswith('/report') else f"{self.remote_url.rstrip('/')}/report"
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(endpoint, json={'topic': topic, 'facts': facts})
                    response.raise_for_status()
                payload = response.json()
                content = payload.get('content')
                if content:
                    return str(content)
            except Exception:
                pass
        return self._render_local_report(topic, facts)

    @staticmethod
    def _render_local_report(topic: str, facts: dict[str, Any]) -> str:
        """本地兜底报告模板。

        它把知识引用、Memory 命中和工具结果拼成一份结构化 Markdown，
        这样即使没有远程服务，前端仍能看到完整汇报效果。
        """
        citations = facts.get('citations', [])
        memory_hits = facts.get('memory_hits', [])
        tool_results = facts.get('tool_results', [])
        summary = facts.get('summary', '')

        lines = [
            f'# 故障复盘汇报：{topic}',
            '',
            '## 一、结论',
            '当前信息显示支付与订单链路近期存在典型的容量与重试放大风险，建议优先处理高等级未关闭工单，并对回调链路进行容量校准。',
            '',
            '## 二、事实依据',
        ]
        if citations:
            for item in citations[:4]:
                lines.append(f"- 文档《{item.get('title', '未命名文档')}》：{item.get('snippet', '')}")
        else:
            lines.append('- 当前没有命中知识文档引用。')

        lines.extend(['', '## 三、用户上下文'])
        if memory_hits:
            for item in memory_hits[:3]:
                lines.append(f"- 命中长期记忆：{item.get('content', '')}")
        else:
            lines.append('- 当前没有命中稳定的用户长期记忆。')

        lines.extend(['', '## 四、工具与数据侧信息'])
        if tool_results:
            for item in tool_results:
                lines.append(f"- `{item.get('tool_name', 'tool')}`：{A2AClient._compact(item.get('result', {}))}")
        else:
            lines.append('- 当前没有额外工具结果。')

        lines.extend([
            '',
            '## 五、建议动作',
            '- 先处理高优先级未关闭工单，确认回调链路、连接池与重试参数是否匹配当前流量峰值。',
            '- 将相似故障的根因与处置动作沉淀进知识库，作为后续复盘的标准引用。',
            '- 对老板汇报建议采用“先结论、后依据、再动作”的结构，便于快速同步风险状态。',
        ])
        if summary:
            lines.extend(['', '## 六、补充摘要', summary])
        return '\n'.join(lines)

    @staticmethod
    def _compact(payload: Any) -> str:
        text = str(payload)
        return text if len(text) <= 220 else f'{text[:220]}...'