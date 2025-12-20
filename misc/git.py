from pathlib import Path
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

    # Push to origin
    origin = repo.remotes.origin
    origin.push()

    # Get current commit hash
    commit_hash = repo.head.commit.hexsha
    return commit_hash
