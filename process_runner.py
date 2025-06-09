import subprocess
from typing import List, Optional

class CommandRunner:
    """A wrapper for running external shell commands."""
    
    def run(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("text", True)
        kwargs.setdefault("check", True)
        return subprocess.run(command, **kwargs)

class MockCommandRunner:
    """Mock command runner for testing purposes."""
    
    def __init__(self, expected_stdout: str = "", expected_stderr: str = "", return_code: int = 0):
        self.expected_stdout = expected_stdout
        self.expected_stderr = expected_stderr
        self.return_code = return_code
        self.commands_run = []

    def run(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        self.commands_run.append(command)
        
        if kwargs.get("check", True) and self.return_code != 0:
            raise subprocess.CalledProcessError(
                self.return_code, 
                command, 
                output=self.expected_stdout, 
                stderr=self.expected_stderr
            )
        
        return subprocess.CompletedProcess(
            args=command,
            stdout=self.expected_stdout,
            stderr=self.expected_stderr,
            returncode=self.return_code,
        ) 