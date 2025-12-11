import os
import subprocess
import shlex
from typing import List, Dict, Any
from utils.path_mapper import PathMapper
from config import settings

class AgentTools:
    def __init__(self, path_mapper: PathMapper):
        self.path_mapper = path_mapper

    def list_dir(self, path: str = ".") -> str:
        try:
            real_path = self.path_mapper.to_real_path(path)
            if not os.path.exists(real_path):
                return f"Error: Path {path} does not exist."
            
            items = os.listdir(real_path)
            output = []
            for item in items:
                item_path = os.path.join(real_path, item)
                is_dir = os.path.isdir(item_path)
                kind = "DIR" if is_dir else "FILE"
                output.append(f"{kind}: {item}")
            return "\n".join(output)
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    def read_file(self, path: str) -> str:
        try:
            real_path = self.path_mapper.to_real_path(path)
            if not os.path.exists(real_path):
                return f"Error: File {path} does not exist."
            if not os.path.isfile(real_path):
                return f"Error: {path} is not a file."
            
            with open(real_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def write_file(self, path: str, content: str) -> str:
        try:
            real_path = self.path_mapper.to_real_path(path)

            # Create parent directories if they don't exist
            # os.path.dirname returns empty string for files in root directory
            parent_dir = os.path.dirname(real_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            with open(real_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def run_command(self, command: str) -> str:
        """
        Run a command in the 'gpt' conda environment.
        The working directory is the session workspace root.

        Security note: Commands are executed in a bash shell. While the workspace
        is isolated, the command has access to the conda environment and system.
        """
        try:
            # Basic validation - reject obviously dangerous patterns
            dangerous_patterns = [
                'rm -rf /',
                'dd if=',
                'mkfs.',
                ':(){ :|:& };:',  # Fork bomb
            ]

            for pattern in dangerous_patterns:
                if pattern in command:
                    return f"Error: Command contains potentially dangerous pattern '{pattern}' and was blocked."

            # Construct command to run in conda env with proper escaping
            # We use shlex.quote to safely escape the conda paths
            conda_sh = shlex.quote(settings.CONDA_SH_PATH)
            conda_env = shlex.quote(settings.CONDA_ENV_NAME)

            # Note: We still pass the user command as-is because it may contain
            # legitimate shell constructs (pipes, redirects, etc.)
            # The command comes from the LLM agent, not direct user input
            full_command = f'source {conda_sh} && conda activate {conda_env} && {command}'

            # We need to run this in a shell (bash)
            # And we set cwd to the session workspace
            cwd = str(self.path_mapper.session_workspace)

            process = subprocess.run(
                ['/bin/bash', '-c', full_command],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60  # Timeout to prevent hanging
            )

            output = f"Exit Code: {process.returncode}\n"
            if process.stdout:
                output += f"STDOUT:\n{process.stdout}\n"
            if process.stderr:
                output += f"STDERR:\n{process.stderr}\n"

            return output
        except subprocess.TimeoutExpired:
            return "Error: Command timed out."
        except Exception as e:
            return f"Error running command: {str(e)}"
