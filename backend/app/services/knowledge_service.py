from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.models.schemas import Citation, DocumentListResponse, DocumentRecord, DocumentUploadResponse
from app.services.document_parser import DocumentParser
from app.services.embedding_service import EmbeddingService
from app.services.object_storage import ObjectStorage


class KnowledgeService:
    """企业知识服务。

    它负责两件核心事情：
    - 把原始文档摄取成可检索的数据
    - 按查询返回带引用的知识片段
    """

    def __init__(
        self,
        store: Any,
        embedding_service: EmbeddingService,
        parser: DocumentParser,
        object_storage: ObjectStorage | None = None,
    ) -> None:
        self.store = store
        self.embedding_service = embedding_service
        self.parser = parser
        self.object_storage = object_storage

    async def ingest_document(
        self,
        title: str,
        source: str,
        content: str = '',
        file: UploadFile | None = None,
    ) -> DocumentUploadResponse:
        """摄取一份知识文档，并建立可检索索引。"""
        parsed_text, filename, raw = await self.parser.parse(file, content)
        cleaned_text = parsed_text.strip()
        if not cleaned_text:
            raise ValueError('上传内容为空，无法建立知识索引。')

        document_id = self._new_id('doc')
        path: str | None = None

        # 原始文件和切块内容分开存：
        # 原始文件进对象存储，切块文本进知识存储。
        if raw and filename and self.object_storage is not None:
            storage_name = f'{document_id}_{Path(filename).name}'
            path = self.object_storage.save_bytes(storage_name, raw)

        document = DocumentRecord(
            id=document_id,
            title=title,
            source=source,
            path=path,
            metadata={
                'filename': filename,
                'char_count': len(cleaned_text),
            },
            created_at=datetime.now(UTC),
        )
        self.store.add_document(document.model_dump(mode='json'))

        chunk_payloads: list[dict[str, Any]] = []
        for index, chunk in enumerate(self._chunk_text(cleaned_text)):
            chunk_payloads.append(
                {
                    'id': self._new_id('chunk'),
                    'document_id': document_id,
                    'chunk_index': index,
                    'content': chunk,
                    'metadata': {
                        'source': source,
                        'title': title,
                        'embedding': self.embedding_service.embed_text(chunk),
                    },
                }
            )
        self.store.add_chunks(chunk_payloads)
        return DocumentUploadResponse(document=document, chunks_created=len(chunk_payloads))

    def list_documents(self) -> DocumentListResponse:
        """列出最近导入的文档。"""
        rows = [DocumentRecord.model_validate(item) for item in self.store.list_documents()]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return DocumentListResponse(items=rows)

    def search(self, query: str, top_k: int = 4) -> list[Citation]:
        """检索知识库，并返回可直接展示给前端的引用结构。"""
        query_embedding = self.embedding_service.embed_text(query)
        documents = {row['id']: row for row in self.store.list_documents()}

        # 有数据库向量检索能力时优先用数据库；否则退回本地遍历计算。
        if hasattr(self.store, 'search_chunks'):
            chunk_rows = self.store.search_chunks(query_embedding, top_k=top_k)
        else:
            chunk_rows = self._search_local_chunks(query_embedding, top_k)

        citations: list[Citation] = []
        for row in chunk_rows:
            document = documents.get(row['document_id'], {})
            citations.append(
                Citation(
                    document_id=row['document_id'],
                    title=document.get('title', '未命名文档'),
                    chunk_id=row['id'],
                    snippet=self._snippet(row['content']),
                    score=float(row.get('score', 0.0)),
                )
            )
        return citations

    def _search_local_chunks(self, query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        """JSON 模式下的本地相似度检索。"""
        scored: list[dict[str, Any]] = []
        for row in self.store.list_chunks():
            embedding = row.get('metadata', {}).get('embedding') or self.embedding_service.embed_text(row.get('content', ''))
            score = self.embedding_service.similarity(query_embedding, embedding)
            scored.append({**row, 'score': score})
        scored.sort(key=lambda item: item['score'], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 380, overlap: int = 60) -> list[str]:
        """对长文本进行轻量切块。

        这里采用字符级切块而不是复杂分句，是为了保证项目在最小依赖下也能稳定运行。
        """
        cleaned = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
        if len(cleaned) <= chunk_size:
            return [cleaned]
        chunks: list[str] = []
        start = 0
        while start < len(cleaned):
            end = min(start + chunk_size, len(cleaned))
            chunks.append(cleaned[start:end].strip())
            if end >= len(cleaned):
                break
            start = max(0, end - overlap)
        return [chunk for chunk in chunks if chunk]

    @staticmethod
    def _snippet(text: str, length: int = 180) -> str:
        """把切块内容压缩成适合前端卡片展示的摘要。"""
        compact = ' '.join(text.split())
        return compact if len(compact) <= length else f'{compact[:length]}...'

    def _new_id(self, prefix: str) -> str:
        if hasattr(self.store, 'new_id'):
            return self.store.new_id(prefix)
        return f'{prefix}_{int(datetime.now(UTC).timestamp())}'