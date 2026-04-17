from __future__ import annotations

import contextlib
import functools
import sys
from pathlib import Path

import httpx
from pydantic import BaseModel, Field
from starlette.applications import Starlette
from starlette.routing import Mount


# 让独立服务在直接运行时也能找到 backend 包。
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / 'backend'
for candidate in [ROOT_DIR, BACKEND_DIR]:
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from mcp.server.fastmcp import FastMCP

from app.core.config import settings
from app.core.container import build_container
from app.models.schemas import Citation, MemoryHit


class SearchDocsResult(BaseModel):
    """文档检索工具的结构化返回。"""

    citations: list[Citation] = Field(default_factory=list)


class SearchMemoryResult(BaseModel):
    """记忆检索工具的结构化返回。"""

    hits: list[MemoryHit] = Field(default_factory=list)


class MetricResult(BaseModel):
    """指标查询结果。"""

    metric_name: str
    value: int


class TicketResult(BaseModel):
    """工单查询结果。"""

    ticket_id: str
    status: str | None = None
    owner: str | None = None
    summary: str | None = None
    severity: str | None = None
    system_name: str | None = None


class SQLAnalysisResult(BaseModel):
    """SQL 分析结果。"""

    question: str
    sql: str
    rows: list[dict] = Field(default_factory=list)
    summary: str


@functools.lru_cache(maxsize=1)
def _services():
    """复用主后端的容器装配逻辑，避免 MCP Server 再维护一套依赖初始化。"""
    return build_container()


# `stateless_http=True` 适合当前这种请求即来即走的工具调用模式。
mcp = FastMCP('enterprise-tools', stateless_http=True, json_response=True)


@mcp.tool()
def search_docs(query: str, top_k: int = 4) -> SearchDocsResult:
    """检索企业知识文档。"""
    citations = _services().knowledge_service.search(query, top_k=top_k)
    return SearchDocsResult(citations=citations)


@mcp.tool()
def search_memory(user_id: str, query: str, limit: int = 3) -> SearchMemoryResult:
    """检索指定用户的长期记忆。"""
    hits = _services().memory_service.search_memories(user_id, query, limit=limit)
    return SearchMemoryResult(hits=hits)


@mcp.tool()
def query_metric(metric_name: str) -> MetricResult:
    """查询运营/故障指标。"""
    payload = _services().ops_service.query_metric(metric_name)
    return MetricResult(**payload)


@mcp.tool()
def get_ticket(ticket_id: str) -> TicketResult:
    """查询单个工单详情。"""
    payload = _services().ops_service.get_ticket(ticket_id) or {'ticket_id': ticket_id}
    return TicketResult(**payload)


@mcp.tool()
async def run_sql_analysis(question: str) -> SQLAnalysisResult:
    """执行 SQL 分析。

    如果配置了独立 SQL Agent，就委托给它；
    否则直接使用本地 `OpsService` 的规则分析能力。
    """
    if settings.sql_agent_url:
        endpoint = f"{settings.sql_agent_url.rstrip('/')}/analyze"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(endpoint, json={'question': question})
            response.raise_for_status()
        return SQLAnalysisResult(**response.json())
    payload = _services().ops_service.analyze_question(question)
    return SQLAnalysisResult(**payload)


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    """在服务生命周期内托管 MCP session manager。"""
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(mcp.session_manager.run())
        yield


# 通过 Starlette 包装 MCP 的 Streamable HTTP 应用。
app = Starlette(routes=[Mount('/', mcp.streamable_http_app())], lifespan=lifespan)