#!/usr/bin/env python
import os
import sys
from sqlalchemy import create_engine, text

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
            # 1. Get current version
            version_check = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).fetchone()
            
            if not version_check:
                print("Error: alembic_version table not found or empty")
                sys.exit(1)
            
            current_version = version_check[0]
            target_version = 'daf60e35187d'
            
            print(f"Current version: {current_version}")
            
            # 2. Update the alembic version
            conn.execute(
                text("UPDATE alembic_version SET version_num = :new_version"),
                {"new_version": target_version}
            )
            
            # 3. Try to add the constraint if it doesn't exist
            try:
                conn.execute(text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = 'uq_organizations_mandrill_webhook_secret'
                        ) THEN
                            ALTER TABLE organizations 
                            ADD CONSTRAINT uq_organizations_mandrill_webhook_secret
                            UNIQUE (mandrill_webhook_secret);
                        END IF;
                    END
                    $$;
                """))
                print("Constraint check completed")
            except Exception as e:
                print(f"Warning: Constraint operation failed: {e}")
                # Continue anyway
            
            print(f"Successfully updated alembic version to {target_version}")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1) 