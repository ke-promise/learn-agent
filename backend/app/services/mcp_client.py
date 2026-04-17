from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.models.schemas import ToolResult
from app.services.knowledge_service import KnowledgeService
from app.services.memory_service import MemoryService
from app.services.ops_service import OpsService


class MCPClient:
    """MCP 工具调用客户端。

    设计原则是“远程优先，本地兜底”：
    - 如果配置了真实 MCP Server，就走标准协议调用
    - 如果没有配置，或远程失败，就回退到本地服务实现
    """

    def __init__(self, knowledge_service: KnowledgeService, memory_service: MemoryService, ops_service: OpsService) -> None:
        self.knowledge_service = knowledge_service
        self.memory_service = memory_service
        self.ops_service = ops_service
        self.server_url = settings.mcp_server_url.strip()

    async def search_docs(self, query: str, top_k: int = 4) -> ToolResult:
        remote = await self._call_remote_tool('search_docs', {'query': query, 'top_k': top_k})
        if remote is not None:
            return ToolResult(tool_name='search_docs', ok=True, result=remote)
        citations = [item.model_dump(mode='json') for item in self.knowledge_service.search(query, top_k=top_k)]
        return ToolResult(tool_name='search_docs', ok=True, result={'citations': citations})

    async def search_memory(self, user_id: str, query: str, limit: int = 3) -> ToolResult:
        remote = await self._call_remote_tool('search_memory', {'user_id': user_id, 'query': query, 'limit': limit})
        if remote is not None:
            return ToolResult(tool_name='search_memory', ok=True, result=remote)
        hits = [item.model_dump(mode='json') for item in self.memory_service.search_memories(user_id, query, limit=limit)]
        return ToolResult(tool_name='search_memory', ok=True, result={'hits': hits})

    async def query_metric(self, metric_name: str) -> ToolResult:
        remote = await self._call_remote_tool('query_metric', {'metric_name': metric_name})
        if remote is not None:
            return ToolResult(tool_name=f'metric:{metric_name}', ok=True, result=remote)
        return ToolResult(tool_name=f'metric:{metric_name}', ok=True, result=self.ops_service.query_metric(metric_name))

    async def get_ticket(self, ticket_id: str) -> ToolResult:
        remote = await self._call_remote_tool('get_ticket', {'ticket_id': ticket_id})
        if remote is not None:
            return ToolResult(tool_name='get_ticket', ok=True, result=remote)
        ticket = self.ops_service.get_ticket(ticket_id)
        return ToolResult(tool_name='get_ticket', ok=ticket is not None, result=ticket or {'ticket_id': ticket_id, 'message': '未找到工单'})

    async def run_sql_analysis(self, question: str) -> ToolResult:
        remote = await self._call_remote_tool('run_sql_analysis', {'question': question})
        if remote is not None:
            return ToolResult(tool_name='run_sql_analysis', ok=True, result=remote)
        return ToolResult(tool_name='run_sql_analysis', ok=True, result=self.ops_service.analyze_question(question))

    async def _call_remote_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        """通过 MCP 标准协议调用远程工具。"""
        if not self.server_url:
            return None
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError:
            return None
        try:
            async with streamable_http_client(self.server_url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
        except Exception:
            return None

        # 优先拿结构化内容；拿不到时再从文本内容里尝试反序列化 JSON。
        structured = getattr(result, 'structuredContent', None)
        if structured is not None:
            return structured
        content = getattr(result, 'content', None) or []
        for item in content:
            text = getattr(item, 'text', None)
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {'text': text}
        return None