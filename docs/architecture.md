# 架构说明

## 1. 总体架构图

```mermaid
graph TD
    UI[Vue3 工作台] --> API[FastAPI 主后端]
    API --> ORCH[Orchestrator 多 Agent 编排]
    ORCH --> ROUTER[Router Agent]
    ORCH --> PLANNER[Planner Agent]
    ORCH --> MEMORY[Memory Agent]
    ORCH --> RETRIEVAL[Retrieval Agent]
    ORCH --> TOOL[Tool Agent]
    ORCH --> REPORT[Report Agent]

    RETRIEVAL --> KNOW[KnowledgeService]
    MEMORY --> MEM[MemoryService]
    TOOL --> MCP[MCPClient]
    REPORT --> A2A[A2AClient]

    KNOW --> STORE[(JSON / PostgreSQL + pgvector)]
    MEM --> STORE
    MEM --> CONV[(JSON / Redis)]
    KNOW --> OBJ[(Local / MinIO)]

    MCP --> MCP_SVC[MCP Server]
    MCP_SVC --> SQL[SQL Agent Service]
    A2A --> REPORT_SVC[Report Agent Service]
```

## 2. 一次汇报任务的执行时序

```mermaid
sequenceDiagram
    participant User as 用户
    participant UI as 前端工作台
    participant API as FastAPI
    participant Orch as Orchestrator
    participant Mem as MemoryAgent
    participant Rag as RetrievalAgent
    participant Tool as ToolAgent
    participant Report as ReportAgent

    User->>UI: 帮我总结支付系统最近故障，并给老板写一份汇报
    UI->>API: POST /api/v1/chat
    API->>Orch: run_chat
    Orch->>Orch: Router 判定为汇报生成
    Orch->>Orch: Planner 生成执行计划
    Orch->>Mem: 查询长期记忆
    Orch->>Rag: 查询知识文档
    Orch->>Tool: 调 MCP 工具
    Orch->>Report: 调远程或本地报告服务
    Report-->>Orch: 返回 Markdown 汇报
    Orch-->>API: ChatResponse
    API-->>UI: answer + citations + memory + tools + trace
```

## 3. 模块边界

### 3.1 主后端

负责：

- 对外 API
- Agent 编排
- RAG 和 Memory 主流程
- 工具聚合与结果整合

### 3.2 独立服务

负责：

- MCP Server：统一工具接入协议
- SQL Agent：只读 SQL 分析
- Report Agent：独立报告生成能力

### 3.3 存储与基础设施

负责：

- PostgreSQL + pgvector：结构化数据与向量检索
- Redis：短期会话
- MinIO：原始文件对象存储

## 4. 设计取舍

- 为保证项目可运行，默认保留 JSON / 本地文件回退模式
- 为保证基础设施完整性，同时实现 PostgreSQL、Redis、MinIO 真实接入
- 为保证协议接入真实可信，MCP Server 使用官方 SDK，而不是伪造“像 MCP”的 JSON 接口
- 为保证演示效果，前端把引用、Memory、工具结果、Trace 与指标拆成明确功能区
