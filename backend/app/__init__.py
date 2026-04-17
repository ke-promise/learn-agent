"""主后端应用包。

这个包是整个 FastAPI 后端的根入口，下面按职责划分为：
- `api`：对外 HTTP 接口
- `agents`：多 Agent 编排节点
- `services`：业务能力实现
- `repositories`：数据读写
- `core`：配置、启动和依赖装配
"""