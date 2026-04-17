# 源码导读文档

这份文档的目标不是重复需求说明，而是带你“顺着源码读懂整个项目”。

项目根目录：`D:\dev\vscode\ai_project\learn_agent`

建议你一边看这份文档，一边打开对应源码文件。最适合的阅读方式不是一次性全看完，而是按章节走读。

## 第 1 章：先建立全局地图

### 1.1 先看目录

项目主要分成三块：

- `backend/`：FastAPI 主后端，承接主业务链路
- `frontend/`：Vue3 工作台，负责展示输入、输出和链路
- `services/`：独立服务，包括 MCP Server、SQL Agent、Report Agent

你可以把它理解成一套真实业务系统的缩小版：

- 主后端负责“组织任务”
- 独立服务负责“提供专长能力”
- 前端负责“把复杂过程解释给人看”

### 1.2 先看核心文件

如果你只想最快建立整体印象，先看这几个文件：

1. `backend/app/main.py`
2. `backend/app/core/container.py`
3. `backend/app/agents/orchestrator.py`
4. `backend/app/services/knowledge_service.py`
5. `backend/app/services/memory_service.py`
6. `services/mcp_server/app.py`
7. `frontend/src/stores/dashboard.ts`
8. `frontend/src/App.vue`

## 第 2 章：应用是怎么启动起来的

### 2.1 后端入口：`backend/app/main.py`

这个文件是 FastAPI 的主入口。

你重点看三件事：

- `app = FastAPI(...)`
- `@app.on_event('startup')`
- `app.include_router(...)`

它表达的是一个很清楚的结构：

1. 先创建应用实例
2. 启动时初始化共享依赖
3. 最后挂上业务路由

也就是说，`main.py` 不负责业务逻辑，它只是把系统“拼起来”。

### 2.2 启动时做了什么：`backend/app/core/bootstrap.py`

这里的工作非常集中：

- 创建本地需要的数据目录
- 构建容器 `build_container()`
- 把容器挂到 `app.state.container`

这样后面的路由层就不需要自己初始化服务对象了。

### 2.3 容器如何装配：`backend/app/core/container.py`

这是你读后端时最值得停下来理解的文件之一。

它做的是“依赖装配”，顺序是：

1. 决定主存储后端是 `JSON` 还是 `PostgreSQL`
2. 决定会话后端是 `JSON` 还是 `Redis`
3. 决定对象存储是本地文件还是 `MinIO`
4. 构建基础组件：`EmbeddingService`、`DocumentParser`
5. 构建服务层：`KnowledgeService`、`MemoryService`、`OpsService`
6. 构建协议层：`MCPClient`、`A2AClient`
7. 构建 Agent：`ToolAgent`、`ReportAgent`
8. 最后构建 `Orchestrator`

这一点非常重要：

- 服务层是能力
- Agent 层是协作
- `Orchestrator` 是总调度器

## 第 3 章：一条请求是怎么走完的

这一章建议配合 `backend/app/agents/orchestrator.py` 一起看。

### 3.1 从接口进入

聊天入口在：`backend/app/api/routes/chat.py`

核心代码非常薄：

```python
@router.post('', response_model=ChatResponse)
async def chat(payload: ChatRequest, container: AppContainer = Depends(get_container)) -> ChatResponse:
    return await container.orchestrator.run_chat(payload)
```

这段代码体现了项目的分层原则：

- 路由层不处理复杂业务
- 路由层只负责接收请求和转发给编排器

### 3.2 编排主入口：`run_chat()`

`Orchestrator.run_chat()` 是整个项目最重要的方法。

它的主要步骤是：

1. 记录用户消息到短期会话
2. 初始化状态 `state`
3. 根据环境决定走 `LangGraph` 还是内置顺序编排
4. 执行所有需要的节点
5. 尝试从用户输入中抽取长期记忆
6. 把回答写回短期会话
7. 计算指标并记录一次运行结果
8. 返回 `ChatResponse`

你可以把 `state` 理解成“这一轮任务的工作台”，所有节点都在同一个状态对象上读写。

### 3.3 为什么有两个编排模式

在 `orchestrator.py` 里你会看到：

```python
if self.graph_app is not None:
    final_state = await self.graph_app.ainvoke(state)
    orchestration_mode = 'langgraph'
else:
    final_state = await self._run_builtin(state)
    orchestration_mode = 'builtin'
```

这个设计很值得学习。

它意味着：

- 安装了 `LangGraph` 时，可以展示图编排能力
- 没安装时，项目仍然可以完整运行

这是一个典型的工程取舍：

- 不让“高级架构”阻塞“基础可运行性”

## 第 4 章：Agent 是怎么拆开的

### 4.1 Router Agent：`backend/app/agents/router_agent.py`

Router 的职责不是回答问题，而是做用户意图分类。

当前只分四类：

- `knowledge_query`
- `status_analysis`
- `report_generation`
- `preference_management`

这比 `qa/sql/report/memory` 更像产品语言，也更适合面试表达。

