# Kave Project: AWS Deployment Plan

This document outlines the step-by-step process to prepare the Kave project for deployment to AWS. Each step is detailed with specific commands and explanations.

## 1. Set Up Proper Alembic Configuration

Similar to the Heroku deployment, you need a standard Alembic setup for database migrations.

### 1.1. Install Alembic (if not already installed)

```bash
pip install alembic
```

### 1.2. Initialize Alembic

```bash
alembic init alembic
```

### 1.3. Configure Alembic

Edit `alembic.ini`:

```bash
# Replace the default sqlalchemy.url line with:
sqlalchemy.url = postgresql://user:pass@localhost/dbname
# This will be overridden by the env.py file
```

Edit `alembic/env.py` to connect to your SQLAlchemy models:

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

If you have custom migrations in `app/db/migrations/`:

1. Create a new migration:
```bash
alembic revision -m "initial_migration"
```

2. Edit the generated migration file to implement your custom migration logic.

## 2. Create Root Requirements.txt File

Create a consolidated requirements.txt file at the project root:

```bash
# Option 1: Reference existing requirements files
-r requirements/base.txt
-r requirements/integrations.txt

# Option 2: Copy/consolidate all dependencies into a single file
```

## 3. Configure AWS Services

### 3.1. Set Up AWS Account and Install AWS CLI

If you don't already have an AWS account, create one. Then install the AWS CLI:

```bash
# For macOS
brew install awscli

# For other systems, see AWS documentation
```

Configure AWS CLI:

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, region, and output format
```

### 3.2. Set Up an Amazon RDS PostgreSQL Database

1. Go to the AWS Management Console
2. Navigate to Amazon RDS
3. Create a new PostgreSQL database:
   - Choose PostgreSQL as your database engine
   - Select the appropriate tier (e.g., db.t3.micro for dev/test, larger for production)
   - Set up master username and password
   - Configure additional settings like VPC, subnet group, and security groups
   - Enable backups and encryption if needed

After creation, note the database endpoint, port, username, password, and database name.

### 3.3. Set Up Amazon S3 for File Storage

1. Go to the AWS Management Console
2. Navigate to Amazon S3
3. Create a new bucket:
   - Choose a unique bucket name
   - Select the region
   - Configure public access settings (typically block all public access for security)
   - Enable versioning and encryption if needed

4. Create an IAM user with S3 access:
   - Go to IAM in the AWS Console
   - Create a new user with programmatic access
   - Attach the `AmazonS3FullAccess` policy or a custom policy with more restrictive permissions
   - Save the access key ID and secret access key

### 3.4. Choose a Deployment Method

You have several options for deploying a FastAPI application on AWS:

#### Option A: AWS Elastic Beanstalk (Simplest)

1. Go to the AWS Management Console
2. Navigate to Elastic Beanstalk
3. Create a new environment:
   - Select Web server environment
   - Choose Python as the platform
   - Upload your application code as a .zip file or choose to deploy from Git

#### Option B: Amazon ECS with Fargate (Containerized)

1. Create a Dockerfile in the project root:

```Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. Build and push the Docker image to Amazon ECR:

```bash
# Create an ECR repository
aws ecr create-repository --repository-name kave-app

# Get the repository URI
ECR_REPO=$(aws ecr describe-repositories --repository-names kave-app --query "repositories[0].repositoryUri" --output text)

# Log in to ECR
aws ecr get-login-password --region $(aws configure get region) | docker login --username AWS --password-stdin $ECR_REPO

# Build and tag the Docker image
docker build -t kave-app .
docker tag kave-app:latest $ECR_REPO:latest

# Push the image to ECR
docker push $ECR_REPO:latest
```

3. Create an ECS cluster, task definition, and service using the AWS Console or CLI

#### Option C: Amazon EC2 (Most Control)

1. Launch an EC2 instance:
   - Choose an Amazon Linux 2 or Ubuntu AMI
   - Select an appropriate instance type (e.g., t2.micro for dev/test)
   - Configure instance details, storage, and security groups
   - Create or use an existing key pair for SSH access

2. Connect to your instance and set up the environment:

```bash
ssh -i /path/to/key.pem ec2-user@your-instance-public-dns

# Update the system
sudo yum update -y  # For Amazon Linux
# or
sudo apt update && sudo apt upgrade -y  # For Ubuntu

# Install Python and other dependencies
sudo yum install -y python3 python3-pip git  # For Amazon Linux
# or
sudo apt install -y python3 python3-pip git  # For Ubuntu

# Clone your repository
git clone https://github.com/yourusername/kave.git
cd kave

# Install dependencies
pip3 install -r requirements.txt
```

