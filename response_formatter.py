from typing import List, Dict, Any
from mcp import types

class ResponseFormatter:
    """Formats operation results into MCP TextContent responses."""
    
    @staticmethod
    def format_install_success(result: Dict[str, Any]) -> List[types.TextContent]:
        """Format successful installation result."""
        server_name = result['server_name']
        image_name = result['image_name']
        required_secrets = result.get('required_secrets', [])
        ports = result.get('ports', [])
        
        config_name = server_name.replace('-', '_')
        
        docker_args = ["run", "-i", "--rm"]
        
        env_config = ""
        env_instructions = ""
        if required_secrets:
            env_config = f',\n        "env": {{\n'
            env_entries = []
            for secret in required_secrets:
                env_entries.append(f'            "{secret}": "${{input:{secret.lower().replace("_", "-")}}}"')
            env_config += ',\n'.join(env_entries)
            env_config += '\n        }'
            
            env_instructions = f"\n\n**ENVIRONMENT VARIABLES SETUP:**\n"
            env_instructions += f"This server requires the following secrets. VS Code/Cursor will prompt you for these:\n"
            for secret in required_secrets:
                env_instructions += f"- {secret}\n"
        
        mcp_config = f'''"servers": {{
    "{config_name}": {{
        "type": "stdio",
        "command": "docker",
        "args": {docker_args + [image_name]}{env_config}
    }}
}}'''
        
        setup_instructions = f"""**MCP Server '{server_name}' is ready!**

** IMPORTANT:**

This is not the final step. To run the server, you still need to add the server to MCP client's MCP settings. Please display the following JSON configuration to the user.

VS Code: Add to `.vscode/settings.json` under `"mcp"`:
```json
{mcp_config}
```{env_instructions}

**SERVER DETAILS:**
- Repository: {result['url']}
- Docker Image: {image_name}
- Build Status: {result['dockerfile_status']}
- Transport: STDIO (recommended for MCP)"""
        
        if ports:
            setup_instructions += f"\n- Exposed Ports: {', '.join(map(str, ports))}"
        
        return [types.TextContent(
            type="text",
            text=setup_instructions
        )]

    @staticmethod
    def format_install_failure(result: Dict[str, Any]) -> List[types.TextContent]:
        """Format installation failure result."""
        return [types.TextContent(
            type="text",
            text=f"Docker build failed for MCP server '{result['server_name']}'.\n\n" +
                  f"Analyze result: {result.get('analysis', 'No analysis available')}\n\n" +
                  f"Repository: {result['url']}\n" +
                  f"Location: {result['server_dir']}\n\n" +
                  f"DOCKER ERROR:\n{result.get('error', 'Unknown Docker error')}\n\n" +
                  f"STDOUT:\n{result.get('docker_stdout', 'No output')}\n\n" +
                  f"STDERR:\n{result.get('docker_stderr', 'No errors')}\n\n" +
                  f"Return Code: {result.get('return_code', 'Unknown')}"
        )]

    @staticmethod
    def format_update_success(result: Dict[str, Any]) -> List[types.TextContent]:
        """Format successful update result."""
        metadata = result["metadata"]
        return [types.TextContent(
            type="text",
            text=f"Successfully updated MCP server '{result['server_name']}'!\n\n" +
                  f"Docker image rebuilt:\n{result['image_info']}\n\n" +
                  f"Run instructions:\n{metadata.get('run_instructions', 'Use docker run commands from metadata')}"
        )]

    @staticmethod
    def format_delete_success(result: Dict[str, Any]) -> List[types.TextContent]:
        """Format successful deletion result."""
        return [types.TextContent(
            type="text",
            text=f"Cleanup completed for MCP server '{result['server_name']}':\n\n" + 
                  "\n".join(result['cleanup_results'])
        )]

    @staticmethod
    def format_list_result(result: Dict[str, Any]) -> List[types.TextContent]:
        """Format list servers result."""
        if not result['servers']:
            return [types.TextContent(
                type="text",
                text=result.get('message', 'No MCP servers installed yet.')
            )]
        
        server_info = []
        for server in result['servers']:
            if server['status'] == 'ERROR':
                server_info.append(f"• {server['name']}: ERROR - {server['error']}")
            else:
                ports_str = 'none (STDIO)' if not server['ports'] else str(server['ports'])
                secrets_str = 'none' if not server['required_secrets'] else str(server['required_secrets'])
                
                server_info.append(f"""• {server['name']}
  Repository: {server['repository']}
  Transport: {server['transport']}
  Ports: {ports_str}
  Required Secrets: {secrets_str}
  Created: {server['created']}""")
        
        return [types.TextContent(
            type="text",
            text=f"Installed MCP servers ({result['count']}):\n\n" + "\n\n".join(server_info)
        )]

    @staticmethod
    def format_error(error_message: str) -> List[types.TextContent]:
        """Format error message."""
        return [types.TextContent(
            type="text",
            text=f"Operation failed: {error_message}"
        )] 