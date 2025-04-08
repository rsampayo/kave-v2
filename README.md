# Kave - AI Agent Platform

A platform for AI agents that processes emails from MailChimp, parses them, and stores them along with their attachments.

## Project Overview

Kave is designed to be a comprehensive AI agent platform. In this first phase, it focuses on:

1. Receiving emails from MailChimp via webhooks
2. Parsing and validating email content
3. Storing emails and their attachments in a database
4. Providing a solid foundation for future AI agent capabilities

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