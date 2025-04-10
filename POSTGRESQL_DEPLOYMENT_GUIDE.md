# PostgreSQL Database Configuration for Heroku

This document provides a comprehensive guide for setting up and testing PostgreSQL for the Kave project on Heroku. These steps are crucial for preparing your application for deployment.

## Why PostgreSQL for Heroku

Heroku strongly recommends using PostgreSQL for several reasons:

1. **Officially Supported**: PostgreSQL is Heroku's officially supported and preferred database.
2. **Managed Service**: Heroku Postgres is a fully managed database service with automated backups, monitoring, and scaling.
3. **Data Persistence**: Unlike the ephemeral filesystem, Heroku Postgres provides persistent data storage.
4. **Performance**: Optimized for cloud environments with excellent performance characteristics.

## Testing PostgreSQL Locally

Before deploying to Heroku, it's recommended to test your application with PostgreSQL locally to ensure compatibility.

### Setting Up PostgreSQL Locally

1. **Install PostgreSQL**:
   - macOS: `brew install postgresql`
   - Linux: `sudo apt install postgresql`
   - Windows: Download from [PostgreSQL website](https://www.postgresql.org/download/windows/)

2. **Start PostgreSQL Service**:
   - macOS: `brew services start postgresql@14`
   - Linux: `sudo systemctl start postgresql`
   - Windows: Service should start automatically

3. **Create a Test Database**:
   ```bash
   createdb kave_test
   ```

4. **Configure Your Environment**:
   Update your `.env` file to use PostgreSQL instead of SQLite:
   ```
   DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/kave_test
   ```
   Replace `username` and `password` with your PostgreSQL credentials.

### Testing PostgreSQL Connection

You can use the provided script to test your PostgreSQL connection:

```bash
./pg_connection_test.py
```

The script will:
1. Connect to the PostgreSQL database
2. Create a test table
3. Insert, query, and delete a test record
4. Drop the test table
5. Report success or failure

## Handling Heroku PostgreSQL Specifics

### Database URL Format

Heroku provides a `DATABASE_URL` environment variable in the format:
```
postgres://username:password@hostname:port/database_name
```

Our application handles this automatically by:
1. Checking for `postgres://` prefix
2. Converting it to `postgresql://` required by SQLAlchemy

### Connection Pooling

Heroku has connection limits based on your database plan. The application is configured to:
- Use a moderate pool size of connections
- Handle connection recycling appropriately
- Properly close connections when not in use

### Migrations with Alembic

We've configured Alembic to handle database migrations on Heroku:
1. The Procfile's `release` phase runs `alembic upgrade head`
2. This ensures all migrations are applied before the application starts
3. Alembic is configured to use Heroku's `DATABASE_URL` environment variable

## Using Heroku PostgreSQL Add-on

When deploying to Heroku, you'll need to add the PostgreSQL add-on:

```bash
heroku addons:create heroku-postgresql:hobby-dev
```

This will:
1. Create a PostgreSQL database instance
2. Set the `DATABASE_URL` environment variable automatically
3. Provide access to additional Heroku PostgreSQL commands and features

## Verifying PostgreSQL on Heroku

After deployment, verify your PostgreSQL setup:

1. Check connection with the test script:
   ```bash
   heroku run python pg_connection_test.py
   ```

2. Check database migrations:
   ```bash
   heroku run alembic current
   ```

3. Inspect database tables:
   ```bash
   heroku pg:psql
   # Then in psql:
   \dt
   ```

## Backup and Recovery

Heroku provides built-in backup capabilities:

1. **Manual Backup**:
   ```bash
   heroku pg:backups:capture
   ```

2. **Schedule Automatic Backups**:
   ```bash
   heroku pg:backups:schedule DATABASE_URL --at '02:00 America/New_York'
   ```

3. **Download Backup**:
   ```bash
   heroku pg:backups:download
   ```

## Troubleshooting

### Common Issues

1. **Connection Errors**:
   - Check the `DATABASE_URL` format
   - Verify the Heroku PostgreSQL add-on is provisioned
   - Test connectivity with the pg_connection_test.py script

2. **Migration Failures**:
   - Check the Alembic migration files
   - Verify that your models are compatible with PostgreSQL
   - Check the Heroku logs after deployment

3. **Performance Issues**:
   - Review query patterns in your application
   - Consider adding indexes to frequently queried columns
   - Monitor connection pool usage

### Debugging Commands

```bash
# Check PostgreSQL info
heroku pg:info

# Check running queries
heroku pg:ps

# View logs with database messages
heroku logs --tail --source app
```
