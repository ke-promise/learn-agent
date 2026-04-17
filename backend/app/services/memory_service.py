from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.models.schemas import MemoryCreateRequest, MemoryHit, MemoryListResponse, MemoryRecord
from app.services.embedding_service import EmbeddingService


class MemoryService:
    """统一管理长期记忆和短期会话记录。"""

    def __init__(self, store: Any, embedding_service: EmbeddingService, conversation_store: Any | None = None) -> None:
        self.store = store
        self.embedding_service = embedding_service
        self.conversation_store = conversation_store or store

    def list_memories(self, user_id: str) -> MemoryListResponse:
        """按用户查看长期记忆。"""
        items = [
            MemoryRecord.model_validate(row)
            for row in self.store.list_memories()
            if row.get('user_id') == user_id
        ]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return MemoryListResponse(items=items)

    def create_memory(self, request: MemoryCreateRequest) -> MemoryRecord:
        """创建一条长期记忆，并补上向量表示。"""
        embedding = self.embedding_service.embed_text(request.content)
        record = MemoryRecord(
            id=self.new_id('memory'),
            user_id=request.user_id,
            namespace=request.namespace,
            memory_type=request.memory_type,
            content=request.content,
            importance=request.importance,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        payload = record.model_dump(mode='json')
        payload['embedding'] = embedding
        self.store.add_memory(payload)
        return record

    def search_memories(self, user_id: str, query: str, limit: int = 3) -> list[MemoryHit]:
        """检索与当前问题最相关的长期记忆。"""
        query_embedding = self.embedding_service.embed_text(query)
        if hasattr(self.store, 'search_memories'):
            rows = self.store.search_memories(user_id, query_embedding, limit=limit)
        else:
            rows = self._search_local_memories(user_id, query_embedding, limit)
        return [
            MemoryHit(
                id=row['id'],
                content=row['content'],
                memory_type=row['memory_type'],
                score=float(row.get('score', 0.0)),
            )
            for row in rows
        ]

    def maybe_capture_memory(self, user_id: str, message: str) -> MemoryRecord | None:
        """根据关键词判断是否值得写入长期记忆。

        这体现了项目里的一个重要产品约束：
        不是所有对话都应该永久保存，只有“稳定、有长期价值”的信息才写入长期记忆。
        """
        normalized = message.strip()
        keywords = ['记住', '偏好', '喜欢', '负责', '以后默认', '长期']
        if not any(keyword in normalized for keyword in keywords):
            return None

        memory_type = 'profile' if any(keyword in normalized for keyword in ['喜欢', '偏好', '负责', '以后默认']) else 'semantic'
        request = MemoryCreateRequest(
            user_id=user_id,
            namespace='default',
            memory_type=memory_type,
            content=normalized,
            importance=0.8,
        )
        return self.create_memory(request)

    def record_conversation_turn(self, conversation_id: str, role: str, content: str) -> None:
        """记录一轮会话消息。"""
        payload = {
            'role': role,
            'content': content,
            'created_at': datetime.now(UTC).isoformat(),
        }
        self.conversation_store.append_message(conversation_id, payload)

    def get_recent_messages(self, conversation_id: str, limit: int = 6) -> list[dict[str, Any]]:
        return self.conversation_store.get_recent_messages(conversation_id, limit=limit)

    def record_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """记录一次任务运行结果，用于首页统计。"""
        if hasattr(self.store, 'add_run'):
            return self.store.add_run(payload)
        return payload

    def new_id(self, prefix: str) -> str:
        if hasattr(self.store, 'new_id'):
            return self.store.new_id(prefix)
        return f'{prefix}_{uuid4().hex[:10]}'

    def _search_local_memories(self, user_id: str, query_embedding: list[float], limit: int) -> list[dict[str, Any]]:
        """JSON 模式下的本地记忆检索。"""
        scored: list[dict[str, Any]] = []
        for row in self.store.list_memories():
            if row.get('user_id') != user_id:
                continue
            embedding = row.get('embedding') or self.embedding_service.embed_text(row.get('content', ''))
            similarity = self.embedding_service.similarity(query_embedding, embedding)
            score = similarity + float(row.get('importance', 0.5)) * 0.1
            scored.append({**row, 'score': score})
        scored.sort(key=lambda item: item['score'], reverse=True)
        return scored[:limit]