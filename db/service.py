import os
import time
from datetime import datetime, timezone

import psycopg2
from dotenv import load_dotenv

from misc.git import get_code_link_at_commit, get_solution_code_link

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
CACHE_TTL_SECONDS = 120
_cache = {}


def _get_or_set_cache(key, loader):
    now = time.monotonic()
    entry = _cache.get(key)
    if entry:
        ts, data = entry
        if now - ts < CACHE_TTL_SECONDS:
            return data
    data = loader()
    _cache[key] = (now, data)
    return data


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


def get_leaderboard_rank_and_model_latest_session():
    """
    Get rank and model_name from negotiations_leaderboard_latest.
    Returns a list of dictionaries with rank and model_name.
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT rank, model_name
            FROM negotiations_leaderboard_latest
            ORDER BY rank;
            """
        )
        rows = cursor.fetchall()
        results = [
            {
                "rank": row[0],
                "model_name": row[1],
            }
            for row in rows
        ]
    finally:
        cursor.close()
        conn.close()

    return results


def get_negotiations_leaderboard_latest():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    def loader():
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT rank, model_name, profit_percentage, max_possible_profit, total_profit, code_link
                FROM negotiations_leaderboard_latest
                ORDER BY rank;
                """
            )
            rows = cursor.fetchall()
            cursor.execute("SELECT MAX(timestamp) FROM negotiations;")
            latest_timestamp_row = cursor.fetchone()
            latest_timestamp = latest_timestamp_row[0] if latest_timestamp_row else None
            return {
                "rows": [
                    {
                        "rank": row[0],
                        "model_name": row[1],
                        "profit_percentage": float(row[2]),
                        "max_possible_profit": float(row[3]),
                        "total_profit": float(row[4]),
                        "code_link": row[5],
                    }
                    for row in rows
                ],
                "latest_timestamp": latest_timestamp,
            }
        finally:
            cursor.close()
            conn.close()

    return _get_or_set_cache("negotiations_leaderboard_latest", loader)


def get_negotiations_leaderboard_all():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    def loader():
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT rank, model_name, profit_percentage, max_possible_profit, total_profit
                FROM negotiations_leaderboard
                ORDER BY rank;
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "rank": row[0],
                    "model_name": row[1],
                    "profit_percentage": float(row[2]),
                    "max_possible_profit": float(row[3]),
                    "total_profit": float(row[4]),
                    "code_link": get_solution_code_link(row[1]),
                }
                for row in rows
            ]
        finally:
            cursor.close()
            conn.close()

    return _get_or_set_cache("negotiations_leaderboard_all", loader)


def get_samples(commit_hash):
    """
    Get all session_samples records filtered by commit_hash.
    Returns a list of dictionaries with id, model_name, opponent_model_name, data, and commit_hash.
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, model_name, opponent_model_name, data, commit_hash
            FROM session_samples
            WHERE commit_hash = %s;
            """,
            (commit_hash,),
        )
        rows = cursor.fetchall()
        results = [
            {
                "id": row[0],
                "model_name": row[1],
                "opponent_model_name": row[2],
                "data": row[3],
                "commit_hash": row[4],
            }
            for row in rows
        ]
    finally:
        cursor.close()
        conn.close()

    return results


def save_battle_results(results: dict, max_possible_profit: int, commit_hash: str, top_model_name: str):
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
                if model_name == top_model_name:
                    code_link = "No new solution was generated for the previous top model."
                else:
                    code_link = get_code_link_at_commit(commit_hash, model_name)
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


def save_battle_samples(battle_scenarios: list, commit_hash: str):
    """
    Save all battle scenarios to the database.

    Args:
        battle_scenarios: List of scenario dictionaries. Each scenario contains:
            - 'scenario': the original scenario data with '{model_name} values' keys
            - 'outcome': 'deal', 'no_deal', or error type
            - '{model_x} profit': profit achieved by model_x
            - '{model_y} profit': profit achieved by model_y
            - 'turn_history': list of offers per round with '{model_name} offer' keys
        commit_hash: The git commit hash
    """
    import json

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    records = []
    for scenario_info in battle_scenarios:
        profit_keys = [k for k in scenario_info.keys() if k.endswith(" profit")]
        if len(profit_keys) != 2:
            continue
        
        model_x = profit_keys[0].replace(" profit", "")
        model_y = profit_keys[1].replace(" profit", "")
        
        data = {
            "scenario": scenario_info["scenario"],
            "outcome": scenario_info["outcome"],
            f"{model_x} profit": scenario_info[f"{model_x} profit"],
            f"{model_y} profit": scenario_info[f"{model_y} profit"],
            "turn_history": scenario_info["turn_history"],
        }
        data_json = json.dumps(data)

        records.append((model_x, model_y, data_json, commit_hash))

    if not records:
        print("No battle scenarios to save")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        # Bulk insert all records in a single call
        from psycopg2.extras import execute_values

        execute_values(
            cursor,
            """
            INSERT INTO session_samples (model_name, opponent_model_name, data, commit_hash)
            VALUES %s
            """,
            records,
        )

        conn.commit()
        print(f"Saved {len(records)} battle samples to database")
    except Exception as e:
        conn.rollback()
        print(f"Failed to save battle samples: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
