# S3 Storage Setup for Heroku Deployment

This document provides step-by-step instructions for configuring S3 storage for the Kave project when deploying to Heroku.

## Why S3 Storage is Required for Heroku

Heroku uses an ephemeral filesystem, which means:

1. Any files written to the filesystem are temporary and will be lost when:
   - The dyno restarts (which happens at least once per day)
   - The application is redeployed
   - The dyno is scaled up or down

2. For Kave's email attachment storage needs, we need a persistent storage solution.
   S3 provides a reliable, scalable solution that works well with Heroku.

## Setting Up an S3 Bucket

1. **Sign in to the AWS Management Console**
   - Go to https://aws.amazon.com/console/
   - Sign in with your AWS account

2. **Create an S3 Bucket**
   - Go to the S3 service
   - Click "Create bucket"
   - Choose a globally unique bucket name (e.g., `kave-production-attachments`)
   - Select the appropriate AWS region (e.g., `us-east-1`)
   - Configure options as needed (typically default settings are fine)
   - Create the bucket

3. **Configure CORS (if necessary)**
   - If you need to access attachments directly from a browser, configure CORS
   - Go to your bucket → Permissions → CORS configuration
   - Add a configuration like:
     ```json
     [
       {
         "AllowedHeaders": ["*"],
         "AllowedMethods": ["GET"],
         "AllowedOrigins": ["https://your-app-domain.com"],
         "ExposeHeaders": []
       }
     ]
     ```

## Creating IAM Credentials for S3 Access

1. **Create an IAM User**
   - Go to IAM service
   - Click "Users" → "Add user"
   - Enter a username (e.g., `kave-s3-user`)
   - Select "Programmatic access"

2. **Attach Permissions**
   - Create a policy with the following JSON (replace `your-bucket-name` with your actual bucket name):
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Action": [
             "s3:PutObject",
             "s3:GetObject",
             "s3:DeleteObject"
           ],
           "Resource": "arn:aws:s3:::your-bucket-name/*"
         },
         {
           "Effect": "Allow",
           "Action": "s3:ListBucket",
           "Resource": "arn:aws:s3:::your-bucket-name"
         }
       ]
     }
     ```
   - Attach this policy to the user

3. **Get Access Keys**
   - After creating the user, download or copy the access key ID and secret access key
   - Store these securely - you won't be able to view the secret key again

## Configuring Heroku Environment Variables

Set the following environment variables in Heroku:

```bash
heroku config:set S3_BUCKET_NAME=your-bucket-name
heroku config:set AWS_ACCESS_KEY_ID=your-access-key-id
heroku config:set AWS_SECRET_ACCESS_KEY=your-secret-access-key
heroku config:set AWS_REGION=your-selected-region
heroku config:set USE_S3_STORAGE=True
```

## Testing S3 Configuration

Before deployment, test your S3 configuration:

1. Update your local `.env` file with your S3 credentials
2. Run the S3 connection test script:
   ```bash
   ./s3_connection_test.py
   ```
3. The script should show successful upload, download, and deletion of a test file

## Verifying Attachment Storage After Deployment

After deploying to Heroku:

1. Create a test email with an attachment via the application
2. Verify the attachment is stored in S3:
   - Check the S3 bucket in the AWS console
   - The attachment should be stored at `attachments/{email_id}/{attachment_id}_{filename}`
3. Verify you can download the attachment through the application

## Troubleshooting

If you encounter issues with S3 storage:

1. **Check Environment Variables**:
   - Verify all S3 environment variables are set correctly in Heroku
   - Use `heroku config` to list all config vars

2. **Check S3 Bucket Permissions**:
   - Ensure the bucket has the correct policies
   - Verify the IAM user has appropriate permissions

3. **Check Logs**:
   - Use `heroku logs --tail` to monitor logs in real-time
   - Look for any S3-related error messages

4. **Test Connectivity**:
   - Run `heroku run python -c "import aioboto3; print('aioboto3 installed')"` to verify the dependency is available
   - You can also run a one-off dyno with a connection test:
     ```bash
     heroku run python s3_connection_test.py
     ```
