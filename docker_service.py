import json
import shutil
from pathlib import Path
from typing import Dict, Any, List
from process_runner import CommandRunner

class DockerService:
    """Service for Docker operations."""
    
    def __init__(self, runner: CommandRunner):
        self.runner = runner
    
    @staticmethod
    def parse_plan(response_text: str, server_name: str) -> Dict[str, Any]:
        """Parse and validate the JSON Docker plan from the client"""
        
        try:
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()
            
            plan = json.loads(response_text)
            
            required_fields = ["dockerfile_content", "image_name", "container_name", "ports"]
            for field in required_fields:
                if field not in plan:
                    return {"success": False, "error": f"Missing required field in Docker plan: {field}"}
            
            if not isinstance(plan["ports"], dict):
                return {"success": False, "error": "Ports must be a dictionary mapping container_port:host_port"}
                
            plan.setdefault("environment_variables", {})
            plan.setdefault("required_secrets", [])
            plan.setdefault("volumes", {})
            plan.setdefault("startup_command", None)
            plan.setdefault("health_check", None)
            plan.setdefault("has_existing_dockerfile", False)
            
            return {"success": True, "plan": plan}
            
        except json.JSONDecodeError as e:
            return {
                "success": False, 
                "error": f"Invalid JSON in Docker plan: {str(e)}",
                "raw_response": response_text[:500] + "..." if len(response_text) > 500 else response_text
            }
        except Exception as e:
            return {
                "success": False, 
                "error": f"Failed to parse Docker plan: {str(e)}",
                "raw_response": response_text[:500] + "..." if len(response_text) > 500 else response_text
            }

    def build_from_plan(self, plan: Dict[str, Any], repo_path: Path, server_name: str, server_dir: Path = None) -> Dict[str, Any]:
        """Execute the Docker plan by building image and providing run instructions"""
        
        try:
            dockerfile_path = repo_path / "Dockerfile"
            
            if not plan.get("has_existing_dockerfile", False):
                dockerfile_path.write_text(plan["dockerfile_content"])
            
            transport_type = plan.get("transport_type", "sse")
            is_stdio = transport_type.lower() == "stdio"
            
            metadata = {
                "server_name": server_name,
                "repository_path": str(repo_path),
                "image_name": plan["image_name"],
                "container_name": plan["container_name"],
                "ports": plan["ports"],
                "environment_variables": plan["environment_variables"],
                "required_secrets": plan["required_secrets"],
                "volumes": plan.get("volumes", {}),
                "startup_command": plan.get("startup_command"),
                "transport_type": transport_type,
                "created_at": self.runner.run(["date", "-Iseconds"]).stdout.strip(),
                "status": "image_built"
            }
            
            metadata_path = (server_dir or repo_path) / "metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self._remove_old_image(plan["image_name"])
            
            build_result = self.runner.run([
                "docker", "build", "-t", plan["image_name"], str(repo_path)
            ], check=False)
            
            if build_result.returncode != 0:
                metadata["status"] = "build_failed"
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                return {
                    "success": False,
                    "error": "Docker build failed",
                    "docker_stdout": build_result.stdout,
                    "docker_stderr": build_result.stderr,
                    "return_code": build_result.returncode
                }
            
            run_command, run_instructions = self._generate_run_instructions(plan, is_stdio)
            
            metadata["status"] = "ready_to_run"
            metadata["run_command"] = run_command
            metadata["run_instructions"] = run_instructions
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            image_info = self.runner.run([
                "docker", "images", "--format", "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}", plan["image_name"]
            ])
            
            return {
                "success": True,
                "image_name": plan["image_name"],
                "image_info": image_info.stdout.strip(),
                "build_output": build_result.stdout,
                "run_command": run_command,
                "run_instructions": run_instructions,
                "transport_type": transport_type,
                "ports": plan["ports"] if not is_stdio else {},
                "environment_variables": list(plan["environment_variables"].keys()),
                "required_secrets": plan["required_secrets"],
                "metadata_path": str(metadata_path)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Docker execution failed: {str(e)}"}

    def _remove_old_image(self, image_name: str):
        """Remove old Docker image if it exists"""
        try:
            old_image = self.runner.run([
                "docker", "images", "-q", image_name
            ], check=False)
            
            if old_image.stdout.strip():
                self.runner.run(["docker", "rmi", "-f", old_image.stdout.strip()], check=False)
        except:
            pass

    def _generate_run_instructions(self, plan: Dict[str, Any], is_stdio: bool) -> tuple[str, str]:
        """Generate Docker run command and instructions"""
        if is_stdio:
            run_cmd_parts = [
                "docker", "run", "-i", "--rm", "--name", plan["container_name"]
            ]
        else:
            run_cmd_parts = [
                "docker", "run", "-d", "--name", plan["container_name"]
            ]
            
            for container_port, host_port in plan["ports"].items():
                run_cmd_parts.extend(["-p", f"{host_port}:{container_port}"])
        
        for env_key, env_value in plan["environment_variables"].items():
            run_cmd_parts.extend(["-e", f"{env_key}={env_value}"])
        
        secret_placeholders = []
        for secret in plan["required_secrets"]:
            run_cmd_parts.extend(["-e", f"{secret}=${{{secret}}}"])
            secret_placeholders.append(f"export {secret}=your_actual_{secret.lower()}_here")
        
        for host_path, container_path in plan.get("volumes", {}).items():
            run_cmd_parts.extend(["-v", f"{host_path}:{container_path}"])
        
        run_cmd_parts.append(plan["image_name"])
        
        if plan.get("startup_command"):
            run_cmd_parts.extend(plan["startup_command"].split())
        
        run_command = " ".join(run_cmd_parts)
        
        if is_stdio:
            run_instructions = f"""
TO RUN THE CONTAINER (STDIO Transport):

1. Set required environment variables (if any):
{chr(10).join(secret_placeholders) if secret_placeholders else "   No secrets required"}

2. Run the container interactively:
   {run_command}
   
   Note: This server uses STDIO transport (stdin/stdout communication).
   - The container runs interactively (-i flag)
   - It will be automatically removed when it exits (--rm flag)
   - No port mapping needed as it uses standard input/output

3. Use your MCP client to connect via subprocess/stdio transport
"""
        else:
            run_instructions = f"""
TO RUN THE CONTAINER (SSE/HTTP Transport):

1. Set required environment variables (if any):
{chr(10).join(secret_placeholders) if secret_placeholders else "   No secrets required"}

2. Run the container:
   {run_command}

3. Use your MCP client to connect via SSE/HTTP transport
"""
        
        return run_command, run_instructions

    def update_server(self, server_dir: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update a server by rebuilding its Docker image"""
        try:
            old_image = metadata.get("image_name")
            if old_image:
                self._remove_old_image(old_image)
            
            build_path = metadata.get("repository_path", str(server_dir))
            
            build_result = self.runner.run([
                "docker", "build", "-t", old_image, build_path
            ], check=False)
            
            if build_result.returncode != 0:
                return {
                    "success": False,
                    "error": "Docker rebuild failed",
                    "stdout": build_result.stdout,
                    "stderr": build_result.stderr
                }
            
            metadata["updated_at"] = self.runner.run(["date", "-Iseconds"]).stdout.strip()
            metadata["status"] = "ready_to_run"
            
            image_info = self.runner.run([
                "docker", "images", "--format", "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}", old_image
            ])
            
            return {
                "success": True,
                "image_info": image_info.stdout,
                "build_output": build_result.stdout,
                "metadata": metadata
            }
            
        except Exception as e:
            return {"success": False, "error": f"Docker update failed: {str(e)}"}

    def cleanup_server(self, metadata: Dict[str, Any], server_name: str) -> List[str]:
        """Clean up Docker resources for a server"""
        cleanup_results = []
        
        container_name = metadata.get("container_name", f"mcp-{server_name}-container")
        image_name = metadata.get("image_name", f"mcp-sinstaller-{server_name}")
        
        try:
            container_check = self.runner.run([
                "docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.ID}}"
            ], check=False)
            
            if container_check.stdout.strip():
                self.runner.run(["docker", "stop", container_name], check=False)
                
                remove_result = self.runner.run([
                    "docker", "rm", container_name
                ], check=False)
                
                if remove_result.returncode == 0:
                    cleanup_results.append(f"✓ Removed container: {container_name}")
                else:
                    cleanup_results.append(f"⚠ Container removal failed: {remove_result.stderr}")
            else:
                cleanup_results.append(f"ℹ No container found: {container_name}")
        except Exception as e:
            cleanup_results.append(f"⚠ Container cleanup error: {str(e)}")
        
        try:
            image_check = self.runner.run([
                "docker", "images", "-q", image_name
            ], check=False)
            
            if image_check.stdout.strip():
                image_remove = self.runner.run([
                    "docker", "rmi", "-f", image_name
                ], check=False)
                
                if image_remove.returncode == 0:
                    cleanup_results.append(f"✓ Removed image: {image_name}")
                else:
                    cleanup_results.append(f"⚠ Image removal failed: {image_remove.stderr}")
            else:
                cleanup_results.append(f"ℹ No image found: {image_name}")
        except Exception as e:
            cleanup_results.append(f"⚠ Image cleanup error: {str(e)}")
        
        return cleanup_results 