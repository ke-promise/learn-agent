from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# 长期记忆的三种类别：
# - profile：稳定身份与偏好
# - episodic：历史任务片段
# - semantic：抽象出来的经验或规则
MemoryType = Literal['profile', 'episodic', 'semantic']

# 当前项目对用户请求做产品化的意图分类，而不是技术导向的 `qa/sql/report` 分类。
IntentType = Literal['knowledge_query', 'status_analysis', 'report_generation', 'preference_management']


class Citation(BaseModel):
    """一次知识命中的引用信息。"""

    document_id: str
    title: str
    chunk_id: str
    snippet: str
    score: float


class TraceStep(BaseModel):
    """工作流中的单个执行节点记录。

    前端会用它展示 Agent 调用链路，所以这里保留输入、输出和耗时。
    """

    agent_name: str
    step_name: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MemoryRecord(BaseModel):
    """长期记忆的完整落库结构。"""

    id: str
    user_id: str
    namespace: str
    memory_type: MemoryType
    content: str
    importance: float = 0.5
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MemoryHit(BaseModel):
    """检索命中的记忆摘要。"""

    id: str
    content: str
    memory_type: MemoryType
    score: float


class DocumentChunk(BaseModel):
    """知识文档切块后的单条记录。"""

    id: str
    document_id: str
    chunk_index: int
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0


class DocumentRecord(BaseModel):
    """知识文档元数据。"""

    id: str
    title: str
    source: str
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentUploadResponse(BaseModel):
    """上传文档后的返回结果。"""

    document: DocumentRecord
    chunks_created: int


class DocumentListResponse(BaseModel):
    """文档列表响应。"""

    items: list[DocumentRecord]


class MemoryCreateRequest(BaseModel):
    """手动写入长期记忆的请求体。"""

    user_id: str
    namespace: str = 'default'
    memory_type: MemoryType
    content: str
    importance: float = 0.6


class MemoryListResponse(BaseModel):
    """长期记忆列表响应。"""

    items: list[MemoryRecord]


class ChatRequest(BaseModel):
    """主聊天接口请求体。"""

    user_id: str
    conversation_id: str = 'default'
    message: str


class ToolResult(BaseModel):
    """工具调用结果的统一封装。"""

    tool_name: str
    ok: bool
    result: dict[str, Any]


class RunMetrics(BaseModel):
    """一次任务执行后的关键指标。"""

    rag_hit: bool
    citation_count: int
    memory_hit_count: int
    tool_call_count: int
    agent_call_count: int
    latency_ms: int


class ChatResponse(BaseModel):
    """主聊天接口返回结构。

    这个模型本身就体现了项目的可解释性设计：
    结果不只有最终回答，还会把依据、工具结果和链路一并返回。
    """

    intent_type: IntentType
    intent_label: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    memory_hits: list[MemoryHit] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    metrics: RunMetrics


class OverviewCard(BaseModel):
    """首页卡片指标。"""

    label: str
    value: int | str


class OverviewMetric(BaseModel):
    """首页图表/概览区使用的指标项。"""

    label: str
    value: str
    hint: str


class OverviewResponse(BaseModel):
    """前端首页概览响应。"""

    cards: list[OverviewCard]
    metrics: list[OverviewMetric]
    latest_documents: list[DocumentRecord]
    latest_memories: list[MemoryRecord]