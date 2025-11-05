"""
Runtime context capture
NEW - Phase 1 enhancements for full attribution
"""

import os
import sys
import subprocess
import platform
from typing import Dict, Any, Optional, List
from pathlib import Path


def get_runtime_versions() -> Dict[str, str]:
    """
    Get versions of runtime environments
    Phase 1: Capture Python, Node, Docker versions for reproducibility
    
    Returns:
        Dict with version strings
    """
    versions = {
        "os": platform.system() + " " + platform.release(),
        "python": platform.python_version(),
    }
    
    # Try to get Node version
    try:
        node_version = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if node_version.returncode == 0:
            versions["node"] = node_version.stdout.strip().lstrip('v')
    except:
        pass
    
    # Try to get Docker version
    try:
        docker_version = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if docker_version.returncode == 0:
            # Extract just version number from "Docker version 24.0.5, build abc123"
            version_str = docker_version.stdout.strip()
            if "version" in version_str.lower():
                version_str = version_str.split("version")[1].split(",")[0].strip()
            versions["docker"] = version_str
    except:
        pass
    
    # Get shell
    shell = os.environ.get("SHELL", "")
    if not shell and sys.platform == "win32":
        shell = "PowerShell" if "powershell" in os.environ.get("PSModulePath", "").lower() else "cmd"
    versions["shell"] = Path(shell).name if shell else "unknown"
    
    return versions


def get_git_info(repo_path: Path) -> Optional[Dict[str, Any]]:
    """
    Get git repository information
    Phase 1: Capture branch, commit, dirty state
    
    Args:
        repo_path: Path to git repository root
        
    Returns:
        Dict with git info or None if not a git repo
    """
    if not (repo_path / ".git").exists():
        return None
    
    try:
        # Get current branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=2
        )
        
        # Get commit hash
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=2
        )
        
        # Get short commit hash
        commit_short_result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=2
        )
        
        # Check if working directory is dirty
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=2
        )
        
        # Get remote URL
        remote_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if branch_result.returncode == 0 and commit_result.returncode == 0:
            git_info = {
                "branch": branch_result.stdout.strip(),
                "commit": commit_short_result.stdout.strip() if commit_short_result.returncode == 0 else commit_result.stdout.strip()[:7],
                "commit_full": commit_result.stdout.strip(),
                "dirty": bool(status_result.stdout.strip()) if status_result.returncode == 0 else False,
            }
            
            if remote_result.returncode == 0:
                remote_url = remote_result.stdout.strip()
                # Convert SSH to HTTPS for cleaner display
                if remote_url.startswith("git@"):
                    remote_url = remote_url.replace(":", "/").replace("git@", "https://").replace(".git", "")
                git_info["remote"] = remote_url
                
                # Extract repo_url (just the github.com/user/repo part)
                if "github.com" in remote_url or "gitlab.com" in remote_url:
                    git_info["repo_url"] = remote_url.replace("https://", "").replace(".git", "")
            
            return git_info
    except Exception:
        pass
    
    return None


def get_env_context(working_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Get environment context
    Phase 1: Working directory, shell, relevant env vars
    
    Args:
        working_dir: Current working directory (defaults to os.getcwd())
        
    Returns:
        Dict with environment context
    """
    if working_dir is None:
        working_dir = Path.cwd()
    
    context = {
        "working_dir": str(working_dir),
        "os": platform.system(),
    }
    
    # Get shell
    runtime = get_runtime_versions()
    context["shell"] = runtime.get("shell", "unknown")
    
    # Capture relevant env vars (not secrets!)
    relevant_vars = {}
    for var in ["NODE_ENV", "PYTHON_ENV", "ENVIRONMENT", "ENV"]:
        if var in os.environ:
            relevant_vars[var] = os.environ[var]
    
    if relevant_vars:
        context["env_vars"] = relevant_vars
    
    return context


def detect_project_name(file_path: Path, project_root: Path) -> Dict[str, str]:
    """
    Detect project name from file path
    Based on existing VMS logic for subdirectory detection
    
    Args:
        file_path: Path to current file
        project_root: Project root directory (e.g., C:\\DEV)
        
    Returns:
        Dict with project name and optional subproject
    """
    try:
        relative = file_path.relative_to(project_root)
        parts = relative.parts
        
        if len(parts) == 0:
            return {"name": "engineering-home", "subproject": None}
        
        # First directory is the project
        project_name = parts[0]
        
        # Check for subproject (e.g., services/api)
        subproject = None
        if len(parts) > 1 and parts[0] in ["services", "tools", "apps"]:
            subproject = parts[1]
        
        return {
            "name": project_name if project_name else "engineering-home",
            "subproject": subproject
        }
    except ValueError:
        # file_path is not under project_root
        return {"name": "external", "subproject": None}


def get_open_files_context(max_files: int = 10) -> Dict[str, Any]:
    """
    Get context about open files in editor
    NOTE: This is a placeholder - actual implementation would need
    to interface with Cursor's API or file system monitoring
    
    Args:
        max_files: Maximum number of files to track
        
    Returns:
        Dict with open files info
    """
    # TODO: Implement via Cursor API when available
    # For now, return placeholder
    return {
        "open_files": [],
        "open_file_count": 0
    }


def get_workspace_fingerprint(workspace_path: Path) -> str:
    """
    Generate fingerprint of workspace
    Phase 1: Hash of repo root + workspace file
    
    Args:
        workspace_path: Path to workspace root
        
    Returns:
        SHA256 hash string
    """
    import hashlib
    
    # Combine workspace path + workspace file name if exists
    fingerprint_input = str(workspace_path)
    
    workspace_files = list(workspace_path.glob("*.code-workspace"))
    if workspace_files:
        fingerprint_input += workspace_files[0].name
    
    return hashlib.sha256(fingerprint_input.encode('utf-8')).hexdigest()

