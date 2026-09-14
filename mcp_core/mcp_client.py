# -*- coding: utf-8 -*-
#这段 Python 代码实现了一个 MCP客户端，用于与一个外部 MCP 服务器进程通信，调用其暴露的工具（如天气查询、音乐搜索等），并将结果返回。
import asyncio
import os
import json
from typing import Optional
from contextlib import AsyncExitStack
from openai import OpenAI  

from mcp import ClientSession, StdioServerParameters #表示与 MCP 服务器的会话，可发送请求、调用工具。配置如何启动 MCP 服务器进程
from mcp.client.stdio import stdio_client #通过标准输入输出（stdin/stdout）与子进程通信的客户端传输层。


class MCPClient:
    def __init__(self):
        """初始化 MCP 客户端"""
        self.exit_stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None #保存当前与 MCP 服务器的会话对象，初始为 None


    async def connect_to_server(self, server_script_path: str):
        """连接到 MCP 服务器并列出可用工具"""
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("服务器脚本必须是 .py 或 .js 文件")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None #表示继承当前环境变量
        )

        # 启动 MCP 服务器并建立通信
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport #从传输对象中提取读写接口
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        #发送初始化消息，完成 MCP 握手协议
        await self.session.initialize()

        # 列出 MCP 服务器上的工具
        response = await self.session.list_tools()
        tools = response.tools
        print("\n已连接到服务器，支持以下工具:", [tool.name for tool in tools])     
        

    async def process_query(self, query: str) -> str:
        return result
            
    
    async def execute(self, function_name, tool_args):
        print("\n🤖 MCP 客户端已启动")

        try:
            # 执行工具
            result = await self.session.call_tool(function_name, tool_args)
            print(f"\n\n[Calling tool with args {tool_args}]\n\n")
            print(f"\n🤖 MCP Response: {result.content[0].text}")
            return result.content[0].text

        except Exception as e:
            print(f"\n⚠️ 发生错误: {str(e)}")
            return "Not Find"


    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()


async def main():
    client = MCPClient()
    try:
        await client.connect_to_server("amp_server.py")
        await client.execute("maps_weather", {"city": "北京", "date": "2025-05-02"})
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys
    asyncio.run(main())