### 4.2 Planner Agent：`backend/app/agents/planner_agent.py`

Planner 根据意图决定该走哪些节点。

例如：

- 知识查询：`memory -> retrieval`
- 状态分析：`memory -> retrieval -> tool`
- 汇报生成：`memory -> retrieval -> tool -> report`

也就是说，Planner 解决的是：

- 这次任务需要哪些能力组合

### 4.3 Memory Agent：`backend/app/agents/memory_agent.py`

只负责查长期记忆，不负责写入。

这样拆开的好处是：

- “查” 和 “写” 是两类不同责任
- 查询作为流程节点很常见
- 写入则更像任务结束后的副作用处理

### 4.4 Retrieval Agent：`backend/app/agents/retrieval_agent.py`

只做知识检索，把问题交给 `KnowledgeService.search()`。

### 4.5 Tool Agent：`backend/app/agents/tool_agent.py`

这个节点非常有代表性。

它一次并发调了 6 类工具：

- 文档检索
- 记忆检索
- 指标查询：`incident_count`
- 指标查询：`alpha_risk_score`
- 工单查询：`INC-1024`
- SQL 分析

这说明项目里“工具调用”不是 prompt 里写死的，而是显式的工程节点。

### 4.6 Report Agent：`backend/app/agents/report_agent.py`

它本身不生成报告，而是把任务交给 `A2AClient`。

这很好地体现了 A2A 的含义：

- 主系统负责调度
- 专长能力可以独立部署

## 第 5 章：RAG 是怎么落地的

### 5.1 先看文档导入：`backend/app/services/knowledge_service.py`

`ingest_document()` 的流程可以拆成这样：

1. 调 `DocumentParser` 把上传内容解析成纯文本
2. 如果有原始文件，则写到对象存储
3. 创建文档主记录 `DocumentRecord`
4. 对文本做轻量切块
5. 为每个切块生成 embedding
6. 把切块写入存储

关键点不在“能不能上传文档”，而在于：

- 原始文件和检索切块是分开存的

### 5.2 为什么对象存储和知识块要分开

- 原始文件适合放 `MinIO / 本地文件目录`
- 切块文本适合放 `JSON / PostgreSQL + pgvector`

如果把两者混在一起，后面会很难解释“文件存哪里”和“向量检索怎么做”。

### 5.3 检索时怎么工作

`search()` 的逻辑是：

1. 问题先变成 embedding
2. 如果底层支持 `search_chunks`，走数据库向量检索
3. 否则在 JSON 记录上本地算相似度
4. 最终包装成 `Citation`

这里的 `Citation` 很关键，因为它是“可解释性”的直接输出。

## 第 6 章：Memory 是怎么设计的

### 6.1 长期记忆：`backend/app/services/memory_service.py`

`MemoryService` 管三件事：

- 长期记忆增删查里的“增”和“查”
- 会话短期消息记录
- 运行指标记录

虽然看起来有点多，但本质上都属于“上下文管理”。

### 6.2 为什么 `maybe_capture_memory()` 很重要

这个方法体现了项目的产品思维。

它不会把所有输入都记下来，只在出现这些关键词时尝试写入长期记忆：

- `记住`
- `偏好`
- `喜欢`
- `负责`
- `以后默认`
- `长期`

也就是说：

- Memory 不是聊天日志
- Memory 是对未来任务有长期价值的信息

### 6.3 Memory 和 RAG 的区别

你一定要从源码层面记住这件事：

- `KnowledgeService` 查的是“企业文档”
- `MemoryService` 查的是“用户背景”

这两个模块是分开的，不是一个大表硬塞两类数据。

## 第 7 章：工具和协议层怎么理解

### 7.1 OpsService：`backend/app/services/ops_service.py`

`OpsService` 是一个业务数据面服务，负责：

- 工单查询
- 指标查询
- 只读 SQL 分析

它不是“大模型工具”，而是明确的领域服务。

### 7.2 MCPClient：`backend/app/services/mcp_client.py`

这是“主系统如何调用工具”的统一入口。

逻辑是：

1. 如果配置了 `MCP_SERVER_URL`，走真实 MCP Server
2. 如果没配置，回退到本地服务实现

这就是 MCP 在项目里的真实价值：

- 工具能力从 Agent Runtime 中解耦出来

### 7.3 MCP Server：`services/mcp_server/app.py`

这里不是模拟接口，而是真的用了 MCP Python SDK 的 `FastMCP`。

它暴露了这些工具：

- `search_docs`
- `search_memory`
- `query_metric`
- `get_ticket`
- `run_sql_analysis`

你可以把 MCP Server 理解成“工具中心”。

## 第 8 章：A2A 是怎么体现的

### 8.1 A2AClient：`backend/app/services/a2a_client.py`

它的逻辑非常清晰：

1. 如果配置了远程报告服务地址，就发 HTTP 请求
2. 如果没有，或者远程失败，就用本地 Markdown 模板兜底

