#!/usr/bin/env python
import os
import sys

from sqlalchemy import create_engine, text


def main():
    """
    Script to manually update the database version in alembic and
    add the unique constraint that was causing issues.
    """
    # Get database URL from environment
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        print("Error: DATABASE_URL environment variable is not set.")
        sys.exit(1)

    # Fix PostgreSQL URL format for SQLAlchemy 1.4+
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    try:
        # Create engine and connection
        engine = create_engine(database_url)

        with engine.connect() as conn:
            # Start a transaction
            with conn.begin():
                # 1. Check if the alembic_version table exists and has the expected current version
                version_check = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).fetchone()

                if not version_check:
                    print("Error: alembic_version table not found or empty")
                    return

                current_version = version_check[0]
                expected_version = "443a8e83492a"
                target_version = "daf60e35187d"

                if current_version != expected_version:
                    print(
                        f"Warning: Current version {current_version} doesn't match "
                        f"expected version {expected_version}"
                    )
                    response = input("Continue anyway? (y/n): ")
                    if response.lower() != "y":
                        return

                # 2. Update the alembic version
                conn.execute(
                    text("UPDATE alembic_version SET version_num = :new_version"),
                    {"new_version": target_version},
                )

                # 3. Check if the constraint already exists
                constraint_exists = (
                    conn.execute(
                        text(
                            """
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_organizations_mandrill_webhook_secret'
                """
                        )
                    ).scalar()
                    is not None
                )

                if not constraint_exists:
                    try:
                        # 4. Add the unique constraint
                        conn.execute(
                            text(
                                """
                            ALTER TABLE organizations
                            ADD CONSTRAINT uq_organizations_mandrill_webhook_secret
                            UNIQUE (mandrill_webhook_secret);
                        """
                            )
                        )
                        print("Successfully added unique constraint")
                    except Exception as e:
                        print(f"Warning: Couldn't add constraint: {e}")
                        # Continue anyway to update the version

                print(
                    f"Successfully updated alembic version from {current_version} to {target_version}"
                )

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
