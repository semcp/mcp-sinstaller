import asyncio
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from process_runner import CommandRunner
from server_manager import ServerManager
from response_formatter import ResponseFormatter

server = Server("mcp-sinstaller")

MCP_SINSTALLER_DIR = Path.home() / ".mcp-sinstaller"
SERVERS_DIR = MCP_SINSTALLER_DIR / "servers"

runner = CommandRunner()
manager = ServerManager(SERVERS_DIR, runner)

def ensure_directories():
    """Ensure the installer directories exist"""
    SERVERS_DIR.mkdir(parents=True, exist_ok=True)

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="install_mcp",
            description="Install an MCP server from a GitHub repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "GitHub URL to the MCP server repository or specific path"
                    },
                    "force": {
                        "type": "boolean", 
                        "description": "Force reinstall if server already exists",
                        "default": False
                    }
                },
                "required": ["url"]
            }
        ),
        types.Tool(
            name="update_mcp",
            description="Update an installed MCP server to the latest version",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_name": {
                        "type": "string",
                        "description": "Name of the installed MCP server to update"
                    }
                },
                "required": ["server_name"]
            }
        ),
        types.Tool(
            name="delete_mcp",
            description="Delete an installed MCP server and its environment",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_name": {
                        "type": "string",
                        "description": "Name of the MCP server to delete"
                    }
                },
                "required": ["server_name"]
            }
        ),
        types.Tool(
            name="list_mcp",
            description="List all installed MCP servers",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    ensure_directories()
    ctx = server.request_context

    try:
        if name == "install_mcp":
            result = await manager.install(
                url=arguments["url"], 
                force=arguments.get("force", False), 
                ctx=ctx
            )
            if result.get("success"):
                return ResponseFormatter.format_install_success(result)
            else:
                return ResponseFormatter.format_install_failure(result)
                
        elif name == "update_mcp":
            result = manager.update(arguments["server_name"])
            if result.get("success"):
                return ResponseFormatter.format_update_success(result)
            else:
                return ResponseFormatter.format_error(result.get("error", "Update failed"))
                
        elif name == "delete_mcp":
            result = manager.delete(arguments["server_name"])
            if result.get("success"):
                return ResponseFormatter.format_delete_success(result)
            else:
                return ResponseFormatter.format_error(result.get("error", "Delete failed"))
                
        elif name == "list_mcp":
            result = manager.list()
            return ResponseFormatter.format_list_result(result)
            
        else:
            return ResponseFormatter.format_error(f"Unknown tool: {name}")
            
    except Exception as e:
        return ResponseFormatter.format_error(str(e))

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main()) 