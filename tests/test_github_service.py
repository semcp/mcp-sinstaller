import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch
from github_service import GitHubService
from process_runner import MockCommandRunner


class TestGitHubService:
    
    # URL Parsing Tests (comprehensive coverage)
    def test_parse_url_main_branch_with_path(self):
        """Test parsing URL with main branch and path"""
        url = "https://github.com/modelcontextprotocol/servers/tree/main/src/fetch"
        result = GitHubService.parse_url(url)
        
        assert result["owner"] == "modelcontextprotocol"
        assert result["repo"] == "servers"
        assert result["branch"] == "main"
        assert result["path"] == "src/fetch"
        assert result["server_name"] == "modelcontextprotocol-servers-fetch"
        assert result["clone_url"] == "https://github.com/modelcontextprotocol/servers.git"

    def test_parse_url_custom_branch_with_path(self):
        """Test parsing URL with custom branch and path"""
        url = "https://github.com/modelcontextprotocol/servers/tree/typescript-servers-0.6.2/src/fetch"
        result = GitHubService.parse_url(url)
        
        assert result["owner"] == "modelcontextprotocol"
        assert result["repo"] == "servers"
        assert result["branch"] == "typescript-servers-0.6.2"
        assert result["path"] == "src/fetch"
        assert result["server_name"] == "modelcontextprotocol-servers-fetch"
        assert result["clone_url"] == "https://github.com/modelcontextprotocol/servers.git"

    def test_parse_url_root_repository(self):
        """Test parsing root repository URL"""
        url = "https://github.com/github/github-mcp-server"
        result = GitHubService.parse_url(url)
        
        assert result["owner"] == "github"
        assert result["repo"] == "github-mcp-server"
        assert result["branch"] == "main"
        assert result["path"] == ""
        assert result["server_name"] == "github-github-mcp-server"
        assert result["clone_url"] == "https://github.com/github/github-mcp-server.git"

    def test_parse_url_root_repository_with_trailing_slash(self):
        """Test parsing root repository URL with trailing slash"""
        url = "https://github.com/github/github-mcp-server/"
        result = GitHubService.parse_url(url)
        
        assert result["owner"] == "github"
        assert result["repo"] == "github-mcp-server"
        assert result["branch"] == "main"
        assert result["path"] == ""
        assert result["server_name"] == "github-github-mcp-server"

    def test_parse_url_blob_url(self):
        """Test parsing blob URL (should work with same pattern)"""
        url = "https://github.com/owner/repo/blob/main/src/server.py"
        result = GitHubService.parse_url(url)
        
        assert result["owner"] == "owner"
        assert result["repo"] == "repo"
        assert result["branch"] == "main"
        assert result["path"] == "src/server.py"
        assert result["server_name"] == "owner-repo-server.py"

    def test_parse_url_deep_path(self):
        """Test parsing URL with deep path structure"""
        url = "https://github.com/owner/repo/tree/main/src/servers/fetch"
        result = GitHubService.parse_url(url)
        
        assert result["path"] == "src/servers/fetch"
        assert result["server_name"] == "owner-repo-fetch"

    def test_parse_url_invalid_url_format(self):
        """Test that invalid URLs raise ValueError"""
        invalid_urls = [
            "https://gitlab.com/owner/repo",
            "https://github.com",
            "https://github.com/owner",
            "not-a-url",
            ""
        ]
        
        for invalid_url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid GitHub URL format"):
                GitHubService.parse_url(invalid_url)

    @pytest.mark.parametrize("url,expected_name", [
        ("https://github.com/owner/repo/tree/main/src/fetch", "owner-repo-fetch"),
        ("https://github.com/owner/repo/tree/main/servers/database", "owner-repo-database"),
        ("https://github.com/owner/simple-server", "owner-simple-server"),
        ("https://github.com/owner/repo/tree/main/complex-name-server", "owner-repo-complex-name-server"),
    ])
    def test_parse_url_server_name_extraction(self, url, expected_name):
        """Test server name extraction from various URL patterns"""
        result = GitHubService.parse_url(url)
        assert result["server_name"] == expected_name
    
    # Git Operations Tests
    
    def test_clone_success(self):
        mock_runner = MockCommandRunner()
        github_service = GitHubService(mock_runner)
        
        clone_url = "https://github.com/owner/repo.git"
        target_dir = Path("/tmp/test-repo")
        branch = "main"
        
        github_service.clone(clone_url, target_dir, branch)
        
        expected_command = ["git", "clone", "--branch", "main", clone_url, str(target_dir)]
        assert mock_runner.commands_run == [expected_command]
    
    def test_clone_with_custom_branch(self):
        mock_runner = MockCommandRunner()
        github_service = GitHubService(mock_runner)
        
        clone_url = "https://github.com/owner/repo.git"
        target_dir = Path("/tmp/test-repo")
        branch = "feature-branch"
        
        github_service.clone(clone_url, target_dir, branch)
        
        expected_command = ["git", "clone", "--branch", "feature-branch", clone_url, str(target_dir)]
        assert mock_runner.commands_run == [expected_command]
    
    def test_clone_failure_propagates_exception(self):
        mock_runner = MockCommandRunner(return_code=1, expected_stderr="Clone failed")
        github_service = GitHubService(mock_runner)
        
        clone_url = "https://github.com/owner/repo.git"
        target_dir = Path("/tmp/test-repo")
        branch = "main"
        
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            github_service.clone(clone_url, target_dir, branch)
        
        assert exc_info.value.returncode == 1
        assert "Clone failed" in str(exc_info.value.stderr)
    
    def test_pull_success(self):
        mock_runner = MockCommandRunner()
        github_service = GitHubService(mock_runner)
        
        repo_dir = Path("/tmp/test-repo")
        
        github_service.pull(repo_dir)
        
        expected_command = ["git", "pull"]
        assert mock_runner.commands_run == [expected_command]
    
    def test_pull_with_correct_cwd(self):
        mock_runner = Mock()
        mock_runner.run = Mock()
        github_service = GitHubService(mock_runner)
        
        repo_dir = Path("/tmp/test-repo")
        
        github_service.pull(repo_dir)
        
        mock_runner.run.assert_called_once_with(["git", "pull"], cwd=str(repo_dir))
    
    def test_pull_failure_propagates_exception(self):
        mock_runner = MockCommandRunner(return_code=1, expected_stderr="Pull failed")
        github_service = GitHubService(mock_runner)
        
        repo_dir = Path("/tmp/test-repo")
        
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            github_service.pull(repo_dir)
        
        assert exc_info.value.returncode == 1
        assert "Pull failed" in str(exc_info.value.stderr) 