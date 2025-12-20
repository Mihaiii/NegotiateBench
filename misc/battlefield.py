import os
import random
from pathlib import Path


def load_agent_class(display_name: str):
    """
    Load the Agent class from a model's solution file.
    Returns the Agent class or None if not found/invalid.
    """
    solutions_path = Path(__file__).parent.parent / "solutions" / f"{display_name}.py"
    if not solutions_path.exists():
        return None

    try:
        with open(solutions_path, "r") as f:
            code = f.read()

        namespace = {}
        exec(code, namespace)

        if "Agent" not in namespace:
            return None

        return namespace["Agent"]
    except Exception as e:
        print(f"Failed to load agent for {display_name}: {e}")
        return None


def validate_code(code: str) -> tuple[bool, str | None]:
    """
    Validate the code by:
    1. Loading it in memory as Python code
    2. Checking that an Agent class exists with proper __init__ and offer method
    3. Testing the Agent with sample data

    Returns (is_valid, error_message)
    """
    try:
        # Compile and execute the code in a namespace
        namespace = {}
        exec(code, namespace)

        # Check that Agent class exists
        if "Agent" not in namespace:
            return False, "Code does not contain an 'Agent' class"

        Agent = namespace["Agent"]

        # Test instantiation with sample data
        me = 0
        counts = [2, 3, 1]
        values = [1, 2, 3]
        max_rounds = 5

        agent = Agent(me, counts, values, max_rounds)

        # Test offer method with None (first offer)
        result = agent.offer(None)

        # Test offer method with sample offer
        sample_offer = [1, 1, 0]
        result = agent.offer(sample_offer)

        return True, None

    except Exception as e:
        return False, str(e)


def generate_negotiation_data():
    """
    Generate negotiation data with player_0, player_1, and rounds.

    Each player has counts and values lists where:
    - Both lists have the same length (between 2 and 10)
    - The total worth (sum of counts[i] * values[i]) is the same for both players
    - Total worth can be 32, 64, or 128
    """

    # Get max_num_data from environment variable, default to 20
    try:
        max_num_data = int(os.getenv("MAX_NUM_DATA", "20"))
    except ValueError:
        max_num_data = 20

    def generate_player_values(counts, target_worth):
        """Generate values list that sums to target_worth when multiplied with counts."""
        length = len(counts)
        max_attempts = 1000

        def random_value():
            """Generate random value with reduced probability of 0."""
            # 5% chance of 0, 95% chance of 1-10
            if random.random() < 0.05:
                return 0
            return random.randint(1, 10)

        for _ in range(max_attempts):
            # Generate random values, leaving last 2 to adjust
            values = [random_value() for _ in range(length - 2)]

            # Calculate current worth without last 2 values
            current_worth = sum(c * v for c, v in zip(counts[:-2], values))

            # Calculate what remains for the last 2 positions
            remaining = target_worth - current_worth

            # Get the last two counts
            c1, c2 = counts[-2], counts[-1]

            # Try to find valid v1, v2 such that c1*v1 + c2*v2 = remaining
            # Strategy: use parity to guide the search
            found = False

            # If c2 is even, we have more flexibility; if odd, remaining - c1*v1 must be divisible by c2
            for v1 in range(11):
                leftover = remaining - c1 * v1
                if leftover >= 0 and leftover % c2 == 0:
                    v2 = leftover // c2
                    if 0 <= v2 <= 10:
                        values.append(v1)
                        values.append(v2)
                        found = True
                        break

            if found:
                # Only return if less than half of the values are zeros
                zero_count = sum(1 for v in values if v == 0)
                if zero_count < len(values) / 2:
                    return values

        return None

    data = []
    target_worths = [32, 64, 128]

    for _ in range(max_num_data):
        # Random length between 2 and 10
        length = random.randint(2, 10)

        # Generate random counts (1-5 for each item) - shared by both players
        counts = [random.randint(1, 5) for _ in range(length)]

        # Random target worth
        target_worth = random.choice(target_worths)

        # Generate values for both players with same counts and target worth
        player_0 = generate_player_values(counts, target_worth)
        if not player_0:
            continue
        player_1 = generate_player_values(counts, target_worth)
        if not player_1:
            continue

        # Set rounds based on target_worth
        rounds = target_worth // 4

        data.append(
            {
                "counts": counts,
                "player_0": player_0,
                "player_1": player_1,
                "rounds": rounds,
            }
        )

    return data


