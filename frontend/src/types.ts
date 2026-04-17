// 这一组类型基本与后端响应模型保持对齐，目的是让前端在开发阶段就能获得字段提示和约束。

export interface Citation {
  document_id: string
  title: string
  chunk_id: string
  snippet: string
  score: number
}

export interface MemoryHit {
  id: string
  content: string
  memory_type: 'profile' | 'episodic' | 'semantic'
  score: number
}

export interface ToolResult {
  tool_name: string
  ok: boolean
  result: Record<string, unknown>
}

export interface TraceStep {
  agent_name: string
  step_name: string
  input_data: Record<string, unknown>
  output_data: Record<string, unknown>
  duration_ms: number
  created_at: string
}

export interface RunMetrics {
  rag_hit: boolean
  citation_count: number
  memory_hit_count: number
  tool_call_count: number
  agent_call_count: number
  latency_ms: number
}

export interface ChatResponse {
  intent_type: 'knowledge_query' | 'status_analysis' | 'report_generation' | 'preference_management'
  intent_label: string
  answer: string
  citations: Citation[]
  memory_hits: MemoryHit[]
  tool_results: ToolResult[]
  trace: TraceStep[]
  metrics: RunMetrics
}

export interface OverviewCard {
  label: string
  value: string | number
}

export interface OverviewMetric {
  label: string
  value: string
  hint: string
}

export interface DocumentRecord {
  id: string
  title: string
  source: string
  path?: string | null
  metadata: Record<string, unknown>
  created_at: string
}

export interface MemoryRecord {
  id: string
  user_id: string
  namespace: string
  memory_type: 'profile' | 'episodic' | 'semantic'
  content: string
  importance: number
  created_at: string
  updated_at: string
}

export interface OverviewResponse {
  cards: OverviewCard[]
  metrics: OverviewMetric[]
  latest_documents: DocumentRecord[]
  latest_memories: MemoryRecord[]
}