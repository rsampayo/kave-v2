# Contributing to Kave

Thank you for considering contributing to Kave! This document provides guidelines and instructions for contributing to the project.

## Development Setup

1. Clone the repository
2. Create a virtual environment
3. Install development dependencies: `pip install -r requirements/dev.txt`
4. Set up environment variables in `.env` file
5. Run database migrations: `alembic upgrade head`

## Development Workflow

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes following our coding standards
3. Run code quality checks (see below)
4. Write tests for your changes
5. Run the test suite: `pytest`
6. Commit changes with descriptive commit messages
7. Push to your branch and submit a pull request

## Code Quality Standards

We use the following tools to maintain code quality:

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

## Testing

We use pytest for testing. To run the tests:

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=term-missing
```

## PDF OCR Development

When working with the PDF OCR feature:

1. **System Dependencies**: Ensure you have Redis and Tesseract installed locally:
   ```bash
   # macOS
   brew install tesseract tesseract-lang redis
   brew services start redis
   
   # Ubuntu/Debian
   sudo apt-get install tesseract-ocr tesseract-ocr-eng redis-server
   sudo systemctl start redis
   ```

2. **Running the Worker**: Start the Celery worker to process OCR tasks:
   ```bash
   celery -A app.worker.celery_app worker -l info
   ```

3. **Testing**: 
   - Unit tests for OCR are in `app/tests/test_unit/test_worker.py`
   - Integration tests are in `app/tests/test_integration/test_api/test_pdf_ocr_flow.py`
   - Tests use Celery's eager mode to run tasks synchronously

4. **Configuration**:
   - Adjust OCR settings in environment variables (see README)
   - For additional language support, install language packs:
     ```bash
     brew install tesseract-lang  # macOS
     ```
     and update the `TESSERACT_LANGUAGES` environment variable.

## Pull Request Process

1. Ensure your code adheres to our code quality standards
2. Update documentation if necessary
3. Make sure all tests pass
4. Your PR will be reviewed by project maintainers

## Code of Conduct

Please be respectful and inclusive in all interactions with the project community. 