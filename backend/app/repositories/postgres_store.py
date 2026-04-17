from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类。"""


class DocumentModel(Base):
    """知识文档主表。"""

    __tablename__ = 'documents'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(120))
    path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column('metadata', JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ChunkModel(Base):
    """知识切块表。

    这里用 `pgvector` 的 `Vector` 列保存 embedding，
    这样数据库就能直接做相似度检索。
    """

    __tablename__ = 'chunks'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey('documents.id', ondelete='CASCADE'), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dimensions))
    metadata_json: Mapped[dict[str, Any]] = mapped_column('metadata', JSON, default=dict)


class MemoryModel(Base):
    """长期记忆表。"""

    __tablename__ = 'memories'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    namespace: Mapped[str] = mapped_column(String(120))
    memory_type: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dimensions))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class RunModel(Base):
    """任务运行记录表，用于做概览指标与可观测性统计。"""

    __tablename__ = 'runs'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    intent_type: Mapped[str] = mapped_column(String(64))
    intent_label: Mapped[str] = mapped_column(String(64))
    rag_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    memory_hit_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0)
    agent_call_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    orchestration_mode: Mapped[str] = mapped_column(String(32), default='builtin')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class TicketModel(Base):
    """示例工单表。"""

    __tablename__ = 'tickets'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    system_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32))
    owner: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class IncidentEventModel(Base):
    """示例故障事件表。"""

    __tablename__ = 'incident_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    system_name: Mapped[str] = mapped_column(String(120), index=True)
    severity: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    ticket_id: Mapped[str] = mapped_column(String(32), index=True)
    root_cause: Mapped[str] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PostgresStore:
    """PostgreSQL + pgvector 仓储实现。

    它和 `JsonStore` 的方法名尽量保持一致，目的是让上层服务不需要感知“当前到底用的是数据库还是 JSON 文件”。
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or settings.postgres_url
        self.engine = create_engine(self.database_url, future=True, pool_pre_ping=True)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """初始化数据库结构，并确保 pgvector 扩展可用。"""
        with self.engine.begin() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        Base.metadata.create_all(self.engine)
        self._seed_operational_data()

    def _seed_operational_data(self) -> None:
        """写入一批示例工单与故障数据。

        这样 SQL Agent、指标查询和 Demo 链路在空库里也能直接运行。
        """
        with self.session_factory() as session:
            if session.scalar(select(TicketModel.id).limit(1)):
                return
            now = datetime.now(UTC)
            session.add_all([
                TicketModel(id='INC-1024', system_name='payment', status='open', owner='platform-team', severity='high', summary='Payment callback timeout in production'),
                TicketModel(id='INC-1025', system_name='payment', status='closed', owner='payment-team', severity='medium', summary='Retry storm caused callback latency spike'),
                TicketModel(id='INC-1026', system_name='order', status='open', owner='order-team', severity='medium', summary='Order service rate-limit drift'),
                IncidentEventModel(system_name='payment', severity='high', status='mitigated', ticket_id='INC-1024', root_cause='Connection pool too small combined with retry storm', duration_minutes=47, occurred_at=now - timedelta(days=1)),
                IncidentEventModel(system_name='payment', severity='medium', status='resolved', ticket_id='INC-1025', root_cause='Callback worker saturation under peak traffic', duration_minutes=33, occurred_at=now - timedelta(days=3)),
                IncidentEventModel(system_name='order', severity='medium', status='open', ticket_id='INC-1026', root_cause='Rate-limit threshold drift', duration_minutes=18, occurred_at=now - timedelta(days=2)),
            ])
            session.commit()

    def list_documents(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            return [self._document_to_dict(item) for item in session.scalars(select(DocumentModel)).all()]

    def add_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as session:
            session.add(
                DocumentModel(
                    id=payload['id'],
                    title=payload['title'],
                    source=payload['source'],
                    path=payload.get('path'),
                    metadata_json=payload.get('metadata', {}),
                    created_at=self._coerce_datetime(payload.get('created_at')),
                )
            )
            session.commit()
        return payload

    def list_chunks(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            return [self._chunk_to_dict(item) for item in session.scalars(select(ChunkModel)).all()]

    def add_chunks(self, payloads: list[dict[str, Any]]) -> None:
        with self.session_factory() as session:
            for payload in payloads:
                metadata = dict(payload.get('metadata', {}))

                # embedding 会单独写到向量列，不继续保留在 metadata JSON 中，避免冗余。
                embedding = list(metadata.pop('embedding', []))
                session.add(
                    ChunkModel(
                        id=payload['id'],
                        document_id=payload['document_id'],
                        chunk_index=payload['chunk_index'],
                        content=payload['content'],
                        embedding=embedding,
                        metadata_json=metadata,
                    )
                )
            session.commit()

    def search_chunks(self, embedding: list[float], top_k: int = 4) -> list[dict[str, Any]]:
        """利用 pgvector 的余弦距离直接做相似度检索。"""
        with self.session_factory() as session:
            distance = ChunkModel.embedding.cosine_distance(embedding)
            rows = session.execute(select(ChunkModel, (1 - distance).label('score')).order_by(distance).limit(top_k)).all()
            return [self._chunk_to_dict(chunk, score=float(score)) for chunk, score in rows]

    def list_memories(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            return [self._memory_to_dict(item) for item in session.scalars(select(MemoryModel)).all()]

    def add_memory(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as session:
            session.add(
                MemoryModel(
                    id=payload['id'],
                    user_id=payload['user_id'],
                    namespace=payload['namespace'],
                    memory_type=payload['memory_type'],
                    content=payload['content'],
                    importance=float(payload.get('importance', 0.5)),
                    embedding=list(payload.get('embedding', [])),
                    created_at=self._coerce_datetime(payload.get('created_at')),
                    updated_at=self._coerce_datetime(payload.get('updated_at')),
                )
            )
            session.commit()
        return payload

    def search_memories(self, user_id: str, embedding: list[float], limit: int = 3) -> list[dict[str, Any]]:
        """先按用户过滤，再做向量相似度检索。

        这里会把相似度和 `importance` 做一个简单融合，让“用户明确强调过的重要记忆”更容易排到前面。
        """
        with self.session_factory() as session:
            distance = MemoryModel.embedding.cosine_distance(embedding)
            rows = session.execute(
                select(MemoryModel, (1 - distance).label('similarity'))
                .where(MemoryModel.user_id == user_id)
                .order_by(distance)
                .limit(max(limit * 4, limit))
            ).all()
            items = [{**self._memory_to_dict(mem), 'score': float(sim) + float(mem.importance or 0.0) * 0.1} for mem, sim in rows]
            items.sort(key=lambda item: item['score'], reverse=True)
            return items[:limit]

    def list_runs(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            return [self._run_to_dict(item) for item in session.scalars(select(RunModel)).all()]

    def add_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as session:
            session.add(
                RunModel(
                    id=payload['id'],
                    user_id=payload['user_id'],
                    conversation_id=payload['conversation_id'],
                    intent_type=payload['intent_type'],
                    intent_label=payload['intent_label'],
                    rag_hit=bool(payload.get('rag_hit', False)),
                    citation_count=int(payload.get('citation_count', 0)),
                    memory_hit_count=int(payload.get('memory_hit_count', 0)),
                    tool_call_count=int(payload.get('tool_call_count', 0)),
                    agent_call_count=int(payload.get('agent_call_count', 0)),
                    latency_ms=int(payload.get('latency_ms', 0)),
                    orchestration_mode=payload.get('orchestration_mode', 'builtin'),
                    created_at=self._coerce_datetime(payload.get('created_at')),
                )
            )
            session.commit()
        return payload

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(TicketModel, ticket_id)
            if row is None:
                return None
            return {
                'ticket_id': row.id,
                'system_name': row.system_name,
                'status': row.status,
                'owner': row.owner,
                'severity': row.severity,
                'summary': row.summary,
                'created_at': row.created_at.isoformat(),
            }

    def query_metric(self, metric_name: str) -> dict[str, Any]:
        """返回几个演示场景里常用的运营/故障指标。"""
        with self.session_factory() as session:
            if metric_name == 'incident_count':
                value = session.query(IncidentEventModel).count()
            elif metric_name == 'ticket_backlog':
                value = session.query(TicketModel).filter(TicketModel.status.in_(['open', 'investigating'])).count()
            elif metric_name == 'alpha_risk_score':
                value = min(
                    100,
                    session.query(TicketModel).filter(TicketModel.status.in_(['open', 'investigating'])).count() * 18
                    + session.query(IncidentEventModel).filter(IncidentEventModel.severity == 'high').count() * 22
                    + 20,
                )
            else:
                value = 0
        return {'metric_name': metric_name, 'value': int(value)}

    def execute_readonly_sql(self, sql: str) -> list[dict[str, Any]]:
        """只允许执行只读 SQL，避免演示环境被意外修改。"""
        normalized = sql.strip().lower()
        if not normalized.startswith(('select', 'with')):
            raise ValueError('SQL Agent 只允许执行只读查询。')
        with self.engine.begin() as conn:
            return [dict(row) for row in conn.execute(text(sql)).mappings().all()]

    @staticmethod
    def new_id(prefix: str) -> str:
        return f'{prefix}_{uuid4().hex[:10]}'

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return datetime.now(UTC)

    def _document_to_dict(self, row: DocumentModel) -> dict[str, Any]:
        return {
            'id': row.id,
            'title': row.title,
            'source': row.source,
            'path': row.path,
            'metadata': row.metadata_json or {},
            'created_at': row.created_at,
        }

    def _chunk_to_dict(self, row: ChunkModel, score: float = 0.0) -> dict[str, Any]:
        # 为了和 JSON 模式保持字段结构一致，这里会把向量重新放回 metadata 里返回给上层。
        metadata = dict(row.metadata_json or {})
        metadata['embedding'] = list(row.embedding or [])
        return {
            'id': row.id,
            'document_id': row.document_id,
            'chunk_index': row.chunk_index,
            'content': row.content,
            'metadata': metadata,
            'score': score,
        }

    def _memory_to_dict(self, row: MemoryModel) -> dict[str, Any]:
        return {
            'id': row.id,
            'user_id': row.user_id,
            'namespace': row.namespace,
            'memory_type': row.memory_type,
            'content': row.content,
            'importance': row.importance,
            'embedding': list(row.embedding or []),
            'created_at': row.created_at,
            'updated_at': row.updated_at,
        }

    def _run_to_dict(self, row: RunModel) -> dict[str, Any]:
        return {
            'id': row.id,
            'user_id': row.user_id,
            'conversation_id': row.conversation_id,
            'intent_type': row.intent_type,
            'intent_label': row.intent_label,
            'rag_hit': row.rag_hit,
            'citation_count': row.citation_count,
            'memory_hit_count': row.memory_hit_count,
            'tool_call_count': row.tool_call_count,
            'agent_call_count': row.agent_call_count,
            'latency_ms': row.latency_ms,
            'orchestration_mode': row.orchestration_mode,
            'created_at': row.created_at.isoformat(),
        }