import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment variables (should be set in caps)
DATABASE_URL = os.environ.get("DATABASE_URL")


def setup_database():
    """
    Set up the Supabase database with the required table, view, and policies.
    Only creates them if they don't already exist.
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set")

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        # Create table
        print("Creating table 'negociations'...")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS negociations (
                id BIGSERIAL PRIMARY KEY,
                model_name TEXT NOT NULL,
                negociations INTEGER NOT NULL,
                profit NUMERIC NOT NULL,
                code_link TEXT,
                timestamp TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        print("Table 'negociations' created or already exists.")

        # Create index on timestamp
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_negociations_timestamp ON negociations(timestamp);"
        )
        print("Index on timestamp created or already exists.")

        # Enable RLS
        cursor.execute("ALTER TABLE negociations ENABLE ROW LEVEL SECURITY;")
        print("RLS enabled.")

        # Create policy if it doesn't exist
        cursor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE tablename = 'negociations'
                    AND policyname = 'public_read_only'
                ) THEN
                    CREATE POLICY public_read_only ON negociations
                        FOR SELECT
                        TO anon, authenticated
                        USING (true);
                END IF;
            END $$;
            """
        )
        print("Public read-only policy created or already exists.")

        # Grant SELECT on table to anon and authenticated roles
        cursor.execute("GRANT SELECT ON negociations TO anon, authenticated;")
        print("Public read access granted to table.")

        # Create or replace view
        cursor.execute(
            """
            CREATE OR REPLACE VIEW negociations_leaderboard AS
            SELECT
                ROW_NUMBER() OVER (ORDER BY SUM(profit) / SUM(negociations) DESC) AS rank,
                model_name,
                SUM(negociations) AS negociations,
                SUM(profit) / SUM(negociations) AS avg_profit
            FROM negociations
            GROUP BY model_name
            ORDER BY avg_profit DESC;
            """
        )
        print("View 'negociations_leaderboard' created or replaced.")

        # Create or replace view for latest timestamp only
        cursor.execute(
            """
            CREATE OR REPLACE VIEW negociations_leaderboard_latest AS
            SELECT
                ROW_NUMBER() OVER (ORDER BY SUM(profit) / SUM(negociations) DESC) AS rank,
                model_name,
                SUM(negociations) AS negociations,
                SUM(profit) / SUM(negociations) AS avg_profit
            FROM negociations
            WHERE timestamp = (SELECT MAX(timestamp) FROM negociations)
            GROUP BY model_name
            ORDER BY avg_profit DESC;
            """
        )
        print("View 'negociations_leaderboard_latest' created or replaced.")

        # Grant SELECT on latest view to anon and authenticated roles
        cursor.execute(
            "GRANT SELECT ON negociations_leaderboard_latest TO anon, authenticated;"
        )
        print("Public read access granted to latest view.")

        # Grant SELECT on view to anon and authenticated roles
        cursor.execute(
            "GRANT SELECT ON negociations_leaderboard TO anon, authenticated;"
        )
        print("Public read access granted to view.")

        # Create player_data table
        print("Creating table 'player_data'...")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS player_data (
                id BIGSERIAL PRIMARY KEY,
                model_name TEXT NOT NULL,
                player_number INTEGER NOT NULL CHECK (player_number IN (0, 1)),
                data TEXT,
                commit_hash TEXT NOT NULL
            );
            """
        )
        print("Table 'player_data' created or already exists.")

        # Create index on commit_hash
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_player_data_commit_hash ON player_data(commit_hash);"
        )
        print("Index on commit_hash created or already exists.")

        print("Database setup completed successfully!")

    except Exception as e:
        print(f"Error during database setup: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    setup_database()
