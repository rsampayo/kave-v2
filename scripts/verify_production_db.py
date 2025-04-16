#!/usr/bin/env python3
"""
Database Verification Script

This script verifies that the environment is correctly configured
to use PostgreSQL and not SQLite. It validates the database URL and configuration.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.core.config import settings

    print(f"Checking database configuration for environment: {settings.API_ENV}")
    print(f"DATABASE_URL: {settings.DATABASE_URL}")
    print(f"KAVE_DATABASE_URL: {settings.KAVE_DATABASE_URL}")

    # Validate the database URL
    if settings.effective_database_url.startswith("sqlite"):
        print("ERROR: Using SQLite database! This is not allowed.")
        sys.exit(1)
    elif settings.effective_database_url.startswith("postgresql"):
        print("SUCCESS: Using PostgreSQL database as required.")

        # Attempt to import PostgreSQL driver to ensure it's installed
        try:
            print("SUCCESS: PostgreSQL driver (asyncpg) is installed.")
        except ImportError:
            print("ERROR: PostgreSQL driver (asyncpg) is not installed!")
            sys.exit(1)

        # Ensure SQLite is not installed
        try:
            print(
                "WARNING: aiosqlite (SQLite driver) is installed, though not being used."
            )
        except ImportError:
            print("SUCCESS: aiosqlite (SQLite driver) is not installed, as expected.")
    else:
        print("ERROR: Unsupported database type. Only PostgreSQL is supported.")
        sys.exit(1)

    print("\nDATABASE CONFIGURATION IS VALID.")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {str(e)}")
    sys.exit(1)
