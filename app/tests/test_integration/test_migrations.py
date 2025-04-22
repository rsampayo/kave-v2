"""Test migration integrity after refactoring."""

import glob
from pathlib import Path


def test_migration_refactoring() -> None:
    """Test if migrations have been refactored correctly."""
    # Get the location of all migration files
    project_root = Path(__file__).parent.parent.parent.parent
    migrations_dir = project_root / "alembic" / "versions"

    # Get all migration files - not used directly but kept for context
    _ = glob.glob(str(migrations_dir / "*.py"))

    critical_migrations = [
        "daf60e35187d_fix_unique_constraint_for_postgres.py",
        "3d17b3a3f001_add_unique_constraint_to_mandrill_.py",
        "7b40d1074b24_add_unique_constraint_to_mandrill_.py",
    ]

    # Check each critical migration file
    for migration_file in critical_migrations:
        file_path = migrations_dir / migration_file
        assert file_path.exists(), f"Migration file {migration_file} should exist"

        with open(file_path, "r") as f:
            content = f.read()

            # Check that the migration files have been refactored correctly
            if "daf60e35187d" in migration_file:
                # Should have proper logging instead of print
                assert (
                    "logger.warning" in content
                ), "Should use logger.warning instead of print"
                assert "import logging" in content, "Should import logging module"
                # Should not have manual commit calls
                assert (
                    'conn.execute(sa.text("COMMIT"))' not in content
                ), "Should not execute manual COMMIT"
                assert (
                    "# Commit what we've done" not in content
                ), "Should not contain COMMIT comment"

            elif "3d17b3a3f001" in migration_file or "7b40d1074b24" in migration_file:
                # Should have documentation about being superseded
                assert (
                    "superseded" in content.lower()
                ), "Should document that it was superseded"
                assert "import logging" in content, "Should import logging module"

            # All migrations should have proper logging configured
            assert (
                'logger = logging.getLogger("alembic")' in content
            ), "Should configure logger properly"

    # All tests pass if we get here
