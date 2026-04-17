from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.orchestrator import Orchestrator
from app.agents.report_agent import ReportAgent
from app.agents.tool_agent import ToolAgent
from app.core.config import settings
from app.repositories.json_store import JsonStore
from app.repositories.postgres_store import PostgresStore
from app.repositories.redis_store import RedisConversationStore
from app.services.a2a_client import A2AClient
from app.services.dashboard_service import DashboardService
from app.services.document_parser import DocumentParser
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_service import KnowledgeService
from app.services.mcp_client import MCPClient
from app.services.memory_service import MemoryService
from app.services.object_storage import LocalObjectStorage, MinioObjectStorage, ObjectStorage
from app.services.ops_service import OpsService


@dataclass
class AppContainer:
    """应用级依赖容器。

    它的作用不是增加抽象层数，而是把“这次启动用到的全部共享依赖”集中管理。
    这样路由只要拿到一个容器对象，就能访问整条业务链上的服务。
    """

    store: Any
    conversation_store: Any
    object_storage: ObjectStorage | None
    embedding_service: EmbeddingService
    parser: DocumentParser
    knowledge_service: KnowledgeService
    memory_service: MemoryService
    ops_service: OpsService
    mcp_client: MCPClient
    a2a_client: A2AClient
    dashboard_service: DashboardService
    orchestrator: Orchestrator


def build_container() -> AppContainer:
    """按照配置装配一套完整运行时依赖。

    装配顺序是有意设计的：
    先决定底层存储，再逐层向上构建服务，最后再构建编排器。
    """
    store = _build_store()
    conversation_store = _build_conversation_store(store)
    object_storage = _build_object_storage()

    # 这些是多个业务能力共享的基础组件。
    embedding_service = EmbeddingService(settings.embedding_dimensions)
    parser = DocumentParser()

    # 服务层封装领域能力。
    knowledge_service = KnowledgeService(store, embedding_service, parser, object_storage)
    memory_service = MemoryService(store, embedding_service, conversation_store)
    ops_service = OpsService(store)
    mcp_client = MCPClient(knowledge_service, memory_service, ops_service)
    a2a_client = A2AClient()
    dashboard_service = DashboardService(store)

    # Agent 层基于服务层进行组合。
    tool_agent = ToolAgent(mcp_client)
    report_agent = ReportAgent(a2a_client)
    orchestrator = Orchestrator(knowledge_service, memory_service, tool_agent, report_agent)

    return AppContainer(
        store=store,
        conversation_store=conversation_store,
        object_storage=object_storage,
        embedding_service=embedding_service,
        parser=parser,
        knowledge_service=knowledge_service,
        memory_service=memory_service,
        ops_service=ops_service,
        mcp_client=mcp_client,
        a2a_client=a2a_client,
        dashboard_service=dashboard_service,
        orchestrator=orchestrator,
    )


def _build_store() -> Any:
    """构建主存储后端。

    若用户配置了 PostgreSQL，则优先尝试真实数据库；
    失败时自动回退到 JSON，保证本地学习和演示不被基础设施阻塞。
    """
    if settings.storage_backend == 'postgres':
        try:
            return PostgresStore(settings.postgres_url)
        except Exception:
            return JsonStore()
    return JsonStore()


def _build_conversation_store(store: Any) -> Any:
    """构建短期会话存储。

    会话消息天然适合 Redis 这类可过期的键值存储；
    但如果 Redis 不可用，也允许直接回退到主存储。
    """
    if settings.conversation_backend == 'redis':
        try:
            return RedisConversationStore(settings.redis_url, settings.redis_conversation_ttl_seconds)
        except Exception:
            return store
    return store


def _build_object_storage() -> ObjectStorage | None:
    """构建对象存储实现。

    原始文件和向量块是两类数据：
    - 向量块适合数据库
    - 原始文件更适合对象存储
    """
    if settings.object_storage_backend == 'minio':
        try:
            return MinioObjectStorage()
        except Exception:
            return LocalObjectStorage()
    return LocalObjectStorage()