这就实现了“独立部署”和“本地可跑”两种模式兼容。

### 8.2 Report Agent Service：`services/report_agent_service/app.py`

这个服务本身很轻，只提供 `/report` 接口。

它的重点不在复杂算法，而在于把“报告生成能力”单独拆成了一个服务边界。

## 第 9 章：存储层怎么读

### 9.1 JSON 回退：`backend/app/repositories/json_store.py`

这是项目的学习友好层。

作用是：

- 没有数据库也能完整运行
- 本地调试不需要额外装一堆基础设施

### 9.2 PostgreSQL + pgvector：`backend/app/repositories/postgres_store.py`

这个文件建议慢慢看。

重点看三类内容：

- ORM 模型定义
- `search_chunks()` / `search_memories()` 如何做向量检索
- `tickets` / `incident_events` 如何支撑 SQL Agent 和指标能力

一个很重要的设计点是：

- `PostgresStore` 的方法名尽量和 `JsonStore` 对齐

这样上层服务就能做到“尽量不感知底层差异”。

### 9.3 Redis：`backend/app/repositories/redis_store.py`

只负责会话消息，不负责知识和长期记忆。

这体现了典型的数据分工：

- 长期数据进数据库
- 高频、短期、可过期数据进 Redis

## 第 10 章：前端是怎么组织的

### 10.1 状态层：`frontend/src/stores/dashboard.ts`

这里是前端最值得先读的文件。

它做三类事：

- 拉概览数据
- 发聊天请求
- 做上传文档、写记忆、加载 Demo 等动作

换句话说，它是前端页面和后端接口之间的桥。

### 10.2 页面主结构：`frontend/src/App.vue`

这个文件很长，但你不要从上到下死读。

建议按这几个块看：

1. 左侧概览面板
2. 顶部快速操作区
3. 三个 tab
4. 工作台主结果区
5. 知识库管理区
6. Memory 管理区
7. 脚本里的状态和动作函数

页面的核心设计思路是：

- 不把所有内容堆成一个聊天框
- 而是把“输入、结果、引用、Memory、工具、Trace”拆开

### 10.3 图表：`frontend/src/components/InsightCharts.vue`

这里用 ECharts 画两张图：

- 系统指标柱状图
- 最近一次任务 Trace 折线图

这两张图刚好对应：

- 全局运行情况
- 单次任务执行链路

## 第 11 章：独立服务怎么读

### 11.1 SQL Agent Service

文件：`services/sql_agent_service/app.py`

重点：

- `/analyze`：问题 -> SQL -> 结果摘要
- `/execute`：执行只读 SQL

这个服务不是假装 LLM，而是明确声明“规则驱动、只读 SQL”。

### 11.2 Report Agent Service

文件：`services/report_agent_service/app.py`

重点：

- 接收 `topic + facts`
- 返回 Markdown 报告

### 11.3 MCP Server

文件：`services/mcp_server/app.py`

重点：

- 用官方 MCP SDK
- 暴露结构化工具
- 支持远程 SQL Agent 联动

## 第 12 章：推荐的实际阅读顺序

如果你想真的读懂项目，我建议按下面顺序：

1. `README.md`
2. `docs/architecture.md`
3. `backend/app/main.py`
4. `backend/app/core/bootstrap.py`
5. `backend/app/core/container.py`
6. `backend/app/api/routes/chat.py`
7. `backend/app/agents/orchestrator.py`
8. `backend/app/agents/router_agent.py`
9. `backend/app/agents/planner_agent.py`
10. `backend/app/services/knowledge_service.py`
11. `backend/app/services/memory_service.py`
12. `backend/app/services/mcp_client.py`
13. `backend/app/repositories/postgres_store.py`
14. `services/mcp_server/app.py`
15. `frontend/src/stores/dashboard.ts`
16. `frontend/src/App.vue`

## 第 13 章：读源码时最值得思考的问题

建议你边读边回答这些问题：

- 为什么 `Orchestrator` 不直接写工具调用逻辑，而要依赖 `ToolAgent`？
- 为什么 `MemoryService` 和 `KnowledgeService` 必须拆开？
- 为什么容器层要先装配服务，再装配 Agent？
- 为什么前端要把引用、Memory、Trace 和结果分开显示？
- 为什么 `MCPClient` 和 `A2AClient` 都做了“远程优先、本地兜底”？

如果你能把这些问题答顺，基本就已经真的理解这个项目了。

## 第 14 章：看完后你应该得到什么

读完整个项目后，你应该至少能清楚表达这些事：

- 这不是单纯的聊天机器人，而是一套围绕故障复盘的工作流系统
- 后端的核心是多 Agent 编排，而不是某一段 Prompt
- RAG、Memory、MCP、A2A 在代码里各自承担了明确职责
- 基础设施不是摆设，`PostgreSQL / Redis / MinIO` 都在真实支撑不同类型的数据
- 前端的价值不仅是“能聊天”，而是“让结果可解释、可验证、可展示”