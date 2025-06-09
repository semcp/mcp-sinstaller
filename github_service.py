import re
from pathlib import Path
from typing import Dict
from process_runner import CommandRunner

class GitHubService:
    """Service for GitHub repository operations."""
    
    def __init__(self, runner: CommandRunner):
        self.runner = runner
    
    @staticmethod
    def parse_url(url: str) -> Dict[str, str]:
        """Parse GitHub URL to extract repo info and server path"""
        
        github_patterns = [
            r'https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)',
            r'https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)', 
            r'https://github\.com/([^/]+)/([^/]+)/?$'
        ]
        
        for pattern in github_patterns:
            match = re.match(pattern, url)
            if match:
                if len(match.groups()) == 4:
                    owner, repo, branch, path = match.groups()
                    path_name = Path(path).name
                    server_name = f"{owner}-{repo}-{path_name}"
                else:
                    owner, repo = match.groups()
                    branch = "main"
                    path = ""
                    server_name = f"{owner}-{repo}"
                    
                return {
                    "owner": owner,
                    "repo": repo, 
                    "branch": branch,
                    "path": path,
                    "server_name": server_name,
                    "clone_url": f"https://github.com/{owner}/{repo}.git"
                }
        
        raise ValueError(f"Invalid GitHub URL format: {url}")
    
    def clone(self, clone_url: str, target_dir: Path, branch: str):
        """Clone a GitHub repository to the target directory"""
        self.runner.run([
            "git", "clone", "--branch", branch,
            clone_url, str(target_dir)
        ])
    
    def pull(self, repo_dir: Path):
        """Pull latest changes from the repository"""
        self.runner.run(["git", "pull"], cwd=str(repo_dir)) 