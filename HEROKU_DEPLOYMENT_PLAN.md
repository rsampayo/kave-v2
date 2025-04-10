# Kave Project: Heroku Deployment Plan

This document outlines the step-by-step process to prepare the Kave project for deployment to Heroku. Each step is detailed with specific commands and explanations.

## 1. Set Up Proper Alembic Configuration ✅

The project is currently missing a standard Alembic setup, which is needed for the `alembic upgrade head` command in the Procfile to work correctly.

### 1.1. Install Alembic (if not already installed) ✅

```bash
pip install alembic
```

**Implementation Note**: Alembic was already installed via requirements/base.txt.

### 1.2. Initialize Alembic ✅

```bash
alembic init alembic
```

This will create an `alembic` directory and `alembic.ini` file in the root of the project.

**Implementation Note**: Successfully initialized Alembic structure.

### 1.3. Configure Alembic ✅

Edit `alembic.ini`:

```bash
# Replace the default sqlalchemy.url line with:
sqlalchemy.url = postgresql://user:pass@localhost/dbname
# This will be overridden by the env.py file
```

Edit `alembic/env.py` to connect it to your SQLAlchemy models and use the database URL from the application config:

```python
# Add these imports at the top
import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import Base  # Your SQLAlchemy Base
from app.core.config import settings

# Inside run_migrations_online and run_migrations_offline functions,
# replace the config.get_main_option("sqlalchemy.url") with:
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Ensure target_metadata is set to Base.metadata
target_metadata = Base.metadata
```

**Implementation Note**: Enhanced the env.py file to support async database connections, which was necessary because the project uses SQLAlchemy's async API. Added proper type annotations to satisfy mypy requirements.

### 1.4. Create Initial Migration ✅

**Implementation Note**: Created initial migration to capture the existing schema. Then added a test migration that adds a `test_column` to the `Email` model to verify the migration system works correctly. Used `alembic stamp head` to mark the initial migration as applied since the tables already existed.

## 2. Set Up Requirements Files with pip-tools ✅

Heroku looks for a requirements.txt file in the root directory. We've implemented a structured dependency management approach using pip-tools.

### 2.1. Implement pip-tools dependency management ✅

```bash
# Install pip-tools
pip install pip-tools

# Create source .in files
touch requirements/base.in
touch requirements/integrations.in
touch requirements/dev.in

# Populate .in files with direct dependencies
# (See requirements/base.in, requirements/integrations.in, requirements/dev.in)

# Generate pinned .txt files 
pip-compile requirements/base.in --output-file=requirements/base.txt
pip-compile requirements/integrations.in --output-file=requirements/integrations.txt
pip-compile requirements/dev.in --output-file=requirements/dev.txt
```

**Implementation Note**: Created a structured dependency management system using pip-tools. The root `requirements.txt` now references `requirements/integrations.txt` to ensure Heroku installs all the necessary production dependencies with pinned versions. This approach follows best practices for Python dependency management as detailed in `DEPENDENCY_MANAGEMENT.md`.

### 2.2. Create a root requirements.txt file for Heroku ✅

```bash
# Create a simple root requirements.txt that references the integrations.txt file
echo "-r requirements/integrations.txt" > requirements.txt
```

**Implementation Note**: Updated the root requirements.txt file to reference requirements/integrations.txt instead of duplicating all dependencies, which is cleaner and easier to maintain.

## 3. Configure PostgreSQL for Production ✅

Ensure your application works correctly with PostgreSQL in production.

### 3.1. Test with PostgreSQL locally (optional but recommended) ✅

```bash
# Set up a local PostgreSQL database for testing
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/kave_test
```

**Implementation Note**: Set up a local PostgreSQL database for testing. Created `pg_connection_test.py` script to verify database connectivity and operations. Successfully tested basic database operations using PostgreSQL instead of SQLite. Also created a comprehensive guide in `POSTGRESQL_DEPLOYMENT_GUIDE.md` for PostgreSQL configuration on Heroku.

### 3.2. Ensure DATABASE_URL validation handles Heroku's format ✅

The settings class should handle the conversion from postgres:// to postgresql://, which is already implemented in your code.

