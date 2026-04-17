from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.services.a2a_client import A2AClient


class ReportAgent(BaseAgent):
    """报告生成节点。"""

    name = 'report'

    def __init__(self, a2a_client: A2AClient) -> None:
        self.a2a_client = a2a_client

    async def run(self, topic: str, facts: dict[str, Any]) -> AgentResult:
        start = perf_counter()
        content = await self.a2a_client.generate_report(topic, facts)
        payload = {'answer': content}
        trace = self.trace('report_generation', start, {'topic': topic}, {'answer_preview': content[:120]})
        return AgentResult(data=payload, trace=[trace])