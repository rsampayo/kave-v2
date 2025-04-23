# Step 3: Generate & Apply Database Migration

## Goal
Update the database schema to include the new `attachment_text_content` table using Alembic.

## TDD
This step doesn't use direct TDD as it involves working with Alembic to generate and apply migrations. However, the correctness of the migration will be validated in subsequent testing steps that require the database schema.

## Implementation

### 1. Generate the Migration

Run the following command to generate a migration file based on the changes to your SQLAlchemy models:

```bash
alembic revision --autogenerate -m "Add AttachmentTextContent model"
```

This will create a new migration file in the `alembic/versions/` directory.

### 2. Review the Migration

**Crucially, review** the generated migration script in `alembic/versions/`. Verify that it correctly:

- Creates the `attachment_text_content` table with all specified columns:
  - `id` (primary key)
  - `attachment_id` (foreign key to `attachments.id`)
  - `page_number` (integer, non-nullable)
  - `text_content` (text, nullable)
- Includes the foreign key constraint to `attachments.id` with `ondelete="CASCADE"`
- Creates necessary indexes (especially on `attachment_id` and `id`)

Example of what to look for in the migration file:

```python
# Example snippet from the migration file (your actual file will have a unique identifier)
def upgrade():
    # ... existing operations
    op.create_table('attachment_text_content',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('attachment_id', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attachment_text_content_attachment_id'), 'attachment_text_content', ['attachment_id'], unique=False)
    op.create_index(op.f('ix_attachment_text_content_id'), 'attachment_text_content', ['id'], unique=False)
    # ... any other operations
```

If the generated migration is not correct, you may need to adjust your model definitions and regenerate the migration.

### 3. Apply the Migration

Run the following command to apply the migration to your local development database:

```bash
alembic upgrade head
```

This will create the new table in your database according to the migration script.

### 4. Verify the Migration

You can verify the migration by checking the database schema directly using a database client or by running:

```bash
# If using PostgreSQL
psql your_database_name -c "\d attachment_text_content"

# Or using SQLite
sqlite3 your_database_file ".schema attachment_text_content"
```

## Quality Check
The quality check for this step is primarily the manual review of the migration script, but you should also ensure:

- The migration script follows the project's code style
- The migration is reversible if possible (has a proper `downgrade()` function)
- Any manual adjustments to the migration script are properly documented in comments

## Testing
No automated tests are required specifically for this step, but you should verify that the migration applied successfully and that the database schema matches your expectations.

## Self-Verification Checklist
- [ ] Did Alembic generate a migration script?
- [ ] Does the migration script look correct (all columns, constraints, indexes)?
- [ ] Did `alembic upgrade head` run without errors?
- [ ] Does the `attachment_text_content` table exist in your database?
- [ ] Does the table have the correct structure (columns, types, constraints)?
- [ ] Is the foreign key relationship to `attachments` set up correctly?

After completing this step, stop and request approval before proceeding to Step 4. 