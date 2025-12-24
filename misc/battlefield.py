import os
import random
import multiprocessing

from misc.io import get_current_code


def load_agent_class(display_name: str):
    """
    Load the Agent class from a model's solution file.
    Returns the Agent class or None if not found/invalid.
    """
    code = get_current_code(display_name)
    if code is None:
        return None

    try:
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

    Returns:
        A tuple of (negotiation_data, total_target_worth) where:
        - negotiation_data: list of scenarios
        - total_target_worth: sum of all scenario worths (same for all models)
    """

    # Get max_scenario_data from environment variable, default to 20
    try:
        max_scenario_data = int(os.getenv("MAX_SCENARIO_DATA", "20"))
    except ValueError:
        max_scenario_data = 20

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
    total_target_worth = 0
    target_worths = [32, 64, 128]

    for _ in range(max_scenario_data):
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

        # Add to total_target_worth (same worth for each player in each scenario)
        total_target_worth += target_worth

    return data, total_target_worth


def run_negotiation(agent_0, agent_1, counts, max_rounds, name_0: str, name_1: str):
    """
    Run a negotiation session between two agents.

    Returns a tuple (agent_0_items, agent_1_items, outcome, turn_history) where:
    - agent_0_items: list of items agent_0 gets (or None if no deal)
    - agent_1_items: list of items agent_1 gets (or None if no deal)
    - outcome: 'deal', 'no_deal', or 'error'
    - turn_history: list of dicts with 'round', '{name_0} offer', '{name_1} offer' for each round
    """
    offer = None  # First offer starts as None
    turn_history = []
    offer_key_0 = f"{name_0} offer"
    offer_key_1 = f"{name_1} offer"

    for round_num in range(max_rounds):
        round_record = {
            "round": round_num + 1,
            offer_key_0: None,
            offer_key_1: None,
        }

        # Agent 0's turn
        try:
            response_0 = agent_0.offer(offer)
        except Exception as e:
            print(f"Agent 0 error: {e}")
            return None, None, "error_agent_0", turn_history

        if response_0 is None:
            if offer is not None:
                # Agent 0 accepts agent 1's offer
                # offer contains what agent_0 gets
                agent_0_items = offer
                agent_1_items = [counts[i] - offer[i] for i in range(len(counts))]
                round_record[offer_key_0] = None  # Accepted
                turn_history.append(round_record)
                return agent_0_items, agent_1_items, "deal", turn_history
            else:
                # Agent 0 returned None on the first round (invalid - must make an offer)
                turn_history.append(round_record)
                return None, None, "error_agent_0", turn_history

        # Agent 0 made a counter-offer (what agent_0 wants for itself)
        round_record[offer_key_0] = response_0
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
            round_record[offer_key_1] = None  # Accepted
            turn_history.append(round_record)
            return agent_0_items, agent_1_items, "deal", turn_history

        # Agent 1 made a counter-offer (what agent_1 wants for itself)
        round_record[offer_key_1] = response_1
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


def _run_model_pair_task(args):
    model_0, model_1, negotiation_data_local, num_samples_local = args
    display_name_0 = model_0["display_name"]
    display_name_1 = model_1["display_name"]
    Agent0Class = load_agent_class(display_name_0)
    if Agent0Class is None:
        print(f"Skipping {display_name_0}: no valid agent found")
        return {}, {}
    Agent1Class = load_agent_class(display_name_1)
    if Agent1Class is None:
        print(f"Skipping opponent {display_name_1}: no valid agent found")
        return {}, {}

    pair_results = {
        display_name_0: {"total_profit": 0},
        display_name_1: {"total_profit": 0},
    }
    pair_battle_scenarios = {}
    pair_scenario_counts = {}

    canonical_key = tuple(sorted([display_name_0, display_name_1]))
    pair_battle_scenarios[canonical_key] = []
    pair_scenario_counts[canonical_key] = {
        "as_agent_0": 0,
        "as_agent_1": 0,
    }

    ref_model = canonical_key[0]
    max_as_agent_0 = (num_samples_local + 1) // 2
    max_as_agent_1 = num_samples_local // 2

    orders = [
        (display_name_0, display_name_1, Agent0Class, Agent1Class),
        (display_name_1, display_name_0, Agent1Class, Agent0Class),
    ]

    for name_0, name_1, AgentClass0, AgentClass1 in orders:
        print(f"\nBattle: {name_0} vs {name_1}")

        for scenario in negotiation_data_local:
            counts = scenario["counts"]
            values_0 = scenario["player_0"]
            values_1 = scenario["player_1"]
            max_rounds = scenario["rounds"]

            try:
                agent_0 = AgentClass0(0, counts, values_0, max_rounds)
                agent_1 = AgentClass1(1, counts, values_1, max_rounds)

                items_0, items_1, outcome, turn_history = run_negotiation(
                    agent_0,
                    agent_1,
                    counts,
                    max_rounds,
                    name_0,
                    name_1,
                )

                profit_0 = calculate_profit(items_0, values_0)
                profit_1 = calculate_profit(items_1, values_1)

                pair_results[name_0]["total_profit"] += profit_0
                pair_results[name_1]["total_profit"] += profit_1

                print(
                    f"  Scenario result: {outcome}, profits: {name_0}={profit_0}, {name_1}={profit_1}"
                )

                if name_0 == ref_model:
                    position_key = "as_agent_0"
                    max_for_position = max_as_agent_0
                else:
                    position_key = "as_agent_1"
                    max_for_position = max_as_agent_1

                if (
                    num_samples_local > 0
                    and pair_scenario_counts[canonical_key][position_key]
                    < max_for_position
                ):
                    scenario_with_names = {
                        "counts": scenario["counts"],
                        "rounds": scenario["rounds"],
                        f"{name_0} values": scenario["player_0"],
                        f"{name_1} values": scenario["player_1"],
                    }
                    pair_battle_scenarios[canonical_key].append(
                        {
                            "scenario": scenario_with_names,
                            "outcome": outcome,
                            f"{name_0} profit": profit_0,
                            f"{name_1} profit": profit_1,
                            "turn_history": turn_history,
                        }
                    )
                    pair_scenario_counts[canonical_key][position_key] += 1

            except Exception as e:
                print(f"  Error in scenario: {e}")

    return pair_results, pair_battle_scenarios


def run_battles(
    models: list[dict],
    negotiation_data: list[dict],
    num_samples: int = 5,
) -> tuple[dict, dict]:
    """
    Run negotiation battles between all pairs of models.

    Args:
        models: List of model dicts with 'display_name' and optionally 'openrouter_name' or 'is_human'
        negotiation_data: List of negotiation scenarios with 'counts', 'player_0', 'player_1', 'rounds'
        num_samples: Maximum number of samples to store per model pair (default 5, can be set via NUM_SAMPLES env var)

    Returns:
        A tuple of:
        - results: Dictionary with model display names as keys and dicts containing:
            - 'total_profit': accumulated profit across all sessions
        - battle_scenarios: Dictionary mapping (model_X, model_Y) to list of scenario data.
            For each pair, stores up to num_samples scenarios, with num_samples // 2 where
            model_X is agent_0 and the rest where model_X is agent_1. Each scenario contains:
            - 'scenario': the original scenario data
            - 'outcome': 'deal', 'no_deal', or error type
            - '{model_x} profit': profit achieved by model_x
            - '{model_y} profit': profit achieved by model_y
            - 'turn_history': list of offers per round with '{model_name} offer' keys
    """
    try:
        num_samples = int(os.getenv("NUM_SAMPLES", str(num_samples)))
    except ValueError:
        pass

    results = {}
    battle_scenarios = {}
    for model in models:
        display_name = model["display_name"]
        results[display_name] = {
            "total_profit": 0,
        }

    tasks = []
    for i, model_0 in enumerate(models):
        for j in range(i + 1, len(models)):
            model_1 = models[j]
            tasks.append((model_0, model_1, negotiation_data, num_samples))

    max_processes = os.getenv("NUM_PROCESSES")
    try:
        max_processes = int(max_processes) if max_processes is not None else None
    except ValueError:
        max_processes = None

    cpu_count = multiprocessing.cpu_count()
    if max_processes is None:
        processes = min(8, cpu_count)
    else:
        processes = max(1, min(max_processes, cpu_count))

    if processes == 1 or not tasks:
        for task in tasks:
            pair_results, pair_battle_scenarios = _run_model_pair_task(task)
            for name, data in pair_results.items():
                if name in results:
                    results[name]["total_profit"] += data["total_profit"]
                else:
                    results[name] = {"total_profit": data["total_profit"]}
            for key, scenarios in pair_battle_scenarios.items():
                if key not in battle_scenarios:
                    battle_scenarios[key] = []
                battle_scenarios[key].extend(scenarios)
    else:
        with multiprocessing.Pool(processes=processes) as pool:
            for pair_results, pair_battle_scenarios in pool.imap_unordered(
                _run_model_pair_task, tasks
            ):
                for name, data in pair_results.items():
                    if name in results:
                        results[name]["total_profit"] += data["total_profit"]
                    else:
                        results[name] = {"total_profit": data["total_profit"]}
                for key, scenarios in pair_battle_scenarios.items():
                    if key not in battle_scenarios:
                        battle_scenarios[key] = []
                    battle_scenarios[key].extend(scenarios)

    return results, battle_scenarios
