from db.service import get_top_model_latest_session
from dotenv import load_dotenv
import json
from openai import OpenAI
import os
import re
import misc.git as git
from misc.battlefield import validate_code, generate_negotiation_data, run_battles
from misc.io import (
    load_models,
    load_prompts,
    get_current_code,
    get_code_example,
    save_solution,
)
from db.service import save_battle_results, save_battle_samples, get_samples

# Load environment variables from .env file
load_dotenv()

# Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)


def build_user_prompt(
    prompts: dict,
    current_code: str | None = None,
    error: str | None = None,
    samples_data: list | None = None,
) -> str:
    """Build the user prompt, optionally including current code, error, and samples."""
    user_prompt_template = prompts.get("user_prompt", "")

    if current_code:
        current_code_section_template = prompts.get("current_code_section", "")
        current_code_section = current_code_section_template.format(
            current_code=current_code
        )
    else:
        current_code_section = ""

    if error:
        error_section_template = prompts.get("error_section", "")
        error_section = error_section_template.format(error=error)
    else:
        error_section = ""

    if samples_data:
        samples_template = prompts.get("samples", "")
        samples = samples_template.format(
            samples_data=json.dumps(samples_data, indent=2)
        )
    else:
        samples = ""

    return user_prompt_template.format(
        current_code_section=current_code_section,
        error_section=error_section,
        samples=samples,
    )


def call_openrouter(model_name: str, system_prompt: str, user_prompt: str) -> str:
    """Call OpenRouter API and return the response text."""
    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            print(
                f"OpenRouter API call failed (attempt {attempt + 1}/{max_retries}): {e}"
            )

    raise last_error


def extract_python_code(response_text: str) -> str | None:
    """Extract Python code from markdown code blocks."""
    pattern = r"```python\s*(.*?)\s*```"
    matches = re.findall(pattern, response_text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return None


def main():
    # Pull from origin and get current commit
    # We need the commit hash in order to get the samples against the top performing model from the db.
    commit_hash = git.pull()

    # Get samples from the database for this commit
    samples = get_samples(commit_hash)
    print(f"Retrieved {len(samples)} samples from database for commit {commit_hash}")

    # Load models from config
    models: list[dict] = load_models()
    print(f"Loaded models: {models}")

    # Generate negotiation data
    negotiation_data, total_target_worth = generate_negotiation_data()
    print(f"Generated {len(negotiation_data)} negotiation scenarios")
    print(f"Total target worth: {total_target_worth}")
    print(json.dumps(negotiation_data[:2], indent=2))  # Print first 2 for brevity

    # Identify top model
    top_model = get_top_model_latest_session()

    # Iterate through models and call OpenRouter
    for model in models.copy():
        # do not ask to regenerate code for the top model from the latest session
        if model == top_model:
            continue

        display_name = model["display_name"]
        openrouter_name = model["openrouter_name"]

        print(f"\nProcessing model: {display_name}")

        # Get existing code if any
        current_code = get_current_code(display_name)

        # Filter samples to only include those where this model participated
        model_samples = [
            s
            for s in samples
            if s.get("model_name") == display_name
            or s.get("opponent_model_name") == display_name
        ]

        new_code = get_algos(display_name, openrouter_name, current_code, model_samples)
        if not new_code:
            models.remove(model)
            continue

    # Check if we have any models left to battle
    if len(models) < 2:
        print("Not enough models to run battles (need at least 2 models)")
        return

    try:
        # Run battles between all models
        print("\n" + "=" * 50)
        print("Starting negotiation battles...")
        print("=" * 50)

        battle_results, battle_scenarios = run_battles(models, negotiation_data)

        # Check if we got any battle results
        if not battle_results:
            print("No battle results generated - no valid agents found")
            return

        # each model fights against all other models and all other models fight against it (with swapped data)
        max_possible_profit = total_target_worth * 2 * (len(models) - 1)
        # Print results summary
        print("\n" + "=" * 50)
        print("Battle Results Summary:")
        print("=" * 50)
        for model_name, stats in battle_results.items():
            total_profit = stats["total_profit"]
            profit_percentage = (
                (total_profit * 100.0 / max_possible_profit)
                if max_possible_profit > 0
                else 0
            )
            print(
                f"{model_name}: max_possible_profit={max_possible_profit}, total_profit={total_profit}, profit_percentage={profit_percentage:.2f}%"
            )

        new_commit_hash = git.push()

        # Determine the winner (model with max total profit)
        winner_name = max(
            battle_results.keys(), key=lambda m: battle_results[m]["total_profit"]
        )
        print(f"\nWinner: {winner_name}")
        # Save battle scenarios
        save_battle_samples(battle_scenarios, new_commit_hash)

    except Exception as e:
        print(f"Failed to run battles, push changes or save battle samples: {e}")
        return

    # Save results to database (only if save_battle_samples succeeded)
    save_battle_results(battle_results, max_possible_profit, new_commit_hash)


def get_algos(display_name, openrouter_name, current_code, samples):

    prompts = load_prompts()
    system_prompt_template = prompts.get("system_prompt", "")
    problem_description = prompts.get("problem_description", "")
    code_example = get_code_example()
    problem_description = problem_description.format(code_example=code_example)
    system_prompt = system_prompt_template.format(
        model_name=display_name, problem_description=problem_description
    )

    error = None
    max_attempts = 3
    for attempt in range(max_attempts):
        print(f"Attempt {attempt + 1}/{max_attempts}")

        # Build user prompt with current code, error, and samples (if any)
        user_prompt = build_user_prompt(prompts, current_code, error, samples)

        print("=" * 20)
        print(f"{display_name}: {system_prompt=}")
        print("-" * 20)
        print(f"{display_name}: {user_prompt=}")
        print("=" * 20)
        # Call OpenRouter
        response_text = call_openrouter(openrouter_name, system_prompt, user_prompt)

        # Extract Python code from response
        extracted_code = extract_python_code(response_text)
        if not extracted_code:
            error = "No Python code block found in response"
            current_code = None
            print(f"Error: {error}")
            continue

            # Validate the code
        is_valid, validation_error = validate_code(extracted_code)
        if is_valid:
            # Save the solution
            save_solution(display_name, extracted_code)
            print(f"Successfully validated and saved code for {display_name}")
            return extracted_code
        else:
            error = validation_error
            current_code = extracted_code
            print(f"Validation error: {error}")

    print(f"Failed to get valid code for {display_name} after {max_attempts} attempts")
    return None


if __name__ == "__main__":
    main()
