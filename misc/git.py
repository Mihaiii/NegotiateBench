from pathlib import Path
import os
import git

from misc.utils import sanitize

# Initialize repo once at module level
_repo_path = Path(__file__).parent.parent
_repo = git.Repo(_repo_path)


def _ensure_git_config():
    """Ensure Git user email and name are configured."""
    try:
        email = _repo.config_reader().get_value("user", "email", None)
        name = _repo.config_reader().get_value("user", "name", None)
    except:
        email = None
        name = None
    
    if not email:
        email = os.environ.get("GIT_USER_EMAIL", "auto-update@negotiatebench.local")
        _repo.config_writer().set_value("user", "email", email).release()
    
    if not name:
        name = os.environ.get("GIT_USER_NAME", "Auto Update Bot")
        _repo.config_writer().set_value("user", "name", name).release()


_ensure_git_config()


def pull():
    """Pull from origin and return the current commit hash."""
    _ensure_git_config()
    origin = _repo.remotes.origin
    origin.pull()


def push():
    _ensure_git_config()
    _repo.git.add(A=True)

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
        # Pull with rebase first to avoid "failed to push some refs" errors
        origin.pull(rebase=True)
        origin.push()
    finally:
        # Restore original URL to avoid storing token in git config
        origin.set_url(original_url)

    # Get current commit hash
    commit_hash = _repo.head.commit.hexsha
    return commit_hash


def get_code_link_at_commit(commit_hash: str, model_name: str) -> str:
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


def get_solution_code_link(model_name: str) -> str:
    origin_url = _repo.remotes.origin.url
    if origin_url.startswith("git@github.com:"):
        origin_url = origin_url.replace("git@github.com:", "https://github.com/")
    if origin_url.endswith(".git"):
        origin_url = origin_url[:-4]
    try:
        branch = _repo.active_branch.name
    except Exception:
        branch = "main"
    sanitized_display_name = sanitize(model_name)
    return f"{origin_url}/blob/{branch}/solutions/{sanitized_display_name}.py"


# Get the newest commit for each file in the solutions folder and return the newest commit overall
def get_newest_commit_in_solutions() -> str:
    """
    Go through the latest commit for each file in the solutions folder and return the newest commit hash.
    Returns:
        The newest commit hash (str) among all files in the solutions folder.
    """
    solutions_path = _repo_path / "solutions"
    newest_commit = None
    newest_time = None
    for file in solutions_path.glob("*.py"):
        # Get the latest commit for this file
        commits = list(_repo.iter_commits(paths=str(file), max_count=1))
        if commits:
            commit = commits[0]
            commit_time = commit.committed_datetime
            if newest_time is None or commit_time > newest_time:
                newest_time = commit_time
                newest_commit = commit.hexsha
    return newest_commit