3. Configure application to run with Gunicorn and Supervisor:

Create a Gunicorn configuration file (`gunicorn_conf.py`):

```python
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
bind = "0.0.0.0:8000"
```

Set up Supervisor to manage the process:

```bash
sudo apt install -y supervisor  # For Ubuntu
# or
sudo yum install -y supervisor  # For Amazon Linux

sudo nano /etc/supervisor/conf.d/kave.conf  # Path may vary by OS
```

Add the following to the supervisor config:

```
[program:kave]
command=/home/ec2-user/.local/bin/gunicorn -c gunicorn_conf.py app.main:app
directory=/home/ec2-user/kave
user=ec2-user
autostart=true
autorestart=true
stderr_logfile=/var/log/kave.err.log
stdout_logfile=/var/log/kave.out.log
```

Start the supervisor service:

```bash
sudo systemctl enable supervisor
sudo systemctl start supervisor
sudo supervisorctl reload
```

4. Set up Nginx as a reverse proxy:

```bash
sudo apt install -y nginx  # For Ubuntu
# or
sudo yum install -y nginx  # For Amazon Linux

sudo nano /etc/nginx/sites-available/kave  # For Ubuntu
# or
sudo nano /etc/nginx/conf.d/kave.conf  # For Amazon Linux
```

Add the following configuration:

```
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site (Ubuntu only) and restart Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/kave /etc/nginx/sites-enabled/  # Ubuntu only
sudo systemctl restart nginx
```

## 4. Configure Environment Variables

### 4.1. Set Up Environment Variables Based on Deployment Method

#### For Elastic Beanstalk:

Use the Elastic Beanstalk Console to set environment variables:
1. Go to your environment
2. Navigate to Configuration > Software
3. Under "Environment properties", add:

```
API_ENV=production
DEBUG=False
SECRET_KEY=your_secure_secret_key
DATABASE_URL=postgresql://username:password@your-rds-endpoint:5432/your-db-name
MAILCHIMP_API_KEY=your_mailchimp_api_key
MAILCHIMP_WEBHOOK_SECRET=your_mailchimp_webhook_secret
S3_BUCKET_NAME=your_s3_bucket_name
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=your_aws_region
USE_S3_STORAGE=True
SQL_ECHO=False
```

#### For EC2:

Create a .env file on your EC2 instance:

```bash
nano ~/.env
```

Add your environment variables:

```
API_ENV=production
DEBUG=False
SECRET_KEY=your_secure_secret_key
DATABASE_URL=postgresql://username:password@your-rds-endpoint:5432/your-db-name
MAILCHIMP_API_KEY=your_mailchimp_api_key
MAILCHIMP_WEBHOOK_SECRET=your_mailchimp_webhook_secret
S3_BUCKET_NAME=your_s3_bucket_name
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=your_aws_region
USE_S3_STORAGE=True
SQL_ECHO=False
```

#### For ECS:

Configure environment variables in your task definition:
1. When creating your task definition, add environment variables under "Container Definition"
2. Include all the environment variables listed above

## 5. Configure Application for Production

### 5.1. Update CORS Settings in app/main.py

For production, restrict CORS origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],  # Replace with actual domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5.2. Add Health Check Endpoint (Recommended for AWS)

Add a health check endpoint in your app/main.py:

```python
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for AWS load balancers."""
    return {"status": "healthy"}
```

## 6. Set Up CI/CD Pipeline (Optional)

### 6.1. Configure GitHub Actions for AWS Deployment

Create a GitHub workflow file at `.github/workflows/aws-deploy.yml`:

```yaml
name: Deploy to AWS

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v2
      
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        
    - name: Run tests
      run: |
        pytest
        
    # For Elastic Beanstalk deployment
    - name: Deploy to AWS Elastic Beanstalk
      uses: einaregilsson/beanstalk-deploy@v20
      with:
        aws_access_key: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws_secret_key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        application_name: kave-app
        environment_name: kave-app-prod
        region: us-east-1
        version_label: ${{ github.sha }}
        deployment_package: deploy.zip
        
    # Alternatively, for ECS deployment
    # - name: Configure AWS credentials
    #   uses: aws-actions/configure-aws-credentials@v1
    #   with:
    #     aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    #     aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    #     aws-region: us-east-1
    #     
    # - name: Login to Amazon ECR
    #   id: login-ecr
    #   uses: aws-actions/amazon-ecr-login@v1
    #   
    # - name: Build, tag, and push image to Amazon ECR
    #   env:
    #     ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
    #     ECR_REPOSITORY: kave-app
    #     IMAGE_TAG: ${{ github.sha }}
    #   run: |
    #     docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
    #     docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
    #     
    # - name: Update ECS service
    #   run: |
    #     aws ecs update-service --cluster your-cluster-name --service your-service-name --force-new-deployment
```

