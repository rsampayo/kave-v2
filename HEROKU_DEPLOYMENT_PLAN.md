# Kave Project: Heroku Deployment Plan

This document outlines the step-by-step process to prepare the Kave project for deployment to Heroku. Each step is detailed with specific commands and explanations.

## 1. Set Up Proper Alembic Configuration

The project is currently missing a standard Alembic setup, which is needed for the `alembic upgrade head` command in the Procfile to work correctly.

### 1.1. Install Alembic (if not already installed)

```bash
pip install alembic
```

### 1.2. Initialize Alembic

```bash
alembic init alembic
```

This will create an `alembic` directory and `alembic.ini` file in the root of the project.

### 1.3. Configure Alembic

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

### 1.4. Migrate Your Custom Migrations (Optional)

If your custom migrations in `app/db/migrations/` need to be incorporated into Alembic:

1. Create a new migration:
```bash
alembic revision -m "initial_migration"
```

2. Edit the generated migration file to implement your custom migration logic.

## 2. Create Root Requirements.txt File

Heroku looks for a requirements.txt file in the root directory.

### 2.1. Create a new requirements.txt file in the project root

```bash
# Option 1: Reference existing requirements files
-r requirements/base.txt
-r requirements/integrations.txt

# Option 2: Copy/consolidate all dependencies into a single file
```

## 3. Configure PostgreSQL for Production

Ensure your application works correctly with PostgreSQL in production.

### 3.1. Test with PostgreSQL locally (optional but recommended)

```bash
# Set up a local PostgreSQL database for testing
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/kave_test
```

### 3.2. Ensure DATABASE_URL validation handles Heroku's format

The settings class should handle the conversion from postgres:// to postgresql://, which is already implemented in your code.

## 4. Configure File Storage for Production

Heroku has an ephemeral filesystem, so local file storage won't persist. Your code appears to have S3 support.

### 4.1. Ensure S3 storage is properly implemented

Review the S3 storage implementation in your code and confirm it works correctly.

### 4.2. Make sure environment variables are correctly set up for S3

In your `app/core/config.py`, you should have:
- S3_BUCKET_NAME
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION
- USE_S3_STORAGE

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