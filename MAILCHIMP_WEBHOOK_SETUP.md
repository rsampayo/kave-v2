# Mailchimp Inbound Email Webhook Setup Guide

This guide outlines the steps required to configure Mailchimp Transactional Email (formerly Mandrill) to receive emails sent to an address at your domain (e.g., `csr@ramonsampayo.com`) and forward them to your application's webhook endpoint for processing.

**Prerequisites:**

*   A Mailchimp account with the **Transactional Email add-on**.
*   Access to your domain's DNS settings (e.g., through your domain registrar).
*   Your application deployed and publicly accessible via HTTPS.

## Step 1: Configure Mailchimp Transactional Email

1.  **Log in to Mailchimp:** Access your Mailchimp account.
2.  **Navigate to Transactional Email:** Find the section for Transactional Email (Mandrill). This might be under "Automations" or a dedicated "Transactional" tab.
3.  **Add & Verify Sending Domain:**
    *   Go to **Settings** -> **Domains** (or similar section like "Sending Domains").
    *   Click **Add Domain** and enter `ramonsampayo.com`.
    *   Mailchimp will provide several **DNS records** (typically MX, TXT for SPF, and TXT/CNAME for DKIM). **Keep this page/information open**, as you'll need these records in Step 2. You must add these to your DNS provider to verify ownership and allow Mailchimp to handle email for the domain. Verification can take some time after adding the records.
4.  **Set up Inbound Route:**
    *   Navigate to the **Inbound** section within Mailchimp Transactional settings.
    *   Click **Add Inbound Route** (or similar).
    *   **For email address:** Enter the specific address you want to handle (e.g., `csr@ramonsampayo.com`) or use a wildcard pattern (e.g., `*@ramonsampayo.com`) to catch all emails to your domain.
    *   **Webhook URL:** In the "POST to URL" field (or similar), enter the **full, publicly accessible HTTPS URL** of your deployed application's webhook endpoint. Example: `https://<your-app-domain.com>/webhooks/mailchimp`
    *   **Webhook Validation:** When you save this configuration, Mailchimp will send a ping event to your endpoint to verify it exists and is responsive. Your endpoint must respond with a 200 OK status code to confirm successful setup.
    *   Save the inbound route.

## Step 2: Configure Domain DNS Records

1.  **Log in to your DNS Provider:** Access the DNS management panel for `ramonsampayo.com` (e.g., GoDaddy, Cloudflare, Namecheap).
2.  **Add MX Records:**
    *   Add the **MX (Mail Exchanger)** records provided by Mailchimp in Step 1.3. These tell mail servers to send email for `ramonsampayo.com` to Mailchimp's servers. Pay attention to the priority values Mailchimp specifies. Remove or update any pre-existing MX records that might conflict.
3.  **Add SPF Record:**
    *   Add the **TXT** record for **SPF (Sender Policy Framework)** provided by Mailchimp (Step 1.3). This helps prevent email spoofing by listing Mailchimp as an authorized sender for your domain. If you already have an SPF record, you'll need to *merge* Mailchimp's `include:` mechanism into it, rather than creating a second SPF record.
4.  **Add DKIM Record:**
    *   Add the **TXT or CNAME** record for **DKIM (DomainKeys Identified Mail)** provided by Mailchimp (Step 1.3). This adds a digital signature to emails, further verifying their authenticity.
5.  **Wait for Propagation:** DNS changes can take anywhere from a few minutes to 48 hours to propagate fully across the internet. Mailchimp's domain verification status should update once propagation is complete.

## Step 3: Configure Your Application

1.  **Ensure Deployment:** Confirm your application is successfully deployed and running at the public HTTPS URL you provided to Mailchimp in Step 1.4.
2.  **Set Environment Variables:** Your application needs specific environment variables to interact with Mailchimp. Set these in your deployment environment (e.g., `.env` file, Heroku config vars, Docker environment variables):
    *   `MAILCHIMP_API_KEY`: Your application's `MailchimpClient` needs an API key. Generate one in your Mailchimp account settings (Account -> Extras -> API Keys) and set it here.
    *   **Other Variables:** Ensure all other required environment variables are correctly set for your deployment (e.g., `DATABASE_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME` if using S3 for attachments).
3.  **Restart Application (if necessary):** Ensure your application loads the new environment variables, potentially requiring a restart depending on your deployment method.

## Step 4: Test the Setup

1.  **Send a Test Email:** Send an email from any external email account (e.g., your Gmail) to `csr@ramonsampayo.com` (or whichever address you configured in the inbound route).
2.  **Check Mailchimp Logs:** Look at the logs within Mailchimp Transactional's Inbound section. You should see the incoming email and the attempt to POST to your webhook URL. Check for any errors reported by Mailchimp.
3.  **Check Application Logs:** Monitor your application's logs for entries related to `/webhooks/mailchimp`. Look for:
    *   Successful processing messages (e.g., "Webhook received and processed successfully").
    *   Webhook validation messages (e.g., "Received Mailchimp webhook validation ping").
    *   Errors during email processing or database interaction.
4.  **Verify Data:** Check your application's database (specifically the `emails` table) to confirm that the data from the test email has been successfully stored.

By following these steps, you should have a working pipeline where emails sent to your specified address are received by Mailchimp, forwarded to your application's webhook, processed, and stored. 

## Webhook Security and Validation

Note that Mailchimp uses a simple webhook validation approach:

1. When you first register your webhook URL, Mailchimp sends a ping event (POST request) to verify the endpoint exists and is responsive.
2. Your application must respond with a 200 OK status code to this ping event.
3. For subsequent webhook events, Mailchimp simply sends POST requests to your endpoint.
4. Unlike some other webhook providers, Mailchimp does not include cryptographic signatures in its webhook requests for verification.

This approach relies on the secrecy of your webhook URL for security. If you need additional security, consider implementing additional validation in your application or using a proxy service that can add security layers. 