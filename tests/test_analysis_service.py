import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, mock_open
from analysis_service import AnalysisService


@pytest.fixture
def mock_ctx():
    ctx = Mock()
    ctx.session = Mock()
    ctx.session.create_message = AsyncMock()
    return ctx


@pytest.fixture
def analysis_service(mock_ctx):
    return AnalysisService(mock_ctx)


class TestAnalysisService:
    
    @pytest.mark.asyncio
    async def test_analyze_repository_with_readme_and_files(self, analysis_service, mock_ctx):
        repo_path = Path("/fake/repo")
        repo_info = {
            "owner": "test-owner",
            "repo": "test-repo",
            "server_name": "test-server",
            "path": "src/server"
        }
        
        mock_response = Mock()
        mock_response.content.text = "This is a Python MCP server that does XYZ..."
        mock_ctx.session.create_message.return_value = mock_response
        
        with patch('pathlib.Path.exists') as mock_exists, \
             patch('pathlib.Path.is_file') as mock_is_file, \
             patch('pathlib.Path.read_text') as mock_read_text, \
             patch('os.walk') as mock_walk:
            
            mock_exists.return_value = True
            mock_is_file.return_value = True
            mock_read_text.return_value = "# Test Server\nThis is a test MCP server"
            
            mock_walk.return_value = [
                ("/fake/repo", ["src"], ["README.md", "main.py"]),
                ("/fake/repo/src", [], ["server.py", "utils.py"])
            ]
            
            with patch('builtins.open', mock_open(read_data="def main():\n    pass\n")) as mock_file:
                result = await analysis_service.analyze_repository(repo_path, repo_info)
        
        assert result["success"] is True
        assert "This is a Python MCP server" in result["analysis"]
        
        mock_ctx.session.create_message.assert_called_once()
        call_args = mock_ctx.session.create_message.call_args
        
        prompt = call_args[1]["messages"][0]["content"]["text"]
        assert "test-owner/test-repo" in prompt
        assert "test-server" in prompt
        assert "src/server" in prompt
        assert "FULL README CONTENT:" in prompt
        assert "# Test Server" in prompt
        assert "PROJECT FILE OVERVIEW:" in prompt
    
    @pytest.mark.asyncio
    async def test_analyze_repository_without_readme(self, analysis_service, mock_ctx):
        repo_path = Path("/fake/repo")
        repo_info = {
            "owner": "test-owner",
            "repo": "test-repo",
            "server_name": "test-server",
            "path": ""
        }
        
        mock_response = Mock()
        mock_response.content.text = "Analysis without README"
        mock_ctx.session.create_message.return_value = mock_response
        
        with patch('pathlib.Path.exists') as mock_exists, \
             patch('os.walk') as mock_walk:
            
            mock_exists.return_value = False
            
            mock_walk.return_value = [
                ("/fake/repo", [], ["main.py", "config.json"])
            ]
            
            with patch('builtins.open', mock_open(read_data="print('hello')\n")) as mock_file:
                result = await analysis_service.analyze_repository(repo_path, repo_info)
        
        assert result["success"] is True
        assert "Analysis without README" in result["analysis"]
        
        call_args = mock_ctx.session.create_message.call_args
        prompt = call_args[1]["messages"][0]["content"]["text"]
        assert "FULL README CONTENT:" not in prompt
        assert "PROJECT FILE OVERVIEW:" in prompt
    
    @pytest.mark.asyncio
    async def test_analyze_repository_filters_excluded_directories(self, analysis_service, mock_ctx):
        repo_path = Path("/fake/repo")
        repo_info = {
            "owner": "test-owner",
            "repo": "test-repo", 
            "server_name": "test-server",
            "path": ""
        }
        
        mock_response = Mock()
        mock_response.content.text = "Filtered analysis"
        mock_ctx.session.create_message.return_value = mock_response
        
        with patch('pathlib.Path.exists') as mock_exists, \
             patch('os.walk') as mock_walk:
            
            mock_exists.return_value = False
            
            dirs_list = ["src", "node_modules", ".git", "__pycache__", "dist"]
            mock_walk.return_value = [
                ("/fake/repo", dirs_list, ["main.py"])
            ]
            
            with patch('builtins.open', mock_open(read_data="code content")) as mock_file:
                result = await analysis_service.analyze_repository(repo_path, repo_info)
        
        assert result["success"] is True
        
        mock_walk.assert_called_once_with(repo_path)
        dirs_passed = mock_walk.return_value[0][1]
        assert "src" in dirs_passed
        assert "node_modules" not in dirs_passed
        assert ".git" not in dirs_passed
        assert "__pycache__" not in dirs_passed
        assert "dist" not in dirs_passed
    
    @pytest.mark.asyncio 
    async def test_analyze_repository_limits_file_count(self, analysis_service, mock_ctx):
        repo_path = Path("/fake/repo")
        repo_info = {
            "owner": "test-owner",
            "repo": "test-repo",
            "server_name": "test-server", 
            "path": ""
        }
        
        mock_response = Mock()
        mock_response.content.text = "Limited file analysis"
        mock_ctx.session.create_message.return_value = mock_response
        
        with patch('pathlib.Path.exists') as mock_exists, \
             patch('os.walk') as mock_walk:
            
            mock_exists.return_value = False
            
            many_files = [f"file{i}.py" for i in range(25)]
            mock_walk.return_value = [
                ("/fake/repo", [], many_files)
            ]
            
            with patch('builtins.open', mock_open(read_data="def func():\n    pass")) as mock_file:
                result = await analysis_service.analyze_repository(repo_path, repo_info)
        
        assert result["success"] is True
        
        call_args = mock_ctx.session.create_message.call_args
        prompt = call_args[1]["messages"][0]["content"]["text"]
        
        file_entries = prompt.count("--- file")
        assert file_entries <= 20
    
    @pytest.mark.asyncio
    async def test_analyze_repository_handles_exception(self, analysis_service, mock_ctx):
        repo_path = Path("/fake/repo")
        repo_info = {
            "owner": "test-owner",
            "repo": "test-repo",
            "server_name": "test-server",
            "path": ""
        }
        
        mock_ctx.session.create_message.side_effect = Exception("LLM call failed")
        
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = False
            
            result = await analysis_service.analyze_repository(repo_path, repo_info)
        
        assert result["success"] is False
        assert "LLM call failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_create_docker_plan_with_existing_dockerfile(self, analysis_service, mock_ctx):
        repo_path = Path("/fake/repo")
        analysis = "This is a Python FastAPI server"
        server_name = "test-server"
        
        mock_response = Mock()
        mock_response.content.text = """{"has_existing_dockerfile": true, "image_name": "test-image", "container_name": "test-container", "ports": {"8000": "8000"}, "dockerfile_content": "FROM python:3.11"}"""
        mock_ctx.session.create_message.return_value = mock_response
        
        with patch('pathlib.Path.exists') as mock_exists, \
             patch('pathlib.Path.read_text') as mock_read_text:
            
            mock_exists.return_value = True
            mock_read_text.return_value = "FROM python:3.11\nCOPY . .\nRUN pip install -r requirements.txt"
            
            with patch('docker_service.DockerService.parse_plan') as mock_parse:
                mock_parse.return_value = {"success": True, "plan": {"dockerfile_content": "FROM python:3.11"}}
                
                result = await analysis_service.create_docker_plan(repo_path, analysis, server_name)
        
        assert result["success"] is True
        
        mock_ctx.session.create_message.assert_called_once()
        call_args = mock_ctx.session.create_message.call_args
        
        prompt = call_args[1]["messages"][0]["content"]["text"]
        assert "already has a Dockerfile" in prompt
        assert "EXISTING DOCKERFILE:" in prompt
        assert "FROM python:3.11" in prompt
        assert "PREVIOUS ANALYSIS:" in prompt
        assert analysis in prompt
    
    @pytest.mark.asyncio
    async def test_create_docker_plan_without_existing_dockerfile(self, analysis_service, mock_ctx):
        repo_path = Path("/fake/repo")
        analysis = "This is a Node.js Express server"
        server_name = "test-server"
        
        mock_response = Mock()
        mock_response.content.text = """{"has_existing_dockerfile": false, "image_name": "node-server", "container_name": "node-container", "ports": {"3000": "3000"}, "dockerfile_content": "FROM node:18"}"""
        mock_ctx.session.create_message.return_value = mock_response
        
        with patch('pathlib.Path.exists') as mock_exists:
            
            mock_exists.return_value = False
            
            with patch('docker_service.DockerService.parse_plan') as mock_parse:
                mock_parse.return_value = {"success": True, "plan": {"dockerfile_content": "FROM node:18"}}
                
                result = await analysis_service.create_docker_plan(repo_path, analysis, server_name)
        
        assert result["success"] is True
        
        mock_ctx.session.create_message.assert_called_once()
        call_args = mock_ctx.session.create_message.call_args
        
        prompt = call_args[1]["messages"][0]["content"]["text"]
        assert "needs a Dockerfile created" in prompt
        assert "EXISTING DOCKERFILE:" not in prompt
        assert "PREVIOUS ANALYSIS:" in prompt
        assert analysis in prompt
    
    @pytest.mark.asyncio
    async def test_create_docker_plan_with_json_in_markdown(self, analysis_service, mock_ctx):
        repo_path = Path("/fake/repo")
        analysis = "This is a Go server"
        server_name = "test-server"
        
        mock_response = Mock()
        mock_response.content.text = """```json
        {"has_existing_dockerfile": false, "image_name": "go-server", "container_name": "go-container", "ports": {"8080": "8080"}, "dockerfile_content": "FROM golang:1.21"}
        ```"""
        mock_ctx.session.create_message.return_value = mock_response
        
        with patch('pathlib.Path.exists') as mock_exists:
            
            mock_exists.return_value = False
            
            with patch('docker_service.DockerService.parse_plan') as mock_parse:
                mock_parse.return_value = {"success": True, "plan": {"dockerfile_content": "FROM golang:1.21"}}
                
                result = await analysis_service.create_docker_plan(repo_path, analysis, server_name)
        
        assert result["success"] is True
        mock_parse.assert_called_once()
        
        parse_call_args = mock_parse.call_args[0]
        assert '{"has_existing_dockerfile": false' in parse_call_args[0]
    
    @pytest.mark.asyncio
    async def test_create_docker_plan_handles_exception(self, analysis_service, mock_ctx):
        repo_path = Path("/fake/repo")
        analysis = "This is a test server"
        server_name = "test-server"
        
        mock_ctx.session.create_message.side_effect = Exception("Docker planning failed")
        
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = False
            
            result = await analysis_service.create_docker_plan(repo_path, analysis, server_name)
        
        assert result["success"] is False
        assert "Docker planning failed" in result["error"] 