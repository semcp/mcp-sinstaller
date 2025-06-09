import pytest
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from server_manager import ServerManager
from process_runner import MockCommandRunner


@pytest.fixture
def mock_runner():
    return MockCommandRunner()


@pytest.fixture
def servers_dir(tmp_path):
    return tmp_path / "servers"


@pytest.fixture
def server_manager(servers_dir, mock_runner):
    return ServerManager(servers_dir, mock_runner)


@pytest.fixture
def mock_ctx():
    ctx = Mock()
    ctx.session = Mock()
    ctx.session.create_message = AsyncMock()
    return ctx


class TestServerManager:
    
    @pytest.mark.asyncio
    async def test_install_happy_path(self, server_manager, mock_ctx, servers_dir):
        url = "https://github.com/owner/repo/tree/main/src/server"
        
        mock_analysis_response = Mock()
        mock_analysis_response.content.text = "This is a Python FastAPI MCP server"
        
        mock_docker_response = Mock()
        mock_docker_response.content.text = '{"dockerfile_content": "FROM python:3.11", "image_name": "test-image", "container_name": "test-container", "ports": {"8000": "8000"}, "has_existing_dockerfile": false}'
        
        mock_ctx.session.create_message.side_effect = [mock_analysis_response, mock_docker_response]
        
        with patch.object(server_manager.github_service, 'clone') as mock_clone, \
             patch.object(server_manager.docker_service, 'build_from_plan') as mock_build, \
             patch('docker_service.DockerService.parse_plan') as mock_parse, \
             patch('pathlib.Path.exists') as mock_exists:
            
            mock_exists.return_value = False
            mock_parse.return_value = {
                "success": True, 
                "plan": {
                    "dockerfile_content": "FROM python:3.11",
                    "image_name": "test-image",
                    "container_name": "test-container", 
                    "ports": {"8000": "8000"},
                    "has_existing_dockerfile": False
                }
            }
            mock_build.return_value = {
                "success": True,
                "image_name": "test-image",
                "build_output": "Successfully built"
            }
            
            result = await server_manager.install(url, force=False, ctx=mock_ctx)
        
        assert result["success"] is True
        assert result["server_name"] == "owner-repo-server"
        assert result["url"] == url
        assert "dockerfile_status" in result
        assert "Using existing Dockerfile" in result["dockerfile_status"] or "Generated new Dockerfile" in result["dockerfile_status"]
        
        mock_clone.assert_called_once()
        mock_build.assert_called_once()
        assert mock_ctx.session.create_message.call_count == 2
    
    @pytest.mark.asyncio
    async def test_install_server_already_exists_no_force(self, server_manager, mock_ctx, servers_dir):
        url = "https://github.com/owner/repo"
        server_dir = servers_dir / "owner-repo"
        server_dir.mkdir(parents=True)
        
        result = await server_manager.install(url, force=False, ctx=mock_ctx)
        
        assert result["success"] is False
        assert "already exists" in result["error"]
        assert "force=true" in result["error"]
    
    @pytest.mark.asyncio
    async def test_install_server_exists_with_force(self, server_manager, mock_ctx, servers_dir):
        url = "https://github.com/owner/repo"
        server_dir = servers_dir / "owner-repo"
        server_dir.mkdir(parents=True)
        (server_dir / "old_file.txt").write_text("old content")
        
        mock_analysis_response = Mock()
        mock_analysis_response.content.text = "Python server analysis"
        
        mock_docker_response = Mock()
        mock_docker_response.content.text = '{"dockerfile_content": "FROM python:3.11", "image_name": "repo-image", "container_name": "repo-container", "ports": {"8000": "8000"}, "has_existing_dockerfile": false}'
        
        mock_ctx.session.create_message.side_effect = [mock_analysis_response, mock_docker_response]
        
        with patch.object(server_manager.github_service, 'clone') as mock_clone, \
             patch.object(server_manager.docker_service, 'build_from_plan') as mock_build, \
             patch('docker_service.DockerService.parse_plan') as mock_parse, \
             patch('shutil.rmtree') as mock_rmtree:
            
            mock_parse.return_value = {
                "success": True,
                "plan": {
                    "dockerfile_content": "FROM python:3.11",
                    "image_name": "repo-image",
                    "container_name": "repo-container",
                    "ports": {"8000": "8000"},
                    "has_existing_dockerfile": False
                }
            }
            mock_build.return_value = {
                "success": True,
                "image_name": "repo-image",
                "build_output": "Successfully built"
            }
            
            result = await server_manager.install(url, force=True, ctx=mock_ctx)
        
        assert result["success"] is True
        mock_rmtree.assert_called_once_with(server_dir)
        mock_clone.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_install_clone_failure(self, server_manager, mock_ctx, servers_dir):
        url = "https://github.com/owner/repo"
        
        with patch.object(server_manager.github_service, 'clone') as mock_clone:
            mock_clone.side_effect = Exception("Git clone failed")
            
            result = await server_manager.install(url, force=False, ctx=mock_ctx)
        
        assert result["success"] is False
        assert "Git clone failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_install_no_context_provided(self, server_manager, servers_dir):
        url = "https://github.com/owner/repo"
        
        with patch.object(server_manager.github_service, 'clone'):
            result = await server_manager.install(url, force=False, ctx=None)
        
        assert result["success"] is False
        assert "No request context available" in result["error"]
    
    @pytest.mark.asyncio
    async def test_install_analysis_failure(self, server_manager, mock_ctx, servers_dir):
        url = "https://github.com/owner/repo"
        
        mock_ctx.session.create_message.side_effect = Exception("Analysis failed")
        
        with patch.object(server_manager.github_service, 'clone') as mock_clone:
            result = await server_manager.install(url, force=False, ctx=mock_ctx)
        
        assert result["success"] is False
        assert "Analysis failed" in result["error"]
        mock_clone.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_install_docker_plan_failure(self, server_manager, mock_ctx, servers_dir):
        url = "https://github.com/owner/repo"
        
        mock_analysis_response = Mock()
        mock_analysis_response.content.text = "Analysis successful"
        
        mock_docker_response = Mock()
        mock_docker_response.content.text = "invalid json"
        
        mock_ctx.session.create_message.side_effect = [mock_analysis_response, mock_docker_response]
        
        with patch.object(server_manager.github_service, 'clone') as mock_clone, \
             patch('docker_service.DockerService.parse_plan') as mock_parse:
            
            mock_parse.return_value = {
                "success": False,
                "error": "Invalid JSON in Docker plan"
            }
            
            result = await server_manager.install(url, force=False, ctx=mock_ctx)
        
        assert result["success"] is False
        assert "Invalid JSON in Docker plan" in result["error"]
        mock_clone.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_install_docker_build_failure(self, server_manager, mock_ctx, servers_dir):
        url = "https://github.com/owner/repo"
        
        mock_analysis_response = Mock()
        mock_analysis_response.content.text = "Analysis successful"
        
        mock_docker_response = Mock()
        mock_docker_response.content.text = '{"dockerfile_content": "FROM python:3.11", "image_name": "fail-image", "container_name": "fail-container", "ports": {"8000": "8000"}, "has_existing_dockerfile": false}'
        
        mock_ctx.session.create_message.side_effect = [mock_analysis_response, mock_docker_response]
        
        with patch.object(server_manager.github_service, 'clone') as mock_clone, \
             patch.object(server_manager.docker_service, 'build_from_plan') as mock_build, \
             patch('docker_service.DockerService.parse_plan') as mock_parse:
            
            mock_parse.return_value = {
                "success": True,
                "plan": {
                    "dockerfile_content": "FROM python:3.11",
                    "image_name": "fail-image",
                    "container_name": "fail-container",
                    "ports": {"8000": "8000"},
                    "has_existing_dockerfile": False
                }
            }
            mock_build.return_value = {
                "success": False,
                "error": "Docker build failed",
                "docker_stderr": "Missing dependency"
            }
            
            result = await server_manager.install(url, force=False, ctx=mock_ctx)
        
        assert result["success"] is False
        assert "Docker build failed" in result["error"]
        mock_clone.assert_called_once()
        mock_build.assert_called_once()
    
    def test_update_server_not_found(self, server_manager, servers_dir):
        result = server_manager.update("nonexistent-server")
        
        assert result["success"] is False
        assert "not found" in result["error"]
    
    def test_update_missing_metadata(self, server_manager, servers_dir):
        server_dir = servers_dir / "test-server"
        server_dir.mkdir(parents=True)
        
        result = server_manager.update("test-server")
        
        assert result["success"] is False
        assert "missing metadata" in result["error"]
    
    def test_update_success(self, server_manager, servers_dir):
        server_dir = servers_dir / "test-server"
        server_dir.mkdir(parents=True)
        
        metadata = {
            "image_name": "test-image",
            "container_name": "test-container"
        }
        
        metadata_path = server_dir / "metadata.json"
        metadata_path.write_text('{"image_name": "test-image", "container_name": "test-container"}')
        
        with patch.object(server_manager.github_service, 'pull') as mock_pull, \
             patch.object(server_manager.docker_service, 'update_server') as mock_update:
            
            mock_update.return_value = {
                "success": True,
                "metadata": metadata,
                "build_output": "Updated successfully"
            }
            
            result = server_manager.update("test-server")
        
        assert result["success"] is True
        assert result["server_name"] == "test-server"
        mock_pull.assert_called_once_with(server_dir)
        mock_update.assert_called_once()
    
    def test_delete_server_not_found(self, server_manager, servers_dir):
        result = server_manager.delete("nonexistent-server")
        
        assert result["success"] is False
        assert "not found" in result["error"]
    
    def test_delete_success_with_metadata(self, server_manager, servers_dir):
        server_dir = servers_dir / "test-server"
        server_dir.mkdir(parents=True)
        
        metadata_path = server_dir / "metadata.json"
        metadata_path.write_text('{"image_name": "test-image", "container_name": "test-container"}')
        
        with patch.object(server_manager.docker_service, 'cleanup_server') as mock_cleanup, \
             patch('shutil.rmtree') as mock_rmtree:
            
            mock_cleanup.return_value = ["✓ Removed container: test-container", "✓ Removed image: test-image"]
            
            result = server_manager.delete("test-server")
        
        assert result["success"] is True
        assert result["server_name"] == "test-server"
        assert len(result["cleanup_results"]) == 3
        mock_cleanup.assert_called_once()
        mock_rmtree.assert_called_once_with(server_dir)
    
    def test_delete_success_without_metadata(self, server_manager, servers_dir):
        server_dir = servers_dir / "test-server"
        server_dir.mkdir(parents=True)
        
        with patch.object(server_manager.docker_service, 'cleanup_server') as mock_cleanup, \
             patch('shutil.rmtree') as mock_rmtree:
            
            mock_cleanup.return_value = ["ℹ No container found", "ℹ No image found"]
            
            result = server_manager.delete("test-server")
        
        assert result["success"] is True
        mock_cleanup.assert_called_once_with({}, "test-server")
        mock_rmtree.assert_called_once_with(server_dir)
    
    def test_list_no_servers(self, server_manager, servers_dir):
        result = server_manager.list()
        
        assert result["success"] is True
        assert result["servers"] == []
        assert "No MCP servers installed" in result["message"]
    
    def test_list_with_servers(self, server_manager, servers_dir):
        servers_dir.mkdir(parents=True)
        
        server1_dir = servers_dir / "server1"
        server1_dir.mkdir()
        
        metadata1 = {
            "server_name": "server1",
            "transport_type": "stdio",
            "ports": {},
            "required_secrets": [],
            "created_at": "2024-01-01T00:00:00"
        }
        
        (server1_dir / "metadata.json").write_text('{"server_name": "server1", "transport_type": "stdio", "ports": {}, "required_secrets": [], "created_at": "2024-01-01T00:00:00"}')
        
        server2_dir = servers_dir / "server2"
        server2_dir.mkdir()
        
        # Mock the git command that list() calls
        with patch.object(server_manager.runner, 'run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="https://github.com/test/repo.git\n")
            result = server_manager.list()
        
        assert result["success"] is True
        assert len(result["servers"]) == 2
        
        server1_info = next((s for s in result["servers"] if s["name"] == "server1"), None)
        assert server1_info is not None
        assert server1_info["transport"] == "STDIO"
        
        server2_info = next((s for s in result["servers"] if s["name"] == "server2"), None)
        assert server2_info is not None
        assert server2_info["status"] == "ERROR"
        assert "Missing metadata.json" in server2_info["error"] 