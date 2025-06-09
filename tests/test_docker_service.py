import pytest
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch
from docker_service import DockerService
from process_runner import MockCommandRunner


class TestDockerService:
    
    def test_parse_plan_valid_json(self):
        server_name = "test-server"
        valid_json = json.dumps({
            "dockerfile_content": "FROM python:3.11\nCOPY . .\nRUN pip install -r requirements.txt",
            "image_name": "test-image",
            "container_name": "test-container",
            "ports": {"8000": "8000"}
        })
        
        result = DockerService.parse_plan(valid_json, server_name)
        
        assert result["success"] is True
        plan = result["plan"]
        assert plan["dockerfile_content"] == "FROM python:3.11\nCOPY . .\nRUN pip install -r requirements.txt"
        assert plan["image_name"] == "test-image"
        assert plan["container_name"] == "test-container"
        assert plan["ports"] == {"8000": "8000"}
        assert plan["environment_variables"] == {}
        assert plan["required_secrets"] == []
        assert plan["volumes"] == {}
        assert plan["startup_command"] is None
        assert plan["health_check"] is None
        assert plan["has_existing_dockerfile"] is False
    
    def test_parse_plan_json_in_markdown(self):
        server_name = "test-server"
        json_in_markdown = """```json
{
    "dockerfile_content": "FROM node:18",
    "image_name": "node-server",
    "container_name": "node-container",
    "ports": {"3000": "3000"}
}
```"""
        
        result = DockerService.parse_plan(json_in_markdown, server_name)
        
        assert result["success"] is True
        plan = result["plan"]
        assert plan["dockerfile_content"] == "FROM node:18"
        assert plan["image_name"] == "node-server"
        assert plan["container_name"] == "node-container"
        assert plan["ports"] == {"3000": "3000"}
    
    def test_parse_plan_malformed_json(self):
        server_name = "test-server"
        malformed_json = "{ invalid json content"
        
        result = DockerService.parse_plan(malformed_json, server_name)
        
        assert result["success"] is False
        assert "Invalid JSON in Docker plan" in result["error"]
        assert "raw_response" in result
    
    def test_parse_plan_missing_required_fields(self):
        server_name = "test-server"
        incomplete_json = json.dumps({
            "dockerfile_content": "FROM python:3.11",
            "image_name": "test-image"
        })
        
        result = DockerService.parse_plan(incomplete_json, server_name)
        
        assert result["success"] is False
        assert "Missing required field in Docker plan" in result["error"]
        assert "container_name" in result["error"] or "ports" in result["error"]
    
    def test_parse_plan_invalid_ports_format(self):
        server_name = "test-server"
        invalid_ports_json = json.dumps({
            "dockerfile_content": "FROM python:3.11",
            "image_name": "test-image",
            "container_name": "test-container",
            "ports": ["8000", "3000"]
        })
        
        result = DockerService.parse_plan(invalid_ports_json, server_name)
        
        assert result["success"] is False
        assert "Ports must be a dictionary" in result["error"]
    
    @patch('pathlib.Path.write_text')
    @patch('pathlib.Path.exists')
    @patch('builtins.open')
    def test_build_from_plan_new_dockerfile_success(self, mock_open, mock_exists, mock_write_text):
        mock_runner = MockCommandRunner(expected_stdout="Successfully built abc123")
        docker_service = DockerService(mock_runner)
        
        plan = {
            "dockerfile_content": "FROM python:3.11\nCOPY . .\n",
            "image_name": "test-image",
            "container_name": "test-container",
            "ports": {"8000": "8000"},
            "environment_variables": {"ENV_VAR": "value"},
            "required_secrets": ["API_KEY"],
            "has_existing_dockerfile": False
        }
        
        repo_path = Path("/tmp/test-repo")
        server_name = "test-server"
        
        mock_exists.return_value = False
        mock_open.return_value.__enter__.return_value.write = Mock()
        
        result = docker_service.build_from_plan(plan, repo_path, server_name)
        
        assert result["success"] is True
        assert result["image_name"] == "test-image"
        assert result["environment_variables"] == ["ENV_VAR"]
        assert result["required_secrets"] == ["API_KEY"]
        
        mock_write_text.assert_called_once_with("FROM python:3.11\nCOPY . .\n")
        
        build_command = ["docker", "build", "-t", "test-image", str(repo_path)]
        assert build_command in mock_runner.commands_run
    
    @patch('pathlib.Path.write_text')
    @patch('pathlib.Path.exists')
    @patch('builtins.open')
    def test_build_from_plan_existing_dockerfile_success(self, mock_open, mock_exists, mock_write_text):
        mock_runner = MockCommandRunner(expected_stdout="Successfully built def456")
        docker_service = DockerService(mock_runner)
        
        plan = {
            "dockerfile_content": "FROM python:3.11\nCOPY . .\n",
            "image_name": "existing-image",
            "container_name": "existing-container",
            "ports": {"5000": "5000"},
            "environment_variables": {},
            "required_secrets": [],
            "has_existing_dockerfile": True
        }
        
        repo_path = Path("/tmp/test-repo")
        server_name = "test-server"
        
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.write = Mock()
        
        result = docker_service.build_from_plan(plan, repo_path, server_name)
        
        assert result["success"] is True
        assert result["image_name"] == "existing-image"
        
        mock_write_text.assert_not_called()
        
        build_command = ["docker", "build", "-t", "existing-image", str(repo_path)]
        assert build_command in mock_runner.commands_run
    
    @patch('pathlib.Path.write_text')
    @patch('pathlib.Path.exists')
    @patch('builtins.open')
    def test_build_from_plan_build_failure(self, mock_open, mock_exists, mock_write_text):
        mock_runner = Mock()
        
        # Mock different responses for different commands
        def mock_run_side_effect(command, **kwargs):
            if command[0] == "date":
                return Mock(stdout="2024-01-01T00:00:00Z", returncode=0)
            elif command[0] == "docker" and command[1] == "build":
                return Mock(stdout="", stderr="Build failed: missing dependency", returncode=1)
            else:
                return Mock(stdout="", returncode=0)
        
        mock_runner.run = Mock(side_effect=mock_run_side_effect)
        docker_service = DockerService(mock_runner)
        
        plan = {
            "dockerfile_content": "FROM python:3.11\nCOPY . .\n",
            "image_name": "fail-image",
            "container_name": "fail-container",
            "ports": {"8000": "8000"},
            "environment_variables": {},
            "required_secrets": [],
            "has_existing_dockerfile": False
        }
        
        repo_path = Path("/tmp/test-repo")
        server_name = "test-server"
        
        mock_exists.return_value = False
        mock_open.return_value.__enter__.return_value.write = Mock()
        
        result = docker_service.build_from_plan(plan, repo_path, server_name)
        
        assert result["success"] is False
        assert result["error"] == "Docker build failed"
        assert result["docker_stderr"] == "Build failed: missing dependency"
        assert result["return_code"] == 1
    
    def test_cleanup_server_full_cleanup(self):
        mock_runner = MockCommandRunner()
        mock_runner.expected_stdout = "container123"
        
        responses = [
            Mock(stdout="container123", returncode=0),
            Mock(returncode=0), 
            Mock(returncode=0),
            Mock(stdout="image123", returncode=0),
            Mock(returncode=0)
        ]
        
        mock_runner.run = Mock(side_effect=responses)
        docker_service = DockerService(mock_runner)
        
        metadata = {
            "container_name": "test-container",
            "image_name": "test-image"
        }
        server_name = "test-server"
        
        results = docker_service.cleanup_server(metadata, server_name)
        
        assert len(results) == 2
        assert "✓ Removed container: test-container" in results
        assert "✓ Removed image: test-image" in results
        
        expected_calls = [
            ["docker", "ps", "-a", "--filter", "name=test-container", "--format", "{{.ID}}"],
            ["docker", "stop", "test-container"],
            ["docker", "rm", "test-container"],
            ["docker", "images", "-q", "test-image"],
            ["docker", "rmi", "-f", "test-image"]
        ]
        
        actual_calls = [call[0][0] for call in mock_runner.run.call_args_list]
        for expected_call in expected_calls:
            assert expected_call in actual_calls
    
    def test_cleanup_server_no_artifacts(self):
        mock_runner = MockCommandRunner()
        
        responses = [
            Mock(stdout="", returncode=0),
            Mock(stdout="", returncode=0)
        ]
        
        mock_runner.run = Mock(side_effect=responses)
        docker_service = DockerService(mock_runner)
        
        metadata = {
            "container_name": "nonexistent-container",
            "image_name": "nonexistent-image"
        }
        server_name = "test-server"
        
        results = docker_service.cleanup_server(metadata, server_name)
        
        assert len(results) == 2
        assert "No container found: nonexistent-container" in results[0]
        assert "No image found: nonexistent-image" in results[1]
    
    def test_cleanup_server_partial_failure(self):
        mock_runner = MockCommandRunner()
        
        responses = [
            Mock(stdout="container123", returncode=0),
            Mock(returncode=0),
            Mock(returncode=1, stderr="Container removal failed"),
            Mock(stdout="image123", returncode=0),
            Mock(returncode=0)
        ]
        
        mock_runner.run = Mock(side_effect=responses)
        docker_service = DockerService(mock_runner)
        
        metadata = {
            "container_name": "problem-container",
            "image_name": "good-image"
        }
        server_name = "test-server"
        
        results = docker_service.cleanup_server(metadata, server_name)
        
        assert len(results) == 2
        assert "Container removal failed: Container removal failed" in results[0]
        assert "Removed image: good-image" in results[1] 