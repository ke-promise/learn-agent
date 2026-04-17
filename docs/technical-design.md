# 技术设计文档

## 1. 总体设计

项目采用前端工作台 + 主后端 + 独立服务的结构：

- 前端：Vue3 + Pinia + ECharts
- 主后端：FastAPI + 多 Agent 编排
- 存储：JSON 或 PostgreSQL + pgvector，Redis，会话对象存储
- 独立服务：MCP Server、SQL Agent、Report Agent

## 2. 主后端模块

### 2.1 API 层

- `app/main.py`：FastAPI 入口与健康检查
- `app/api/router.py`：聚合业务路由
- `app/api/routes/*`：聊天、文档、记忆、概览接口

### 2.2 服务层

- `knowledge_service.py`：文档摄取与检索
- `memory_service.py`：长期记忆与会话管理
- `ops_service.py`：指标、工单与 SQL 分析
- `mcp_client.py`：MCP 工具调用客户端
- `a2a_client.py`：远程报告协作客户端
- `dashboard_service.py`：概览统计

### 2.3 Agent 层

- `router_agent.py`：用户意图分类
- `planner_agent.py`：执行计划拆解
- `memory_agent.py`：长期记忆查询
- `retrieval_agent.py`：知识检索
- `tool_agent.py`：统一工具调用
- `report_agent.py`：汇报生成
- `orchestrator.py`：主编排执行器
- `langgraph_runtime.py`：LangGraph 可选编排

## 3. RAG 设计

### 3.1 摄取链路

1. 接收上传文件或文本
2. 根据类型解析文本
3. 对文本做轻量切块
4. 通过哈希 embedding 生成向量
5. 写入文档表和块表

### 3.2 查询链路

1. 根据问题生成查询向量
2. 优先用 pgvector 做相似度检索
3. 没有 pgvector 时用本地余弦相似度回退
4. 返回 top-k 文档片段及引用信息

### 3.3 设计原则

- RAG 负责外部知识
- Memory 负责用户背景与历史任务
- 两者分库分责，不混合存储语义

## 4. Memory 设计

### 4.1 短期记忆

- 会话消息列表
- 当前任务链路的上下文
- 可落 JSON 或 Redis

### 4.2 长期记忆

- Profile：职责、系统归属、输出偏好
- Episodic：历史任务摘要
- Semantic：长期稳定习惯或经验

### 4.3 写入策略

当前实现会在命中这些关键词时尝试写入：

- `记住`
- `偏好`
- `喜欢`
- `负责`
- `以后默认`
- `长期`

## 5. MCP 设计

MCP Server 通过官方 Python SDK 的 `FastMCP` 提供 Streamable HTTP 接口，主后端用 `ClientSession + streamable_http_client` 调用工具。

已提供工具：

- `search_docs`
- `search_memory`
- `query_metric`
- `get_ticket`
- `run_sql_analysis`

## 6. A2A 设计

- 主系统通过 `A2AClient` 调用远程 Report Agent
- 远程地址不可用时，回退到本地 Markdown 汇报模板
- 当前 A2A 采用清晰可运行的 HTTP 服务实现，而不是伪造协议

## 7. 基础设施设计

### 7.1 PostgreSQL + pgvector

- `documents`：文档元数据
- `chunks`：知识块和向量
- `memories`：长期记忆和向量
- `runs`：任务运行指标
- `tickets`、`incident_events`：工单与故障事件示例数据

### 7.2 Redis

- 用于短期会话消息存储
- key 格式：`conversation:{conversation_id}`

### 7.3 MinIO

- 存储原始上传文件
- 本地模式下回退为文件目录

## 8. 前端设计

- 工作台突出主流程：输入任务、查看摘要、阅读 Markdown 结果、核对引用与 Trace
- 知识库管理支持文本与文件上传
- Memory 管理支持长期记忆查看和写入
- ECharts 展示系统指标和最近一次任务 Trace
