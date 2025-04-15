# Webhook Secret Refactoring Implementation Plan

## Overview

**Issue**: Querying all organizations to check for duplicate webhook secrets on create/update is inefficient and potentially insecure if secrets are ever logged.

**Solution**: Add a unique database constraint to the `mandrill_webhook_secret` column in the organizations table and handle potential `IntegrityError` exceptions at the service/API layer.

## Implementation Steps

### 1. Create Alembic Migration

1. Generate a new Alembic migration:
   ```bash
   alembic revision -m "add_unique_constraint_to_mandrill_webhook_secret"
   ```

2. Edit the generated migration file:
   ```python
   # In the upgrade function
   def upgrade() -> None:
       op.create_unique_constraint(
           'uq_organizations_mandrill_webhook_secret', 
           'organizations', 
           ['mandrill_webhook_secret']
       )

   # In the downgrade function
   def downgrade() -> None:
       op.drop_constraint(
           'uq_organizations_mandrill_webhook_secret', 
           'organizations', 
           type_='unique'
       )
   ```

3. Apply the migration:
   ```bash
   alembic upgrade head
   ```

### 2. Update Organization Service

1. Modify `app/services/organization_service.py`:
   - Keep the `get_organization_by_webhook_secret` method (still useful for lookups)
   - Update the `create_organization` and `update_organization` methods to allow the database to handle uniqueness

### 3. Update Organization API Endpoints

1. Modify `app/api/v1/endpoints/organizations.py`:
   - Remove the pre-emptive `get_organization_by_webhook_secret` checks in:
     - `create_organization` endpoint
     - `update_organization` endpoint
     - `patch_organization` endpoint
   
   - Add exception handling for SQLAlchemy's `IntegrityError` around `db.commit()`:

   ```python
   from sqlalchemy.exc import IntegrityError
   
   # In create_organization endpoint:
   try:
       organization = await service.create_organization(data)
       await db.commit()
       return OrganizationResponse.model_validate(organization)
   except IntegrityError as e:
       await db.rollback()
       if "mandrill_webhook_secret" in str(e):
           raise HTTPException(
               status_code=status.HTTP_409_CONFLICT,
               detail="Organization with the same webhook secret already exists. This is a security risk."
           )
       raise e
   
   # Similar updates for update_organization and patch_organization
   ```

### 4. Update Tests

1. Update `app/tests/test_unit/test_api/test_organization_endpoints.py`:
   - Ensure tests for duplicate webhook secrets still work correctly
   - Verify the 409 Conflict response is still returned when attempting to create/update with duplicate secrets
   - Add test cases specifically checking that IntegrityError handling works as expected

2. Update any other tests that might be affected by this change.

### 5. Testing

1. Manually test the API endpoints to verify:
   - Creating an organization with a unique webhook secret succeeds
   - Creating an organization with a duplicate webhook secret fails with 409
   - Updating an organization with a unique webhook secret succeeds
   - Updating an organization with a duplicate webhook secret fails with 409

### 6. Documentation

1. Update API documentation to reflect that webhook secrets must be unique
2. Document the error handling behavior

## Benefits

- **Performance**: Eliminates unnecessary database queries before each create/update operation
- **Security**: Reduces exposure of webhook secrets in application code
- **Reliability**: Database-level constraints guarantee data integrity
- **Code Quality**: Simplified logic in the API layer, removing redundant checks

## Timeline

- Estimated implementation time: 2-3 hours
- Testing: 1 hour
- Documentation updates: 30 minutes

## Notes

- This refactoring relies on database-level constraints rather than application-level checks
- The change is backward compatible in terms of API behavior
- No changes to client code should be required 