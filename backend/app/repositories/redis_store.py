from __future__ import annotations

import json
from typing import Any

from redis import Redis

from app.core.config import settings


class RedisConversationStore:
    """Redis 会话存储。

    它只负责“短期、可过期、按时间追加”的消息数据，不承载长期知识和长期记忆。
    """

    def __init__(self, redis_url: str | None = None, ttl_seconds: int | None = None) -> None:
        self.client = Redis.from_url(redis_url or settings.redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds or settings.redis_conversation_ttl_seconds

    def append_message(self, conversation_id: str, message: dict[str, Any]) -> None:
        key = self._key(conversation_id)
        self.client.rpush(key, json.dumps(message, ensure_ascii=False))

        # 每次写入都刷新过期时间，让活跃会话自然保留，不活跃会话自动过期。
        self.client.expire(key, self.ttl_seconds)

    def get_recent_messages(self, conversation_id: str, limit: int = 6) -> list[dict[str, Any]]:
        key = self._key(conversation_id)
        return [json.loads(item) for item in self.client.lrange(key, -limit, -1)]

    @staticmethod
    def _key(conversation_id: str) -> str:
        return f'conversation:{conversation_id}'