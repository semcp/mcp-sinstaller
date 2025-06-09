from typing import List, Dict, Any
from mcp import types

class ResponseFormatter:
    """Formats operation results into MCP TextContent responses."""
    
    @staticmethod
    def format_install_success(result: Dict[str, Any]) -> List[types.TextContent]:
        """Format successful installation result."""
        return [types.TextContent(
            type="text",
            text=f"Successfully built Docker image for MCP server '{result['server_name']}'!\n\n" +
                  f"Repository: {result['url']}\n" +
                  f"Location: {result['server_dir']}\n\n" +
                  f"DOCKER IMAGE:\n" +
                  f"- {result['dockerfile_status']}\n" +
                  f"- Image: {result['image_name']}\n" +
                  f"- Size & Created: {result['image_info']}\n" +
                  f"- Ports: {result['ports']}\n" +
                  f"- Environment Variables: {result['environment_variables']}\n" +
                  f"- Required Secrets: {result['required_secrets']}\n" +
                  f"- Metadata: {result['metadata_path']}\n\n" +
                  f"{result['run_instructions']}"
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