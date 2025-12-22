import os
from datetime import datetime, timezone

import psycopg2
from dotenv import load_dotenv

from misc.git import get_code_link

# Load environment variables from .env file
load_dotenv()

# Environment variables (should be set in caps)
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_top_model_latest_session():
    """
    Get the leaderboard for the latest session.
    Returns the top model (rank 1) or None if the view is empty.
    """
    top_model = None

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT model_name
            FROM negotiations_leaderboard_latest
            WHERE rank = 1
            LIMIT 1;
            """
        )
        row = cursor.fetchone()
        if row:
            top_model = row[0]
    finally:
        cursor.close()
        conn.close()

    return top_model


def get_samples(commit_hash):
    """
    Get all player_data records filtered by commit_hash.
    Returns a list of dictionaries with id, model_name, player_number, data, and commit_hash.
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, model_name, player_number, data, commit_hash
            FROM player_data
            WHERE commit_hash = %s;
            """,
            (commit_hash,),
        )
        rows = cursor.fetchall()
        results = [
            {
                "id": row[0],
                "model_name": row[1],
                "player_number": row[2],
                "data": row[3],
                "commit_hash": row[4],
            }
            for row in rows
        ]
    finally:
        cursor.close()
        conn.close()

    return results


def save_battle_results(results: dict, max_possible_profit: int, commit_hash: str):
    """
    Save battle results to the negotiations table.

    Args:
        results: Dictionary with model names as keys and dicts containing:
            - 'total_profit': accumulated profit across all sessions
        max_possible_profit: Maximum possible profit (same for all models)
        commit_hash: The git commit hash for generating code links
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Use the same timestamp for all records in this transaction
    timestamp = datetime.now(timezone.utc)

    try:
        for model_name, stats in results.items():
            total_profit = stats["total_profit"]

            if max_possible_profit > 0:
                code_link = get_code_link(commit_hash, model_name)
                cursor.execute(
                    """
                    INSERT INTO negotiations (model_name, max_possible_profit, profit, code_link, timestamp)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        model_name,
                        max_possible_profit,
                        total_profit,
                        code_link,
                        timestamp,
                    ),
                )

        conn.commit()
        print(f"Saved battle results for {len(results)} models to database")
    except Exception as e:
        conn.rollback()
        print(f"Failed to save battle results: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def save_player_data(model_name: str, player_number: int, data: str, commit_hash: str):
    """
    Save a single player_data record.

    Args:
        model_name: The name of the losing model
        player_number: 0 or 1, indicating which player position the loser was in
        data: JSON string of the scenario data
        commit_hash: The git commit hash
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO player_data (model_name, player_number, data, commit_hash)
            VALUES (%s, %s, %s, %s);
            """,
            (model_name, player_number, data, commit_hash),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Failed to save player data: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def save_winner_samples(winner_name: str, battle_scenarios: dict, commit_hash: str):
    """
    Save sample battle scenarios involving the winner.

    Args:
        winner_name: The name of the winning model
        battle_scenarios: Dictionary mapping (model_X, model_Y) tuple to list of scenario data.
            Each scenario contains:
            - 'scenario': the original scenario data
            - 'agent_0': name of the model that was agent_0
            - 'agent_1': name of the model that was agent_1
            - 'outcome': 'deal', 'no_deal', or error type
            - 'profit_agent_0': profit achieved by agent_0
            - 'profit_agent_1': profit achieved by agent_1
            - 'turn_history': list of offers per round
        commit_hash: The git commit hash
    """
    import json

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    # Collect all records to insert
    records = []
    for (model_x, model_y), scenarios in battle_scenarios.items():
        # Only process scenarios involving the winner
        if winner_name not in (model_x, model_y):
            continue

        for scenario_info in scenarios:
            # Determine the loser (the model that is not the winner)
            if scenario_info["agent_0"] == winner_name:
                loser_name = scenario_info["agent_1"]
                loser_player_number = 1
            elif scenario_info["agent_1"] == winner_name:
                loser_name = scenario_info["agent_0"]
                loser_player_number = 0
            else:
                continue  # Winner not in this scenario (shouldn't happen)

            # Build the data to save - include all relevant info
            data = {
                "scenario": scenario_info["scenario"],
                "agent_0": scenario_info["agent_0"],
                "agent_1": scenario_info["agent_1"],
                "outcome": scenario_info["outcome"],
                "profit_agent_0": scenario_info["profit_agent_0"],
                "profit_agent_1": scenario_info["profit_agent_1"],
                "turn_history": scenario_info["turn_history"],
            }
            data_json = json.dumps(data)
            records.append((loser_name, loser_player_number, data_json, commit_hash))

    if not records:
        print(f"No battle scenarios found for {winner_name}")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        # Bulk insert all records in a single call
        from psycopg2.extras import execute_values

        execute_values(
            cursor,
            """
            INSERT INTO player_data (model_name, player_number, data, commit_hash)
            VALUES %s
            """,
            records,
        )

        conn.commit()
        print(f"Saved {len(records)} battle samples for {winner_name} to database")
    except Exception as e:
        conn.rollback()
        print(f"Failed to save battle samples: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
