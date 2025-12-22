from pathlib import Path
import os
import git

from misc.utils import sanitize

# Initialize repo once at module level
_repo_path = Path(__file__).parent.parent
_repo = git.Repo(_repo_path)


def pull():
    """Pull from origin and return the current commit hash."""
    # Pull from origin
    origin = _repo.remotes.origin
    origin.pull()

    # Get current commit hash
    commit_hash = _repo.head.commit.hexsha
    return commit_hash


def push():
    # Stage all changes
    _repo.git.add(A=True)

    # Commit with message
    _repo.index.commit("[Auto-update] Update LLM generated solutions")

    # Push to origin using PAT
    origin = _repo.remotes.origin
    github_token = os.environ.get("GITHUB_PAT")
    if not github_token:
        raise ValueError("GITHUB_PAT environment variable is not set")

    # Convert to authenticated URL: https://<token>@github.com/...
    original_url = origin.url
    auth_url = original_url.replace(
        "https://github.com/", f"https://{github_token}@github.com/"
    )
    origin.set_url(auth_url)
    try:
        origin.push()
    finally:
        # Restore original URL to avoid storing token in git config
        origin.set_url(original_url)

    # Get current commit hash
    commit_hash = _repo.head.commit.hexsha
    return commit_hash


def get_code_link(commit_hash: str, model_name: str) -> str:
    """
    Generate a GitHub link to the model's solution file at a specific commit.

    Args:
        commit_hash: The git commit hash
        model_name: The model's display name (used as the filename)

    Returns:
        A GitHub URL like: https://github.com/owner/repo/blob/{commit_hash}/solutions/{model_name}.py
    """
    # Get the origin URL
    origin_url = _repo.remotes.origin.url

    # Convert SSH URL to HTTPS if needed: git@github.com:owner/repo.git -> https://github.com/owner/repo
    if origin_url.startswith("git@github.com:"):
        origin_url = origin_url.replace("git@github.com:", "https://github.com/")

    # Remove .git suffix if present
    if origin_url.endswith(".git"):
        origin_url = origin_url[:-4]

    sanitized_display_name = sanitize(model_name)
    # Build the link
    code_link = f"{origin_url}/blob/{commit_hash}/solutions/{sanitized_display_name}.py"
    return code_link