## 7. Database Migrations

### 7.1. Run Initial Migration on RDS Database

After deploying your application infrastructure but before starting the application:

```bash
# For EC2/direct SSH access
cd /path/to/your/app
alembic upgrade head

# For Elastic Beanstalk
eb ssh
cd /var/app/current
source /var/app/venv/*/bin/activate
alembic upgrade head

# For ECS/Fargate (using a one-time task)
# Create a task definition specifically for migrations, then:
aws ecs run-task --cluster your-cluster --task-definition your-migration-task --network-configuration '{"awsvpcConfiguration":{"subnets":["subnet-12345"],"securityGroups":["sg-12345"],"assignPublicIp":"ENABLED"}}'
```

## 8. DNS and HTTPS Configuration

### 8.1. Set Up Route 53 and Domain Name (Optional)

1. Register a domain through Route 53 or use an existing domain
2. Create a hosted zone in Route 53
3. Add a record set pointing to your AWS resource:
   - For EC2 with Elastic IP: Create an A record with the Elastic IP
   - For Elastic Beanstalk: Create a CNAME record pointing to the Elastic Beanstalk domain
   - For ECS with ALB: Create an A record as an alias to the ALB

### 8.2. Set Up AWS Certificate Manager (ACM) for HTTPS

1. Request a certificate in ACM:
   - Go to AWS Certificate Manager
   - Request a public certificate
   - Enter your domain name(s)
   - Choose DNS validation
   - Follow the steps to validate your domain

2. Associate the certificate with your deployment:
   - For Elastic Beanstalk: Update the environment to use HTTPS with your certificate
   - For EC2 with ALB: Configure the ALB listener to use HTTPS with your certificate
   - For ECS with ALB: Configure the ALB listener to use HTTPS with your certificate

## 9. Monitoring and Logging

### 9.1. Set Up CloudWatch for Logs and Metrics

1. Configure your application or its environment to send logs to CloudWatch:
   - For Elastic Beanstalk: This is configured automatically
   - For EC2: Install and configure the CloudWatch agent
   - For ECS: Configure your task definition to use awslogs as the log driver

2. Create CloudWatch Alarms for important metrics:
   - CPU utilization
   - Memory usage
   - Error rates
   - Response times

### 9.2. Set Up X-Ray for Distributed Tracing (Optional)

1. Add AWS X-Ray SDK to your requirements.txt:
```
aws-xray-sdk>=2.12.0
```

2. Integrate X-Ray with FastAPI in your application:

```python
from aws_xray_sdk.core import xray_recorder, patch_all
from aws_xray_sdk.ext.fastapi.middleware import XRayMiddleware
from fastapi import FastAPI

xray_recorder.configure(service='kave-api')
patch_all()

app = FastAPI()
app.add_middleware(XRayMiddleware, recorder=xray_recorder)
```

## 10. Security Considerations

### 10.1. Set Up Security Groups

Configure security groups to restrict access:
- Database: Allow connections only from application servers
- Application servers: Allow HTTP/HTTPS from the internet
- Restrict SSH access to known IPs

### 10.2. Use IAM Roles for AWS Services

Instead of hardcoding AWS credentials in your application:
1. Create IAM roles with the necessary permissions
2. Assign the roles to your AWS resources:
   - For EC2: Use instance profiles
   - For ECS: Use task execution roles and task roles
   - For Elastic Beanstalk: Configure instance profiles

### 10.3. Enable AWS WAF (Optional)

Set up AWS Web Application Firewall to protect against common web exploits.

## 11. Additional Considerations

### 11.1. Backup and Disaster Recovery

1. RDS Database:
   - Configure automated backups
   - Consider multi-AZ deployment for high availability

2. S3 Data:
   - Enable versioning
   - Consider cross-region replication for critical data

### 11.2. Scaling Strategy

1. Horizontal Scaling:
   - For EC2: Use Auto Scaling Groups
   - For ECS: Configure Service Auto Scaling
   - For Elastic Beanstalk: Configure environment capacity

2. Database Scaling:
   - Read replicas for read-heavy workloads
   - Vertical scaling for write-heavy workloads

### 11.3. Cost Optimization

1. Right-size your resources:
   - Use the smallest instance types that meet your performance needs
   - Configure auto-scaling to scale down during low-traffic periods

2. Use Savings Plans or Reserved Instances for predictable workloads

3. Set up AWS Budgets and Cost Explorer to monitor spending
``` 