**Implementation Note**: Verified that the Settings class in app/core/config.py correctly handles the conversion from postgres:// to postgresql://. Tested this functionality in the pg_connection_test.py script.

## 4. Configure File Storage for Production ✅

Heroku has an ephemeral filesystem, so local file storage won't persist. Your code appears to have S3 support.

### 4.1. Ensure S3 storage is properly implemented ✅

Review the S3 storage implementation in your code and confirm it works correctly.

**Implementation Note**: Created an S3 connection test script (`s3_connection_test.py`) to verify that the S3 storage implementation works correctly. The script tests uploading, downloading, and deleting a file from S3 using the project's configuration. Also created a comprehensive S3 deployment guide in `S3_DEPLOYMENT_GUIDE.md` with detailed instructions for setting up S3 for production use.

### 4.2. Make sure environment variables are correctly set up for S3 ✅

In your `app/core/config.py`, you should have:
- S3_BUCKET_NAME
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION
- USE_S3_STORAGE

**Implementation Note**: Updated the `.env.example` file to include all required S3 environment variables. Verified that the `app/core/config.py` settings class correctly loads and validates these variables.

## 5. Set Up Heroku

### 5.1. Install Heroku CLI (if not already installed)

```bash
# For macOS
brew install heroku/brew/heroku

# For other systems, see Heroku documentation
```

### 5.2. Create a Heroku app

```bash
heroku login
heroku create kave-app  # Replace 'kave-app' with your preferred app name
```

### 5.3. Add Heroku PostgreSQL add-on

```bash
heroku addons:create heroku-postgresql:hobby-dev
```

### 5.4. Configure environment variables

```bash
# API Settings
heroku config:set API_ENV=production
heroku config:set DEBUG=False
heroku config:set SECRET_KEY=your_secure_secret_key

# MailChimp settings
heroku config:set MAILCHIMP_API_KEY=your_mailchimp_api_key
heroku config:set MAILCHIMP_WEBHOOK_SECRET=your_mailchimp_webhook_secret

# S3 Settings (if using S3 for attachments)
heroku config:set S3_BUCKET_NAME=your_s3_bucket_name
heroku config:set AWS_ACCESS_KEY_ID=your_aws_access_key_id
heroku config:set AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
heroku config:set AWS_REGION=your_aws_region
heroku config:set USE_S3_STORAGE=True

# Additional settings
heroku config:set SQL_ECHO=False
```

## 6. Verify CORS Configuration

### 6.1. Update CORS settings in app/main.py

For production, you should restrict CORS origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],  # Replace with actual domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 7. Prepare for Deployment

### 7.1. Make sure all changes are committed

```bash
git add .
git commit -m "Prepare for Heroku deployment"
```

### 7.2. Deploy to Heroku

```bash
git push heroku main  # Or git push heroku master, depending on your branch name
```

### 7.3. Run migrations manually for the first deployment (if needed)

```bash
heroku run alembic upgrade head
```

## 8. Verify Deployment

### 8.1. Open the app

```bash
heroku open
```

### 8.2. Check logs for any errors

```bash
heroku logs --tail
```

### 8.3. Test the API endpoints

Use a tool like Postman or curl to test that your API endpoints are working correctly.

## 9. Set Up Continuous Deployment (Optional)

### 9.1. Connect Heroku to GitHub for automatic deployments

1. Go to the Heroku Dashboard
2. Select your app
3. Go to the Deploy tab
4. Connect to GitHub
5. Enable automatic deploys from your main/master branch

## 10. Additional Considerations

### 10.1. Scaling

If your application needs more resources, you can scale your Heroku dynos:

```bash
heroku ps:scale web=1:standard-1x
```

### 10.2. Monitoring

Set up application monitoring with Heroku's built-in metrics or add New Relic for more detailed monitoring.

### 10.3. Backup strategy

Set up regular database backups using Heroku's PG Backups:

```bash
heroku pg:backups:schedule DATABASE_URL --at '02:00 America/New_York'
```

### 10.4. Custom domain

Configure a custom domain for your application:

```bash
heroku domains:add www.yourdomain.com
```

Follow Heroku's instructions for setting up DNS records. 