# Kave - AI Agent Platform

A platform for AI agents that processes emails from MailChimp, parses them, and stores them along with their attachments.

## Project Overview

Kave is designed to be a comprehensive AI agent platform. In this first phase, it focuses on:

1. Receiving emails from MailChimp via webhooks
2. Parsing and validating email content
3. Storing emails and their attachments in a database
4. Providing a solid foundation for future AI agent capabilities
5. Extracting text from PDF attachments via OCR

Future phases will include:
- Sentiment analysis of emails
- AI agents that can compose and send emails
- Integration with external APIs
- Workflow automation

## Technical Stack

- **Framework**: FastAPI
- **Database**: SQLAlchemy with async support (SQLite for development, PostgreSQL for production)
- **Validation**: Pydantic V2
- **Testing**: Pytest with async support
- **Development**: Black, isort, Flake8, Mypy, Autoflake
- **Webhook Testing**: ngrok for local webhook testing

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Poetry (recommended) or pip

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/kave.git
cd kave
```

2. Set up a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements/dev.txt
```

4. Create a `.env` file:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### Running the Application

To run the application locally:

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000.

### Database Migrations

This project uses Alembic for database migrations. The application no longer automatically creates database tables at startup - instead, migrations must be run explicitly.

To create and apply migrations:

```bash
# After making changes to SQLAlchemy models:
alembic revision --autogenerate -m "Description of your changes"

# To upgrade the database to the latest version:
alembic upgrade head

# To downgrade one migration:
alembic downgrade -1
```

**Note:** When deploying to production, migrations are automatically run by the `release` command in the Procfile before the web process starts.

### Testing

To run the test suite:

```bash
pytest
```

For test coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

### Code Quality

To format and lint your code:

```bash
# Format code with Black
black app

# Sort imports with isort
isort app

# Remove unused imports and variables with autoflake
autoflake --in-place --remove-all-unused-imports --remove-unused-variables --recursive app

# Check for linting issues with flake8
flake8 app

# Check type annotations with mypy
mypy app
```

## Project Structure

```
.
├── app/
│   ├── main.py                 # FastAPI app instantiation
│   ├── api/                    # API routes and endpoints
│   │   ├── deps.py             # API dependencies
│   │   └── endpoints/          # Route handlers
│   │       └── email_webhooks.py
│   ├── models/                 # Database models
│   │   └── email_data.py
│   ├── schemas/                # Pydantic schemas
│   │   └── webhook_schemas.py
│   ├── services/               # Business logic
│   │   └── email_processing_service.py
│   ├── db/                     # Database configuration
│   │   └── session.py
│   ├── core/                   # Core configuration
│   │   └── config.py
│   ├── integrations/           # External service integrations
│   │   └── email/
│   │       └── client.py
│   ├── agents/                 # Future AI agents
│   ├── tools/                  # Tools for AI agents
│   └── tests/                  # Test suite
├── scripts/                    # Utility scripts
│   ├── start_ngrok.py          # Script to start ngrok tunnel
│   └── start_local_with_webhook.py  # Script to start app with ngrok
├── docs/                       # Documentation
│   └── ngrok_webhook_testing.md  # Guide for webhook testing
├── requirements/               # Dependency files
├── .env.example                # Example environment variables
└── README.md                   # This file
```

## API Documentation

Once the application is running, you can access the API documentation at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Setting Up MailChimp Webhooks

1. Log in to your MailChimp account
2. Navigate to Audience > Settings > Webhooks
3. Add a new webhook with the URL: `https://your-domain.com/webhooks/email/mailchimp`
4. Enable the events you want to receive (typically "Subscribe" and "Email")
5. Save the webhook

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Heroku Deployment

This application is configured for Heroku deployment. Refer to the `HEROKU_DEPLOYMENT_PLAN.md` file for detailed deployment instructions.

## Testing Webhooks Locally

For testing Mandrill webhooks with your local development environment, we've integrated ngrok to expose your local server to the internet.

### Prerequisites

1. Install ngrok from [ngrok.com](https://ngrok.com/download)
2. Get your auth token by signing up for a free account

### Quick Start

Run the following command to start both the FastAPI application and ngrok tunnel:

```bash
./start_webhook_testing.sh
```

This will:
1. Start your FastAPI application on port 8000
2. Create an ngrok tunnel to expose your local server
3. Display the URL to use in your Mandrill webhook configuration

For more detailed information, see [docs/ngrok_webhook_testing.md](docs/ngrok_webhook_testing.md).

## PDF OCR Functionality

This application includes functionality to automatically extract text from PDF attachments using OCR:

### Features
- Automatic OCR processing of PDF attachments received via email webhooks
- Text extraction using PyMuPDF with Pytesseract OCR fallback for image-based PDFs
- Text storage per page in the database for easy searching and retrieval
- Asynchronous processing using Celery to avoid impacting webhook response times

### System Dependencies

#### macOS Development
```bash
# Install required system dependencies
brew install tesseract tesseract-lang redis

# Start Redis for Celery
brew services start redis
```

#### Heroku Deployment
The application requires additional buildpacks for Tesseract and PDF processing on Heroku:
```bash
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt
```

### Environment Variables
```
# Redis Configuration (Celery)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
# Note: On Heroku, these will be overridden by REDIS_URL

# PDF Processing Configuration
PDF_BATCH_COMMIT_SIZE=10  # Set to 0 for single transaction per PDF
PDF_USE_SINGLE_TRANSACTION=false
PDF_MAX_ERROR_PERCENTAGE=10.0

# Tesseract Configuration
TESSERACT_PATH=/usr/local/bin/tesseract  # Update for your environment
TESSERACT_LANGUAGES=eng  # Comma-separated list of language codes
```

### Starting the Celery Worker
```bash
# Development
celery -A app.worker.celery_app worker -l info

# On Heroku, the worker is defined in the Procfile
``` 