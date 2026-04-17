from __future__ import annotations

import asyncio
from time import perf_counter

from app.agents.base import AgentResult, BaseAgent
from app.services.mcp_client import MCPClient


class ToolAgent(BaseAgent):
    """工具调用节点。"""

    name = 'tool'

    def __init__(self, mcp_client: MCPClient) -> None:
        self.mcp_client = mcp_client

    async def run(self, user_id: str, message: str) -> AgentResult:
        """并发调用一组预定义工具。

        之所以放在一个节点里统一调度，是为了让 Planner 只关心“要不要查工具”，
        而不用关心内部到底要查多少个工具。
        """
        start = perf_counter()
        tool_results = await asyncio.gather(
            self.mcp_client.search_docs(message),
            self.mcp_client.search_memory(user_id, message),
            self.mcp_client.query_metric('incident_count'),
            self.mcp_client.query_metric('alpha_risk_score'),
            self.mcp_client.get_ticket('INC-1024'),
            self.mcp_client.run_sql_analysis(message),
        )
        payload = {'tool_results': [item.model_dump(mode='json') for item in tool_results]}
        trace = self.trace('tool_orchestration', start, {'user_id': user_id, 'message': message}, {'tool_call_count': len(tool_results)})
        return AgentResult(data=payload, trace=[trace])