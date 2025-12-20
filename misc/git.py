from pathlib import Path
import os
import git


def pull():
    """Pull from origin and return the current commit hash."""
    repo_path = Path(__file__).parent
    repo = git.Repo(repo_path)

    # Pull from origin
    origin = repo.remotes.origin
    origin.pull()

    # Get current commit hash
    commit_hash = repo.head.commit.hexsha
    return commit_hash


def push():
    repo_path = Path(__file__).parent
    repo = git.Repo(repo_path)

    # Stage all changes
    repo.git.add(A=True)

    # Commit with message
    repo.index.commit("[Auto-update] Update LLM generated solutions")

    # Push to origin using PAT token
    origin = repo.remotes.origin
    github_token = os.environ.get("GITHUB_PAT_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_PAT_TOKEN environment variable is not set")

    # Convert to authenticated URL: https://<token>@github.com/...
    original_url = origin.url
    auth_url = original_url.replace("https://github.com/", f"https://{github_token}@github.com/")
    origin.set_url(auth_url)
    try:
        origin.push()
    finally:
        # Restore original URL to avoid storing token in git config
        origin.set_url(original_url)

    # Get current commit hash
    commit_hash = repo.head.commit.hexsha
    return commit_hash
