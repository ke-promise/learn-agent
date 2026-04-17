# 故障复盘与汇报助手

这是一个围绕“故障复盘与汇报”主场景构建的多 Agent 企业知识助理项目。它把文档检索、长期记忆、MCP 工具接入、A2A 报告协作，以及 PostgreSQL/pgvector、Redis、MinIO 等基础设施串成了一条完整链路。

## 当前实现

- FastAPI 后端与 Vue3 前端工作台
- Router / Planner / Retrieval / Memory / Tool / Report 六类 Agent
- RAG 文档导入、切块、向量检索与引用返回
- 长期记忆写入、检索与会话消息记录
- PostgreSQL + pgvector / JSON 双存储模式
- Redis 短期会话存储
- MinIO 与本地文件双对象存储模式
- MCP Server、SQL Agent、Report Agent 三个独立服务
- 扫描 PDF / 图片 OCR 回退解析
- Markdown 结果输出与 ECharts 指标可视化
- 可选 LangGraph 编排运行时

## 目录结构

```text
learn_agent/
├─ backend/                 # FastAPI 主应用
├─ frontend/                # Vue3 工作台
├─ services/                # 独立 MCP / SQL / Report 服务
├─ docker/                  # 容器构建文件
├─ docs/                    # 需求、技术、架构、学习文档
├─ docker-compose.yml
└─ .env.example
```

## 本地启动

### 1. 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 2. 前端

```powershell
cd frontend
npm install
npm run dev
```

### 3. 独立服务

```powershell
python -m services.mcp_server.run
uvicorn services.sql_agent_service.app:app --host 0.0.0.0 --port 8300
uvicorn services.report_agent_service.app:app --host 0.0.0.0 --port 8200
```

## Docker Compose 启动

```powershell
docker compose up --build
```

会启动：

- `postgres`：结构化数据 + pgvector
- `redis`：短期会话
- `minio`：对象存储
- `sql-agent`：只读 SQL 分析服务
- `report-agent`：报告生成服务
- `mcp-server`：统一工具接入入口
- `backend`：主后端 API

## 核心页面与接口

- 前端工作台：`frontend/src/App.vue`
- 后端入口：`backend/app/main.py`
- 聊天接口：`POST /api/v1/chat`
- 文档上传：`POST /api/v1/documents/upload`
- Memory 接口：`GET/POST /api/v1/memories`
- 概览接口：`GET /api/v1/overview`

## 推荐 Demo

加载“真实业务 Demo”后，系统会：

1. 写入支付系统事故与项目风险示例文档
2. 写入“我负责支付系统，汇报时喜欢先结论后依据”的长期记忆
3. 自动发起“帮我总结支付系统最近故障，并给老板写一份汇报”任务
4. 展示 Markdown 结果、引用、Memory、工具结果、Agent Trace 和指标图

## 文档入口

- [需求文档](docs/requirements.md)
- [技术设计](docs/technical-design.md)
- [架构说明](docs/architecture.md)
- [学习文档](docs/learning-guide.md)
- [源码导读文档](docs/source-walkthrough.md)
