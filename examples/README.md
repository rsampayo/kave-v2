# Example Scripts

This directory contains example and utility scripts that can be useful for development, testing, and troubleshooting purposes.

## Available Examples

### simplified_app.py

A minimal version of the main FastAPI application with basic endpoints. This is useful for:
- Diagnosing issues with the application structure
- Testing basic functionality in isolation
- Demonstrating a minimal FastAPI setup with database connectivity

To run:
```bash
python -m examples.simplified_app
```

### test_db_connection.py

A standalone script for testing database connectivity. This is useful for:
- Diagnosing database connection issues
- Verifying database settings and credentials
- Testing connections to different database environments

To run:
```bash
python -m examples.test_db_connection
```

## Usage Notes

These examples are meant for development and debugging purposes only. They should not be used in production. Many of the features and security measures of the full application may be missing from these simplified examples. 