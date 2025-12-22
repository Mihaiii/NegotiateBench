from pathlib import Path
import yaml

from misc.utils import sanitize


def load_models():
    """Load the models.yaml file and return the models list."""
    config_path = Path(__file__).parent.parent / "models.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("models", [])


def load_prompts():
    """Load the prompts.yaml file and return the prompts."""
    prompts_path = Path(__file__).parent / "prompts.yaml"
    with open(prompts_path, "r") as f:
        prompts = yaml.safe_load(f)
    return prompts


def get_current_code(display_name: str) -> str | None:
    """Get the current code for a model from the solutions folder."""
    sanitized_display_name = sanitize(display_name)
    solutions_path = (
        Path(__file__).parent.parent / "solutions" / f"{sanitized_display_name}.py"
    )
    if solutions_path.exists():
        with open(solutions_path, "r") as f:
            return f.read()
    return None


def get_code_example() -> str:
    """Get the code example from solutions/example.py."""
    example_path = Path(__file__).parent.parent / "solutions" / "example.py"
    with open(example_path, "r") as f:
        return f.read()