def run_negotiation(agent_0, agent_1, counts, max_rounds):
    """
    Run a negotiation session between two agents.

    Returns a tuple (agent_0_items, agent_1_items, outcome, turn_history) where:
    - agent_0_items: list of items agent_0 gets (or None if no deal)
    - agent_1_items: list of items agent_1 gets (or None if no deal)
    - outcome: 'deal', 'no_deal', or 'error'
    - turn_history: list of dicts with 'round', 'agent_0_offer', 'agent_1_offer' for each round
    """
    offer = None  # First offer starts as None
    turn_history = []

    for round_num in range(max_rounds):
        round_record = {
            "round": round_num + 1,
            "agent_0_offer": None,
            "agent_1_offer": None,
        }

        # Agent 0's turn
        try:
            response_0 = agent_0.offer(offer)
        except Exception as e:
            print(f"Agent 0 error: {e}")
            return None, None, "error_agent_0", turn_history

        if response_0 is None and offer is not None:
            # Agent 0 accepts agent 1's offer
            # offer contains what agent_0 gets
            agent_0_items = offer
            agent_1_items = [counts[i] - offer[i] for i in range(len(counts))]
            round_record["agent_0_offer"] = None  # Accepted
            turn_history.append(round_record)
            return agent_0_items, agent_1_items, "deal", turn_history

        if response_0 is not None:
            # Agent 0 made a counter-offer (what agent_0 wants for itself)
            round_record["agent_0_offer"] = response_0
            # Convert to what agent_1 would get
            offer_for_agent_1 = [counts[i] - response_0[i] for i in range(len(counts))]

        # Agent 1's turn
        try:
            response_1 = agent_1.offer(offer_for_agent_1)
        except Exception as e:
            print(f"Agent 1 error: {e}")
            turn_history.append(round_record)
            return None, None, "error_agent_1", turn_history

        if response_1 is None:
            # Agent 1 accepts agent 0's offer
            agent_0_items = response_0
            agent_1_items = [counts[i] - response_0[i] for i in range(len(counts))]
            round_record["agent_1_offer"] = None  # Accepted
            turn_history.append(round_record)
            return agent_0_items, agent_1_items, "deal", turn_history

        # Agent 1 made a counter-offer (what agent_1 wants for itself)
        round_record["agent_1_offer"] = response_1
        turn_history.append(round_record)

        # Convert to what agent_0 would get for next round
        offer = [counts[i] - response_1[i] for i in range(len(counts))]

    # No deal reached within max_rounds
    return None, None, "no_deal", turn_history


def calculate_profit(items, values):
    """Calculate the profit (sum of item * value) for a player."""
    if items is None:
        return 0
    return sum(items[i] * values[i] for i in range(len(items)))


