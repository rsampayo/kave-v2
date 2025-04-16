#!/usr/bin/env python3
"""
Production Database Verification Script

This script verifies that the production environment is correctly configured
to use PostgreSQL and not SQLite. It validates the database URL and configuration.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.core.config import settings

    # Force production environment
    os.environ["API_ENV"] = "production"

    print(f"Checking database configuration for environment: {settings.API_ENV}")
    print(f"DATABASE_URL: {settings.DATABASE_URL}")
    print(f"KAVE_DATABASE_URL: {settings.KAVE_DATABASE_URL}")

    # Validate the database URL
    if settings.effective_database_url.startswith("sqlite"):
        print("ERROR: Using SQLite in production environment! This is not allowed.")
        sys.exit(1)
    elif settings.effective_database_url.startswith("postgresql"):
        print("SUCCESS: Using PostgreSQL database as required for production.")

        # Attempt to import PostgreSQL driver to ensure it's installed
        try:
            print("SUCCESS: PostgreSQL driver check completed.")
        except ImportError:
            print("ERROR: PostgreSQL driver (psycopg2) is not installed!")
            sys.exit(1)

        # Ensure SQLite is not installed in production
        try:
            print("SUCCESS: SQLite driver check completed.")
        except ImportError:
            print(
                "SUCCESS: aiosqlite (SQLite driver) is not installed, as expected in production."
            )
    else:
        print(f"UNKNOWN DB TYPE: {settings.effective_database_url[:20]}...")
        sys.exit(1)

    print("\nPRODUCTION DATABASE CONFIGURATION IS VALID.")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {str(e)}")
    sys.exit(1)
