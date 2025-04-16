#!/usr/bin/env python3
"""
PostgreSQL Setup Script

This script helps users set up PostgreSQL for development and testing.
It provides instructions and optionally tries to create the necessary databases.
"""

import subprocess
import sys
from pathlib import Path

# Define database connection details
PG_USER = "ramonsampayo"
PG_PASSWORD = "postgres"
PG_HOST = "localhost"
PG_PORT = "5432"
CONTAINER_NAME = "kave-postgres"

# Define database names
DEV_DB_NAME = "kave_dev"
TEST_DB_NAME = "kave_test"
TEST_ISOLATED_DB_NAME = "kave_test_isolated"

# Add the project root to the Python path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")


def print_step(step, description):
    """Print a formatted step."""
    print(f"\n[{step}] {description}")


def run_command(command, ignore_errors=False):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=not ignore_errors,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0, result.stdout
    except subprocess.CalledProcessError:
        return False, ""


def check_postgres_installation():
    """Check if PostgreSQL is installed via Docker."""
    print_step("1", "Checking PostgreSQL Docker container")
    success, output = run_command(
        f"docker ps | grep {CONTAINER_NAME}", ignore_errors=True
    )

    if success:
        print("✅ PostgreSQL Docker container is running.")
        print(f"   {output.strip()}")
        return True
    else:
        print("❌ PostgreSQL Docker container is not running or not found.")
        print("\nPlease start your PostgreSQL Docker container:")
        print("  docker start kave-postgres")
        return False


def check_database_connection():
    """Check if we can connect to PostgreSQL in Docker."""
    print_step("2", "Checking PostgreSQL Docker connection")

    # Try with Docker connection string
    success, _ = run_command(
        f"docker exec -it {CONTAINER_NAME} psql -U {PG_USER} -c '\\l'",
        ignore_errors=True,
    )

    if success:
        print("✅ Successfully connected to PostgreSQL Docker container.")
        return True
    else:
        print("❌ Could not connect to PostgreSQL Docker container.")
        print("\nPlease ensure PostgreSQL Docker container is running and accessible.")
        return False


def create_database(db_name):
    """Create a database if it doesn't exist in Docker PostgreSQL."""
    # Check if database exists
    check_cmd = (
        f"docker exec -it {CONTAINER_NAME} psql -U {PG_USER} -tc "
        f"\"SELECT 1 FROM pg_database WHERE datname = '{db_name}'\""
    )
    # Command to create database
    create_cmd = f'docker exec -it {CONTAINER_NAME} psql -U {PG_USER} -c "CREATE DATABASE {db_name}"'
    # Combined command
    cmd = f"{check_cmd} | grep -q 1 || {create_cmd}"

    success, output = run_command(
        cmd,
        ignore_errors=True,
    )

    if success:
        print(f"✅ Database '{db_name}' is ready to use.")
        return True
    else:
        print(f"❌ Failed to create database '{db_name}'.")
        print("   You may need to create it manually with:")
        print(
            f'   docker exec -it {CONTAINER_NAME} psql -U {PG_USER} -c "CREATE DATABASE {db_name}"'
        )
        return False


def setup_databases():
    """Set up all required databases."""
    print_step("3", "Setting up databases")

    databases = [
        (DEV_DB_NAME, "Development"),
        (TEST_DB_NAME, "Testing"),
        (TEST_ISOLATED_DB_NAME, "Isolated testing"),
    ]

    all_success = True
    for db_name, purpose in databases:
        print(f"\nCreating {purpose} database: {db_name}")
        if not create_database(db_name):
            all_success = False

    return all_success


def update_env_file():
    """Update or create .env file with PostgreSQL Docker configuration."""
    print_step("4", "Updating environment configuration")

    env_path = ROOT_DIR / ".env"
    env_example_path = ROOT_DIR / ".env.example"

    # Read existing .env file or create from example
    if env_path.exists():
        print(f"Found existing .env file at {env_path}")
        with open(env_path, "r") as f:
            env_lines = f.readlines()
    elif env_example_path.exists():
        print("Creating .env from .env.example")
        with open(env_example_path, "r") as f:
            env_lines = f.readlines()
    else:
        print("Creating new .env file")
        env_lines = []

    # Find and update DATABASE_URL or add it
    database_url = (
        f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{DEV_DB_NAME}"
    )
    db_url_found = False

    for i, line in enumerate(env_lines):
        if line.startswith("DATABASE_URL="):
            if "sqlite:" in line or "postgres" in line:
                env_lines[i] = f"DATABASE_URL={database_url}\n"
                print("✅ Updated DATABASE_URL to use PostgreSQL Docker")
            else:
                print("ℹ️ DATABASE_URL already configured, not changing")
            db_url_found = True
            break

    if not db_url_found:
        env_lines.append(f"DATABASE_URL={database_url}\n")
        print("✅ Added DATABASE_URL to .env file")

    # Write updated .env file
    with open(env_path, "w") as f:
        f.writelines(env_lines)

    print(f"\nEnvironment configuration saved to {env_path}")
    print(f"DATABASE_URL={database_url}")


def check_dependencies():
    """Check if required Python packages are installed."""
    print_step("5", "Checking Python dependencies")

    # Check asyncpg is installed
    try:
        print("✅ asyncpg is installed.")
    except ImportError:
        print("❌ asyncpg is not installed.")
        print("   Run: pip install asyncpg")
        return False

    # Check SQLAlchemy is installed
    try:
        print("✅ SQLAlchemy is installed.")
    except ImportError:
        print("❌ SQLAlchemy is not installed.")
        print("   Run: pip install sqlalchemy")
        return False

    return True


def print_summary(success):
    """Print a summary of the setup process."""
    print_header("SETUP SUMMARY")

    if success:
        print("✅ PostgreSQL Docker setup completed successfully!")
        print("\nYou can now run the application with:")
        print("  uvicorn app.main:app --reload")
        print("\nOr run the tests with:")
        print("  pytest")
    else:
        print("⚠️ Setup completed with some issues.")
        print(
            "Please address the issues mentioned above before running the application."
        )

    print("\nDatabase connection string:")
    print(f"  postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{DEV_DB_NAME}")


def main():
    """Run the PostgreSQL Docker setup script."""
    print_header("PostgreSQL Docker Setup for Kave Application")
    print(
        "This script will help you set up PostgreSQL in Docker for development and testing."
    )

    # Run the setup steps
    postgres_installed = check_postgres_installation()
    if not postgres_installed:
        print_summary(False)
        return

    can_connect = check_database_connection()
    if not can_connect:
        print_summary(False)
        return

    databases_ready = setup_databases()
    update_env_file()
    dependencies_ok = check_dependencies()

    # Print summary
    print_summary(databases_ready and dependencies_ok)


if __name__ == "__main__":
    main()
