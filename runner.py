from db.db_setup import setup_database
from dotenv import load_dotenv
import job
import os
import time

# Load environment variables from .env file
load_dotenv()

if __name__ == "__main__":

    # Initialize database on startup
    setup_database()
    print("Database setup complete. Application is running...")
    try:
        sleep_seconds = int(os.getenv("SLEEP_SECONDS", "3600"))
    except:
        sleep_seconds = 3600

    while True:
        start = time.time()

        job.main()

        elapsed = time.time() - start
        remaining = max(0, sleep_seconds - elapsed)
        print(
            f"Sleeping for {remaining} seconds. {start} start time. {elapsed} seconds elapsed during job execution. {sleep_seconds} seconds total interval.",
        )
        time.sleep(remaining)
