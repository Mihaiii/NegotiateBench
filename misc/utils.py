import re


def sanitize(name: str) -> str:
    """Sanitize a name to be safe for use as a filename or Python identifier.

    Replaces any non-word characters (anything except a-z, A-Z, 0-9, _) with underscores.
    """
    return re.sub(r"[^\w]", "_", name)
