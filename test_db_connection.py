# test_db_connection.py
# Tests if Python can connect to numeris_db using .env credentials

from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text

# Load .env file from current directory
load_dotenv()

# Get the DATABASE_URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env file!")
    exit(1)

print(f"Using DATABASE_URL: {DATABASE_URL}")

try:
    # Create engine (connection factory)
    engine = create_engine(DATABASE_URL)

    # Test connection with a simple query
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1 AS test;"))
        row = result.fetchone()
        print("Connection successful!")
        print(f"Test query returned: {row}")
        print("PostgreSQL version info:")
        version_result = connection.execute(text("SELECT version();"))
        print(version_result.fetchone()[0])

    print("\nSUCCESS: You can now use this connection in your pipeline!")

except Exception as e:
    print("Connection FAILED!")
    print(f"Error details: {str(e)}")
    print("\nCommon fixes:")
    print("- Check if PostgreSQL service is running (Services app → postgresql-x64-XX)")
    print("- Verify password in .env (case-sensitive!)")
    print("- Ensure database name is 'numeris_db' (lowercase)")
    print("- Confirm port 5432 is open/not blocked")
    print("- Try connecting manually in pgAdmin first")
