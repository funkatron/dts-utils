"""Git helpers for the Draw Things community-models repository."""

from __future__ import annotations

import subprocess
from pathlib import Path

COMMUNITY_MODELS_REPO_URL = "https://github.com/drawthingsai/community-models.git"


class RepoSyncError(RuntimeError):
    """Raised when the upstream repository cannot be cloned or updated."""


def _run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def ensure_repo(repo_dir: Path, repo_url: str = COMMUNITY_MODELS_REPO_URL) -> str:
    """Clone or fast-forward the upstream repository."""
    repo_dir = repo_dir.resolve()
    repo_dir.parent.mkdir(parents=True, exist_ok=True)

    try:
        if not repo_dir.exists():
            _run_git(["clone", repo_url, str(repo_dir)])
            return "cloned"

        git_dir = repo_dir / ".git"
        if not git_dir.exists():
            expected_files = [
                repo_dir / "uncurated_models.txt",
                repo_dir / "uncurated_models_sha256.json",
            ]
            if all(path.exists() for path in expected_files):
                return "using-existing-snapshot"
            raise RepoSyncError(f"{repo_dir} exists but is not a git repository")

        _run_git(["fetch", "--all", "--prune"], cwd=repo_dir)
        _run_git(["pull", "--ff-only"], cwd=repo_dir)
        return "updated"
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or str(exc)
        raise RepoSyncError(f"Failed to sync {repo_url}: {detail}") from exc
