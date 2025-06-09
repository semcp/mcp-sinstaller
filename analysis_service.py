import os
from pathlib import Path
from typing import Dict, Any

class AnalysisService:
    """Service for repository analysis using LLM sampling."""
    
    def __init__(self, request_context):
        self.ctx = request_context
    
    async def analyze_repository(self, repo_path: Path, repo_info: Dict[str, str]) -> Dict[str, Any]:
        """Use LLM sampling to analyze and understand the repository"""
        
        try:
            readme_content = ""
            readme_path = repo_path / "README.md"
            if readme_path.exists() and readme_path.is_file():
                try:
                    readme_content = readme_path.read_text(encoding='utf-8')
                except:
                    pass
            
            file_overview = []
            
            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'target', 'dist', 'build']]
                
                level = len(Path(root).relative_to(repo_path).parts)
                if level > 2:
                    continue
                    
                for file in files:
                    if file.startswith('.'):
                        continue
                        
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(repo_path)
                    
                    if file_path.suffix in ['.py', '.js', '.ts', '.json', '.md', '.txt', '.yml', '.yaml', '.toml', '.xml'] or file in ['Dockerfile', 'Makefile']:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                lines = []
                                for i, line in enumerate(f):
                                    if i >= 10:
                                        break
                                    lines.append(line.rstrip())
                                
                                file_overview.append({
                                    "path": str(rel_path),
                                    "first_lines": lines
                                })
                        except:
                            pass
                            
                    if len(file_overview) >= 20:
                        break
                
                if len(file_overview) >= 20:
                    break
            
            readme_section = ""
            if readme_content:
                readme_section = f"\n\nFULL README CONTENT:\n{readme_content}\n"
            
            files_section = ""
            if file_overview:
                files_section = "\n\nPROJECT FILE OVERVIEW:\n"
                for file_info in file_overview:
                    files_section += f"\n--- {file_info['path']} (first 10 lines) ---\n"
                    files_section += "\n".join(file_info['first_lines'])
                    files_section += "\n"
            
            analysis_prompt = f"""
            You are analyzing an MCP server project to understand how to build and run it.
            
            Repository: {repo_info['owner']}/{repo_info['repo']}
            Server name: {repo_info['server_name']}
            Path in repo: {repo_info['path']}
            Repository location: {repo_path}
            
            Please analyze this project and provide your understanding in this format:
            
            PROJECT ANALYSIS:
            - What this MCP server does (purpose and functionality)
            - Programming language and framework used
            - Key dependencies
            - How to build/install the project
            - How to run the MCP server
            - Any special configuration needed
            - Entry points and main files
            - Transport type: STDIO or SSE (very important for Docker setup)
              * STDIO: Uses standard input/output for communication (no network ports needed)
              * SSE: Uses HTTP/WebSocket for communication (needs exposed ports)
              * Look for clues like: stdio transport, server-sent events, HTTP servers, port configurations
            
            Focus on understanding the project well enough that you could later create a containerized environment to run it successfully.
            {readme_section}{files_section}
            """
            
            result = await self.ctx.session.create_message(
                messages=[{
                    "role": "user",
                    "content": {"type": "text", "text": analysis_prompt}
                }],
                max_tokens=2000,
                system_prompt="You are an expert software engineer who understands how to build, deploy and run various types of projects. Pay special attention to the MCP transport type (STDIO vs SSE) as this is crucial for containerization.",
                include_context="thisServer"
            )
            
            return {"success": True, "analysis": result.content.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_docker_plan(self, repo_path: Path, analysis: str, server_name: str) -> Dict[str, Any]:
        """Create containerized environment using structured Docker planning"""
        
        try:
            existing_dockerfile = repo_path / "Dockerfile"
            has_dockerfile = existing_dockerfile.exists()
            
            if has_dockerfile:
                dockerfile_content = existing_dockerfile.read_text()
                environment_prompt = f"""
                This MCP server project already has a Dockerfile. Please analyze it and provide a structured Docker plan.

                PREVIOUS ANALYSIS:
                {analysis}

                PROJECT LOCATION: {repo_path}
                
                EXISTING DOCKERFILE:
                {dockerfile_content}

                CRITICAL: Respond with ONLY a JSON object. No explanations, no markdown, no additional text.

                JSON structure required:
                {{
                  "has_existing_dockerfile": true,
                  "dockerfile_content": "copy the existing Dockerfile content here. If the Dockerfile path is not correct, change it to the correct path.",
                  "image_name": "mcp-sinstaller-{server_name}",
                  "container_name": "mcp-{server_name}-container",
                  "ports": {{"8000": "8000"}},
                  "environment_variables": {{}},
                  "required_secrets": [],
                  "volumes": {{}},
                  "startup_command": null,
                  "health_check": null,
                  "transport_type": "determine from project analysis. choose stdio or sse"
                }}

                Analyze the Dockerfile and the project to determine:
                - Correct ports (if SSE/HTTP transport)
                - Environment variables and required secrets
                - Transport type: "stdio" or "sse" based on how the MCP server communicates

                IMPORTANT: If any path in the Dockerfile is not correct, change it to the correct path.

                Return ONLY the JSON object.
                """
            else:
                environment_prompt = f"""
                This MCP server project needs a Dockerfile created. Analyze the project and provide a complete Docker plan.

                PREVIOUS ANALYSIS:
                {analysis}

                PROJECT LOCATION: {repo_path}

                CRITICAL: Respond with ONLY a JSON object. No explanations, no markdown, no additional text.

                JSON structure required:
                {{
                  "has_existing_dockerfile": false,
                  "dockerfile_content": "Complete Dockerfile content based on the actual project type you discover",
                  "image_name": "mcp-sinstaller-{server_name}",
                  "container_name": "mcp-{server_name}-container", 
                  "ports": {{"8000": "8000"}},
                  "environment_variables": {{}},
                  "required_secrets": [],
                  "volumes": {{}},
                  "startup_command": null,
                  "health_check": null,
                  "transport_type": "determine from project analysis. choose stdio or sse"
                }}

                Analyze the actual project type first (Python/Node.js/TypeScript/Go/etc.) by examining the files in the repository, then:
                - Create appropriate Dockerfile content for that technology stack
                - Determine transport type: "stdio" (stdin/stdout) or "sse" (SSE/Streamable HTTP)
                - Set appropriate ports (only needed for SSE transport)
                - Identify any required secrets
                Return ONLY the JSON object.
                """

            result = await self.ctx.session.create_message(
                messages=[{
                    "role": "user",
                    "content": {"type": "text", "text": environment_prompt}
                }],
                max_tokens=1500,
                system_prompt="You are a DevOps expert. You MUST respond with ONLY valid JSON. Do not include any explanations, markdown formatting, or additional text. Only return the JSON object requested.",
                include_context="thisServer"
            )

            from docker_service import DockerService
            return DockerService.parse_plan(result.content.text, server_name)
            
        except Exception as e:
            return {"success": False, "error": str(e)} 