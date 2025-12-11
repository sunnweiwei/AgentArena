import os
from pathlib import Path
from typing import Optional

class PathMapper:
    def __init__(self, session_id: str, workspace_root: str):
        self.session_id = session_id
        self.workspace_root = Path(workspace_root)
        self.session_workspace = self.workspace_root / session_id
        self.virtual_root = Path("/workspace")

    def to_real_path(self, virtual_path: str) -> str:
        """
        Convert a virtual path (e.g., /workspace/foo.txt) to a real server path.
        Enforces that the resulting path is within the session workspace.

        Security: Validates path before resolution to prevent traversal attacks.
        """
        # Normalize virtual path
        if not virtual_path.startswith("/"):
            virtual_path = "/" + virtual_path

        # Remove /workspace prefix if present
        if virtual_path.startswith(str(self.virtual_root)):
            rel_path = os.path.relpath(virtual_path, str(self.virtual_root))
        else:
            # If path doesn't start with /workspace, treat it as relative
            rel_path = virtual_path.lstrip("/")

        # Security check 1: Validate relative path doesn't contain path traversal
        # Normalize the path and check for ".." components
        normalized_rel = os.path.normpath(rel_path)

        # Check if normalization resulted in path traversal
        if normalized_rel.startswith("..") or "/.." in normalized_rel:
            raise ValueError(f"Access denied: Path {virtual_path} contains invalid path traversal")

        # Build real path
        real_path = self.session_workspace / normalized_rel

        # Security check 2: Ensure real_path is within session_workspace
        # Resolve both paths to handle any remaining edge cases
        real_path_resolved = real_path.resolve()
        workspace_resolved = self.session_workspace.resolve()

        # Check if real_path is under workspace (or is workspace itself)
        try:
            real_path_resolved.relative_to(workspace_resolved)
        except ValueError:
            raise ValueError(f"Access denied: Path {virtual_path} resolves to {real_path_resolved} which is outside workspace {workspace_resolved}")

        return str(real_path_resolved)

    def to_virtual_path(self, real_path: str) -> str:
        """
        Convert a real server path to a virtual path for the agent.
        """
        real_path_obj = Path(real_path).resolve()
        try:
            rel_path = real_path_obj.relative_to(self.session_workspace.resolve())
            return str(self.virtual_root / rel_path)
        except ValueError:
            # If path is not in workspace, return it as is or hide it?
            # For now, return as is but maybe we should hide it.
            return str(real_path)

    def ensure_workspace_exists(self):
        self.session_workspace.mkdir(parents=True, exist_ok=True)