def run_battles(
    models: list[dict], negotiation_data: list[dict], num_samples: int = 5
) -> tuple[dict, dict]:
    """
    Run negotiation battles between all pairs of models.

    Args:
        models: List of model dicts with 'display_name' and 'openrouter_name'
        negotiation_data: List of negotiation scenarios with 'counts', 'player_0', 'player_1', 'rounds'
        num_samples: Maximum number of samples to store per model pair (default 5, can be set via NUM_SAMPLES env var)

    Returns:
        A tuple of:
        - results: Dictionary with model display names as keys and dicts containing:
            - 'total_profit': accumulated profit across all sessions
            - 'sessions': number of negotiation sessions
        - battle_scenarios: Dictionary mapping (model_X, model_Y) to list of scenario data.
            For each pair, stores up to num_samples scenarios, with num_samples // 2 where
            model_X is agent_0 and the rest where model_X is agent_1. Each scenario contains:
            - 'scenario': the original scenario data
            - 'agent_0': name of the model that was agent_0
            - 'agent_1': name of the model that was agent_1
            - 'outcome': 'deal', 'no_deal', or error type
            - 'profit_agent_0': profit achieved by agent_0
            - 'profit_agent_1': profit achieved by agent_1
            - 'turn_history': list of offers per round
    """
    # Get num_samples from environment variable if available
    try:
        num_samples = int(os.getenv("NUM_SAMPLES", str(num_samples)))
    except ValueError:
        pass

    results = {}
    # Track scenarios for each model pair
    # Key: (model_X, model_Y), Value: list of scenario dicts
    battle_scenarios = {}
    # Track counts for limiting samples: key -> {'as_agent_0': count, 'as_agent_1': count}
    scenario_counts = {}

    # Initialize results for all models
    for model in models:
        display_name = model["display_name"]
        results[display_name] = {"total_profit": 0, "sessions": 0}

    # Run each model against every other model
    for i, model_0 in enumerate(models):
        display_name_0 = model_0["display_name"]
        Agent0Class = load_agent_class(display_name_0)

        if Agent0Class is None:
            print(f"Skipping {display_name_0}: no valid agent found")
            continue

        for j, model_1 in enumerate(models):
            if i == j:
                continue  # Don't play against itself

            display_name_1 = model_1["display_name"]
            Agent1Class = load_agent_class(display_name_1)

            if Agent1Class is None:
                print(f"Skipping opponent {display_name_1}: no valid agent found")
                continue

            print(f"\nBattle: {display_name_0} vs {display_name_1}")

            # Run through all negotiation scenarios
            for scenario in negotiation_data:
                counts = scenario["counts"]
                values_0 = scenario["player_0"]
                values_1 = scenario["player_1"]
                max_rounds = scenario["rounds"]

                try:
                    # Create agent instances
                    # me=0 means agent goes first, me=1 means agent goes second
                    agent_0 = Agent0Class(0, counts, values_0, max_rounds)
                    agent_1 = Agent1Class(1, counts, values_1, max_rounds)

                    # Run the negotiation
                    items_0, items_1, outcome, turn_history = run_negotiation(
                        agent_0, agent_1, counts, max_rounds
                    )

                    # Calculate profits
                    profit_0 = calculate_profit(items_0, values_0)
                    profit_1 = calculate_profit(items_1, values_1)

                    # Update results
                    results[display_name_0]["total_profit"] += profit_0
                    results[display_name_0]["sessions"] += 1
                    results[display_name_1]["total_profit"] += profit_1
                    results[display_name_1]["sessions"] += 1

                    print(
                        f"  Scenario result: {outcome}, profits: {display_name_0}={profit_0}, {display_name_1}={profit_1}"
                    )

                    # Store battle scenario with proper structure
                    # Use sorted tuple as canonical key to group both orderings
                    canonical_key = tuple(sorted([display_name_0, display_name_1]))

                    if canonical_key not in battle_scenarios:
                        battle_scenarios[canonical_key] = []
                        scenario_counts[canonical_key] = {
                            "as_agent_0": 0,
                            "as_agent_1": 0,
                        }

                    # Determine if we can add this scenario
                    # model at canonical_key[0] is our reference model
                    # Check if current model_0 matches canonical_key[0]
                    ref_model = canonical_key[0]
                    if display_name_0 == ref_model:
                        # ref_model is agent_0 in this battle
                        position_key = "as_agent_0"
                        max_for_position = num_samples // 2
                    else:
                        # ref_model is agent_1 in this battle
                        position_key = "as_agent_1"
                        max_for_position = num_samples - (num_samples // 2)

                    # Only add if we haven't reached the limit for this position
                    if scenario_counts[canonical_key][position_key] < max_for_position:
                        battle_scenarios[canonical_key].append(
                            {
                                "scenario": scenario,
                                "agent_0": display_name_0,
                                "agent_1": display_name_1,
                                "outcome": outcome,
                                "profit_agent_0": profit_0,
                                "profit_agent_1": profit_1,
                                "turn_history": turn_history,
                            }
                        )
                        scenario_counts[canonical_key][position_key] += 1

                except Exception as e:
                    print(f"  Error in scenario: {e}")
                    # Still count the session but with 0 profit
                    results[display_name_0]["sessions"] += 1
                    results[display_name_1]["sessions"] += 1

    return results, battle_scenarios
