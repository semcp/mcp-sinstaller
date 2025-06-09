import json
import shutil
from pathlib import Path
from typing import Dict, Any, List
from process_runner import CommandRunner
from github_service import GitHubService
from docker_service import DockerService
from analysis_service import AnalysisService

class ServerManager:
    """High-level orchestrator for MCP server management."""
    
    def __init__(self, servers_base_dir: Path, runner: CommandRunner):
        self.servers_dir = servers_base_dir
        self.runner = runner
        self.github_service = GitHubService(self.runner)
        self.docker_service = DockerService(self.runner)

    async def install(self, url: str, force: bool = False, ctx=None) -> Dict[str, Any]:
        """Orchestrates the installation of a server."""
        try:
            repo_info = GitHubService.parse_url(url)
            server_name = repo_info["server_name"]
            server_dir = self.servers_dir / server_name
            
            if server_dir.exists() and not force:
                return {
                    "success": False,
                    "error": f"Server '{server_name}' already exists. Use force=true to reinstall."
                }
            
            if server_dir.exists():
                shutil.rmtree(server_dir)
            
            self.github_service.clone(repo_info["clone_url"], server_dir, repo_info["branch"])
            
            if not ctx:
                return {
                    "success": False,
                    "error": "No request context available for analysis"
                }
            
            repo_path = server_dir / repo_info["path"] if repo_info["path"] else server_dir
            
            analyzer = AnalysisService(ctx)
            analysis_result = await analyzer.analyze_repository(repo_path, repo_info)
            
            if not analysis_result.get("success"):
                return analysis_result
            
            config_result = await analyzer.create_docker_plan(repo_path, analysis_result["analysis"], server_name)
            
            if not config_result.get("success"):
                return config_result
            
            plan = config_result["plan"]
            execution_result = self.docker_service.build_from_plan(plan, repo_path, server_name, server_dir)
            
            if execution_result.get("success"):
                dockerfile_status = "Using existing Dockerfile" if plan.get("has_existing_dockerfile") else "Generated new Dockerfile"
                
                return {
                    "success": True,
                    "server_name": server_name,
                    "url": url,
                    "server_dir": str(server_dir),
                    "dockerfile_status": dockerfile_status,
                    "analysis": analysis_result["analysis"],
                    **execution_result
                }
            else:
                return {
                    "success": False,
                    "server_name": server_name,
                    "analysis": analysis_result["analysis"],
                    "url": url,
                    "server_dir": str(server_dir),
                    **execution_result
                }
                
        except Exception as e:
            return {"success": False, "error": f"Installation failed: {str(e)}"}

    def update(self, server_name: str) -> Dict[str, Any]:
        """Update an installed MCP server."""
        server_dir = self.servers_dir / server_name
        
        if not server_dir.exists():
            return {
                "success": False,
                "error": f"Server '{server_name}' not found. Use install to install it first."
            }
        
        metadata_path = server_dir / "metadata.json"
        if not metadata_path.exists():
            return {
                "success": False,
                "error": f"Server '{server_name}' found but missing metadata. Please reinstall."
            }
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            self.github_service.pull(server_dir)
            
            update_result = self.docker_service.update_server(server_dir, metadata)
            
            if update_result.get("success"):
                with open(metadata_path, 'w') as f:
                    json.dump(update_result["metadata"], f, indent=2)
                
                return {
                    "success": True,
                    "server_name": server_name,
                    "metadata": update_result["metadata"],
                    **update_result
                }
            else:
                return update_result
                
        except Exception as e:
            return {"success": False, "error": f"Update failed: {str(e)}"}

    def delete(self, server_name: str) -> Dict[str, Any]:
        """Delete an installed MCP server and its environment."""
        server_dir = self.servers_dir / server_name
        
        if not server_dir.exists():
            return {
                "success": False,
                "error": f"Server '{server_name}' not found."
            }
        
        cleanup_results = []
        
        try:
            metadata = {}
            metadata_path = server_dir / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                except:
                    pass
            
            docker_cleanup = self.docker_service.cleanup_server(metadata, server_name)
            cleanup_results.extend(docker_cleanup)
            
            try:
                shutil.rmtree(server_dir)
                cleanup_results.append(f"✓ Removed repository: {server_dir}")
            except Exception as e:
                cleanup_results.append(f"⚠ File cleanup error: {str(e)}")
            
            return {
                "success": True,
                "server_name": server_name,
                "cleanup_results": cleanup_results
            }
            
        except Exception as e:
            return {"success": False, "error": f"Deletion failed: {str(e)}"}

    def list(self) -> Dict[str, Any]:
        """List all installed MCP servers."""
        if not self.servers_dir.exists():
            return {
                "success": True,
                "servers": [],
                "message": "No MCP servers installed yet."
            }
        
        servers = []
        
        for server_dir in self.servers_dir.iterdir():
            if not server_dir.is_dir():
                continue
                
            server_name = server_dir.name
            
            metadata_path = server_dir / "metadata.json"
            if not metadata_path.exists():
                servers.append({
                    "name": server_name,
                    "status": "ERROR",
                    "error": "Missing metadata.json (corrupted installation)"
                })
                continue
                
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                transport_type = metadata.get("transport_type", "unknown")
                ports = metadata.get("ports", {})
                required_secrets = metadata.get("required_secrets", [])
                created_at = metadata.get("created_at", "unknown")
                
                repo_url = "unknown"
                try:
                    git_result = self.runner.run([
                        "git", "-C", str(server_dir), "remote", "get-url", "origin"
                    ], check=False)
                    if git_result.returncode == 0:
                        repo_url = git_result.stdout.strip()
                except:
                    pass
                
                servers.append({
                    "name": server_name,
                    "repository": repo_url,
                    "transport": transport_type.upper(),
                    "ports": dict(ports) if ports else None,
                    "required_secrets": required_secrets if required_secrets else [],
                    "created": created_at,
                    "status": "OK"
                })
                
            except Exception as e:
                servers.append({
                    "name": server_name,
                    "status": "ERROR", 
                    "error": f"Failed to read metadata ({str(e)})"
                })
        
        return {
            "success": True,
            "servers": servers,
            "count": len(servers)
        } 