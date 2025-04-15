# Testing Webhooks Locally with Ngrok

This guide explains how to use ngrok to expose your local development server to the internet, allowing you to test Mandrill webhooks with your local application.

## Prerequisites

1. **Install ngrok**:
   - Download from [ngrok.com](https://ngrok.com/download)
   - Follow the installation instructions for your operating system
   - Sign up for a free account and get your auth token

2. **Install required Python packages**:
   ```bash
   pip install httpx pydantic pydantic-settings
   ```

## Configuration

1. **Update your `.env` file** with the ngrok configuration:
   ```
   # Ngrok Settings
   NGROK_AUTH_TOKEN=your_ngrok_auth_token
   NGROK_REGION=us
   NGROK_LOCAL_PORT=8000
   WEBHOOK_PATH=/v1/webhooks/mandrill
   ```

2. **Configure Mandrill webhook**: 
   - Log in to your Mandrill account
   - Go to Settings → Webhooks
   - Click "Add Webhook"
   - For the webhook URL, use the URL provided by the ngrok script (will be displayed when you run the script)
   - Select the events you want to receive (typically "Message Is Sent" and "Message Is Opened")
   - If needed, set the webhook authentication string that matches your `MAILCHIMP_WEBHOOK_SECRET`

## Usage

### Option 1: Start ngrok only

If you prefer to start your FastAPI application separately, you can run just the ngrok tunnel:

```bash
python -m scripts.start_ngrok
```

This will display your ngrok URL, which you can use in your Mandrill webhook configuration.

### Option 2: Start both FastAPI and ngrok

For convenience, you can start both the FastAPI application and ngrok tunnel with a single command:

```bash
python -m scripts.start_local_with_webhook
```

This will:
1. Start your FastAPI application on the configured port (default: 8000)
2. Start an ngrok tunnel to expose that port
3. Display both the local URL and the public ngrok URL

## How It Works

1. **ngrok tunnel** creates a secure tunnel from the public internet to your local machine
2. **Mandrill** sends webhook events to the ngrok URL
3. **ngrok** forwards these requests to your local FastAPI server
4. Your **FastAPI application** processes the webhook events normally

## Troubleshooting

If you encounter issues:

1. **Check ngrok status**:
   - Open `http://localhost:4040` in your browser to see the ngrok dashboard
   - Review the incoming requests to debug issues

2. **Verify webhook configuration**:
   - Make sure the webhook URL in Mandrill exactly matches the URL provided by ngrok
   - Check that your `MAILCHIMP_WEBHOOK_SECRET` matches the webhook authentication string

3. **Check application logs**:
   - The FastAPI application logs and ngrok logs should help identify issues

4. **Test with a ping event**:
   - In Mandrill, you can send a test event to verify the webhook connection

## Security Considerations

1. **ngrok exposes your local server to the internet**
   - Only use for development and testing
   - Don't expose sensitive internal services
   
2. **Use webhook authentication**
   - Always configure the Mandrill webhook authentication string

3. **Auth token**
   - Keep your ngrok auth token secure
   - Don't commit it to version control 