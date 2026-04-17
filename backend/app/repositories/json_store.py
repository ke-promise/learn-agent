from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings


class JsonStore:
    """JSON 回退存储。

    这个实现的存在非常重要：
    它让项目在没有 PostgreSQL / Redis / MinIO 的环境下也能直接跑起来，
    对学习、演示和快速验证都很友好。
    """

    def __init__(self) -> None:
        self.base_dir = settings.data_dir
        self.documents_file = self.base_dir / 'documents.json'
        self.chunks_file = self.base_dir / 'chunks.json'
        self.memories_file = self.base_dir / 'memories.json'
        self.conversations_file = self.base_dir / 'conversations.json'
        self.runs_file = self.base_dir / 'runs.json'
        self._ensure_files()

    def _ensure_files(self) -> None:
        """确保所有 JSON 文件都存在。"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for path in [self.documents_file, self.chunks_file, self.memories_file, self.conversations_file, self.runs_file]:
            if not path.exists():
                path.write_text('[]', encoding='utf-8')

    def _read_list(self, path: Path) -> list[dict[str, Any]]:
        # 用 `utf-8-sig` 兼容 BOM，避免 Windows 环境下初始化文件带 BOM 时读取失败。
        return json.loads(path.read_text(encoding='utf-8-sig'))

    def _write_list(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')

    def list_documents(self) -> list[dict[str, Any]]:
        return self._read_list(self.documents_file)

    def add_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self.list_documents()
        rows.append(payload)
        self._write_list(self.documents_file, rows)
        return payload

    def list_chunks(self) -> list[dict[str, Any]]:
        return self._read_list(self.chunks_file)

    def add_chunks(self, payloads: list[dict[str, Any]]) -> None:
        rows = self.list_chunks()
        rows.extend(payloads)
        self._write_list(self.chunks_file, rows)

    def list_memories(self) -> list[dict[str, Any]]:
        return self._read_list(self.memories_file)

    def add_memory(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self.list_memories()
        rows.append(payload)
        self._write_list(self.memories_file, rows)
        return payload

    def list_conversations(self) -> list[dict[str, Any]]:
        return self._read_list(self.conversations_file)

    def append_message(self, conversation_id: str, message: dict[str, Any]) -> None:
        """把一条消息追加进指定会话。

        JSON 模式下会把整段会话消息列表放进一个对象里。
        """
        rows = self.list_conversations()
        existing = next((row for row in rows if row['id'] == conversation_id), None)
        if existing is None:
            existing = {'id': conversation_id, 'messages': []}
            rows.append(existing)
        existing['messages'].append(message)
        self._write_list(self.conversations_file, rows)

    def get_recent_messages(self, conversation_id: str, limit: int = 6) -> list[dict[str, Any]]:
        rows = self.list_conversations()
        existing = next((row for row in rows if row['id'] == conversation_id), None)
        if existing is None:
            return []
        return existing['messages'][-limit:]

    def list_runs(self) -> list[dict[str, Any]]:
        return self._read_list(self.runs_file)

    def add_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self.list_runs()
        rows.append(payload)
        self._write_list(self.runs_file, rows)
        return payload

    @staticmethod
    def new_id(prefix: str) -> str:
        """生成轻量 ID。

        JSON 模式没有数据库自增键，所以这里统一生成业务前缀 + 随机片段。
        """
        return f'{prefix}_{uuid4().hex[:10]}'