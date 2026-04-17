import uvicorn


if __name__ == '__main__':
    # 单独运行 MCP Server 的便捷入口。
    uvicorn.run('services.mcp_server.app:app', host='0.0.0.0', port=8100)