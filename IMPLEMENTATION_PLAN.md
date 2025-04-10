# Kave Project: Implementation Plan

This document provides a detailed step-by-step implementation plan for the recommended improvements to the Kave project FastAPI application. Each section includes specific instructions, file locations, and code examples necessary for an AI to implement these changes.

## 1. Dependency Management with pip-tools

### 1.1 Create Base Requirements Input Files

**Step 1**: Create the `.in` files:

```bash
# Create base.in
touch requirements/base.in
# Create dev.in
touch requirements/dev.in
# Create integrations.in
touch requirements/integrations.in
```

**Step 2**: Populate base.in with direct dependencies:

```
# requirements/base.in
fastapi>=0.109.0
uvicorn>=0.28.0
pydantic>=2.6.0
pydantic-settings>=2.1.0
sqlalchemy>=2.0.0
alembic>=1.15.0
python-multipart>=0.0.9
email-validator>=2.1.0
python-dotenv>=1.0.0
asyncpg>=0.29.0
aiosqlite>=0.19.0
httpx>=0.27.0
greenlet>=3.1.0
boto3>=1.34.0
aioboto3>=12.3.0
aiofiles>=24.1.0
types-aiofiles>=24.1.0.20250326
```

**Step 3**: Populate integrations.in:

```
# requirements/integrations.in
-r base.in
# For parsing emails and attachments
python-dateutil>=2.8.2
# For MailChimp integration
mailchimp-marketing>=3.0.0
mailchimp-transactional>=1.0.0
```

**Step 4**: Populate dev.in:

```
# requirements/dev.in
-r integrations.in
# Testing
pytest>=8.0.0
pytest-cov>=4.1.0
pytest-asyncio>=0.23.0

# Linting and Formatting
black>=25.1.0
isort>=5.13.0
flake8>=7.0.0
flake8-bugbear>=24.2.0
flake8-docstrings>=1.7.0
flake8-comprehensions>=3.14.0
autoflake>=2.3.0
mypy>=1.8.0
types-python-dateutil>=2.8.0

# Development Tools
pip-tools>=7.3.0
```

**Step 5**: Install pip-tools and generate the .txt files:

```bash
pip install pip-tools
pip-compile requirements/base.in --output-file=requirements/base.txt
pip-compile requirements/integrations.in --output-file=requirements/integrations.txt
pip-compile requirements/dev.in --output-file=requirements/dev.txt
```

**Step 6**: Update README with instructions:

```markdown
## Dependency Management

This project uses pip-tools to manage Python dependencies:

1. Direct dependencies are specified in `.in` files (base.in, integrations.in, dev.in)
2. Add new dependencies to the appropriate `.in` file
3. Run `pip-compile requirements/base.in` to update the corresponding `.txt` file
4. Run `pip-compile requirements/integrations.in` to update integrations.txt
5. Run `pip-compile requirements/dev.in` to update dev.txt
6. Install dependencies with `pip install -r requirements/dev.txt`

Never modify the `.txt` files directly.
```

## 2. API Versioning Implementation

### 2.1 Refactor API Structure

**Step 1**: Create versioned API directory structure:

```bash
mkdir -p app/api/v1
touch app/api/v1/__init__.py
touch app/api/v1/api.py
mkdir -p app/api/v1/endpoints
touch app/api/v1/endpoints/__init__.py
```

**Step 2**: Move existing endpoints to version directory:

```python
# app/api/v1/endpoints/__init__.py
"""API endpoint modules for v1."""
```

**Step 3**: Move email_webhooks.py to the versioned directory:

```bash
cp app/api/endpoints/email_webhooks.py app/api/v1/endpoints/
cp app/api/endpoints/attachments.py app/api/v1/endpoints/
```

**Step 4**: Create API router aggregator:

```python
# app/api/v1/api.py
"""API v1 router module."""

from fastapi import APIRouter

from app.api.v1.endpoints import email_webhooks, attachments

api_router = APIRouter()
api_router.include_router(email_webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(
    attachments.router, prefix="/attachments", tags=["attachments"]
)
```

**Step 5**: Update the main.py file:

```python
# app/main.py modifications
# Change the router import:
from app.api.v1.api import api_router

# Replace router includes with:
app.include_router(api_router, prefix="/api/v1")
```

### 2.2 Update Configuration for API Versioning

**Step 1**: Update the settings class:

```python
# app/core/config.py additions
    # API version settings
    API_V1_STR: str = "/api/v1"
    VERSION: str = "0.1.0"
```

**Step 2**: Use the API version in FastAPI instance:

```python
# app/main.py updates
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI agent platform that processes emails from MailChimp",
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)
```

## 3. Enhanced Security Implementation

### 3.1 Secure CORS Configuration

**Step 1**: Update settings for CORS origins:

```python
# app/core/config.py additions
    # CORS settings
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]
```

**Step 2**: Use these settings in main.py:

```python
# app/main.py updates
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
```

### 3.2 Add Rate Limiting Middleware

**Step 1**: Add slowapi to requirements:

```
# requirements/base.in addition
slowapi>=0.1.8
```

**Step 2**: Implement rate limiting:

```python
# app/core/middleware.py - create this file
"""Middleware configurations for the application."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create rate limiter
limiter = Limiter(key_func=get_remote_address)
```

**Step 3**: Apply rate limiting in main.py:

```python
# app/main.py additions
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import RateLimitMiddleware

from app.core.middleware import limiter

app = FastAPI(...) # existing constructor

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, limiter.error_handler)
app.add_middleware(RateLimitMiddleware, limiter=limiter)
```

**Step 4**: Apply rate limits to endpoints:

```python
# app/api/v1/endpoints/email_webhooks.py updates
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.middleware import limiter

# Add limiter decorator to endpoints
@router.post(
    "/mailchimp",
    status_code=status.HTTP_202_ACCEPTED,
    # ...existing parameters
)
@limiter.limit("10/minute")
async def receive_mailchimp_webhook(...):
    # ...existing implementation
```

### 3.3 Authentication/Authorization Middleware

**Step 1**: Add dependencies:

```
# requirements/base.in addition
python-jose>=3.3.0
passlib>=1.7.4
bcrypt>=4.0.1
```

**Step 2**: Create authentication utilities:

```python
# app/core/security.py - create this file
"""Security utilities for authentication and authorization."""

from datetime import datetime, timedelta
from typing import Any, Optional, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token URL - update this based on your API structure
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

# Token model
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """Create a new JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)
```

**Step 3**: Enhance configuration for auth:

```python
# app/core/config.py additions
    # Security settings
    SECRET_KEY: str  # Should be set in environment
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
```

**Step 4**: Create authentication dependencies:

```python
# app/api/deps.py additions
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import TokenPayload
from app.db.session import get_db
# Import your User model - add it if not exists

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token"
)

async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> Any:
    """Get the current authenticated user."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    # This is where you'd get the user from the database
    # For now we'll return a placeholder
    return {"id": token_data.sub, "is_active": True}

def get_current_active_user(
    current_user: Any = Depends(get_current_user),
) -> Any:
    """Check if the current user is active."""
    if not current_user.get("is_active"):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
```

## 4. Improved Development Workflow with Docker

### 4.1 Create Dockerfiles

**Step 1**: Create the main Dockerfile:

```dockerfile
# Dockerfile
FROM python:3.11-slim as base

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install dependencies
FROM base as dependencies

RUN pip install --no-cache-dir pip-tools

COPY requirements/base.in requirements/integrations.in requirements/dev.in /app/requirements/
RUN pip-compile requirements/base.in --output-file=requirements/base.txt && \
    pip-compile requirements/integrations.in --output-file=requirements/integrations.txt && \
    pip-compile requirements/dev.in --output-file=requirements/dev.txt

# Development image
FROM base as development

# Copy compiled requirements
COPY --from=dependencies /app/requirements /app/requirements

# Install development dependencies
RUN pip install --no-cache-dir -r requirements/dev.txt

# Copy application code
COPY . /app/

# Production image
FROM base as production

# Copy compiled requirements
COPY --from=dependencies /app/requirements/base.txt /app/requirements/integrations.txt /app/requirements/

# Install production dependencies only
RUN pip install --no-cache-dir -r requirements/integrations.txt

# Copy application code
COPY . /app/

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2**: Create docker-compose.yml:

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build:
      context: .
      target: development
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/kave
      - MAILCHIMP_API_KEY=${MAILCHIMP_API_KEY}
      - MAILCHIMP_WEBHOOK_SECRET=${MAILCHIMP_WEBHOOK_SECRET}
      - SECRET_KEY=${SECRET_KEY}
      - DEBUG=true
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    depends_on:
      - db

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=kave
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

**Step 3**: Create .dockerignore file:

```
# .dockerignore
.git
.gitignore
.env
.env.example
.pytest_cache
.mypy_cache
__pycache__
*.pyc
*.pyo
*.pyd
.Python
.coverage
htmlcov
coverage.xml
*.db
venv
venv_new
```

### 4.2 Update README with Docker Instructions:

```markdown
## Docker Development Setup

This project includes Docker configuration for easy development and testing.

### Starting the Development Environment

1. Clone the repository
2. Create a `.env` file with required variables (see `.env.example`)
3. Start the docker-compose environment:
   ```bash
   docker-compose up -d
   ```
4. Access the API at http://localhost:8000/api/v1/docs

### Running Tests with Docker

```bash
docker-compose exec api pytest
```

### Building for Production

```bash
docker build -t kave-api:latest --target production .
```
```

## 5. Database Optimization

### 5.1 Improve Connection Pooling

**Step 1**: Enhance database session configuration:

```python
# app/db/session.py updates
# Improve engine creation with pooling settings
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=settings.SQL_ECHO,
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
)
```

**Step 2**: Add settings for database pooling:

```python
# app/core/config.py additions
    # Database pool settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
```

### 5.2 Implement Repository Pattern

**Step 1**: Create base repository:

```python
# app/db/repositories/base.py - create this file
"""Base repository for database operations."""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base repository with common CRUD operations."""

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        """Initialize repository with model and database session."""
        self.model = model
        self.db = db

    async def get(self, id: Any) -> Optional[ModelType]:
        """Get a record by ID."""
        result = await self.db.execute(select(self.model).filter(self.model.id == id))
        return result.scalars().first()

    async def get_multi(
        self, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records."""
        result = await self.db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, *, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """Update a record."""
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def remove(self, *, id: int) -> ModelType:
        """Remove a record."""
        obj = await self.get(id)
        await self.db.delete(obj)
        await self.db.commit()
        return obj
```

**Step 2**: Create specific repositories for models:

```python
# app/db/repositories/attachment.py - create this file
"""Repository for attachment operations."""

from app.db.repositories.base import BaseRepository
from app.models.email_data import Attachment
from app.schemas.webhook_schemas import EmailAttachment as AttachmentSchema

class AttachmentRepository(
    BaseRepository[Attachment, AttachmentSchema, AttachmentSchema]
):
    """Attachment repository with specialized methods."""
    pass
```

**Step 3**: Create repository factory for dependency injection:

```python
# app/db/repositories/factory.py - create this file
"""Factory functions for repositories."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.attachment import AttachmentRepository
from app.db.session import get_db
from app.models.email_data import Attachment

def get_attachment_repository(
    db: AsyncSession = Depends(get_db),
) -> AttachmentRepository:
    """Get attachment repository instance."""
    return AttachmentRepository(Attachment, db)
```

**Step 4**: Use repositories in services:

```python
# app/services/storage_service.py updates
from fastapi import Depends

from app.db.repositories.attachment import AttachmentRepository
from app.db.repositories.factory import get_attachment_repository

class StorageService:
    def __init__(
        self,
        attachment_repo: AttachmentRepository = Depends(get_attachment_repository),
    ):
        self.attachment_repo = attachment_repo
        # ...existing initialization
        
    async def get_attachment(self, attachment_id: int):
        """Get attachment by ID using repository."""
        return await self.attachment_repo.get(attachment_id)
```

## 6. Enhanced API Documentation

### 6.1 Add Examples and Descriptions to Schemas

**Step 1**: Enhance existing schemas with better metadata:

```python
# app/schemas/webhook_schemas.py updates
# Add for each schema class:

class WebhookResponse(BaseModel):
    """Schema for webhook API responses.
    
    Used to provide consistent response format for webhook processing endpoints.
    Includes status of the operation and a descriptive message.
    """

    status: str = Field(
        ..., 
        description="Status of the operation (success or error)",
        examples=["success", "error"]
    )
    message: str = Field(
        ..., 
        description="Human-readable result message",
        examples=["Email processed successfully", "Failed to process webhook: Invalid data format"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"status": "success", "message": "Email processed successfully"},
            "description": "Standard response format for webhook processing"
        }
    )
```

### 6.2 Add Request/Response Examples to Endpoints

**Step 1**: Enhance the documentation in endpoints:

```python
# app/api/v1/endpoints/email_webhooks.py updates
@router.post(
    "/mailchimp",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive MailChimp email webhook",
    description=(
        "Endpoint for MailChimp to send email data via webhook. "
        "Processes incoming emails, extracts data, "
        "and stores them in the database.\n\n"
        "**Authentication**: Requires valid webhook signature in headers.\n\n"
        "**Request Format**: Expects MailChimp webhook format with email content.\n\n"
        "**Processing**: Extracts email metadata, body content, and attachments."
    ),
    response_model=WebhookResponse,
    responses={
        status.HTTP_202_ACCEPTED: {
            "description": "Webhook received and processed successfully",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Email processed successfully",
                    }
                }
            },
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid request format or missing required data",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "Failed to process webhook: Invalid data format",
                    }
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing webhook signature",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "Unauthorized request: Invalid webhook signature",
                    }
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "An error occurred while processing the webhook",
            "model": WebhookResponse,
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "Failed to process webhook: Internal server error",
                    }
                }
            },
        },
    },
)
```

### 6.3 Configure Swagger UI Customizations

**Step 1**: Add custom Swagger UI to main.py:

```python
# app/main.py updates
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "AI agent platform that processes emails from MailChimp\n\n"
        "## Features\n\n"
        "- **Email Processing**: Receive and process emails via webhooks\n"
        "- **Attachment Handling**: Extract and store email attachments\n"
        "- **Storage Integration**: Optional S3 storage for attachments\n\n"
        "## Authentication\n\n"
        "API endpoints are protected by authentication mechanisms appropriate for each endpoint type:\n"
        "- **Webhook endpoints**: Validated using webhook signatures\n"
        "- **Management endpoints**: Protected with JWT authentication\n"
    ),
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
    swagger_ui_parameters={
        "defaultModelsExpandDepth": 1,
        "defaultModelExpandDepth": 2,
        "deepLinking": True,
        "displayRequestDuration": True,
        "filter": True,
    },
)
```

## 7. Monitoring and Observability

### 7.1 Structured Logging Implementation

**Step 1**: Add dependencies:

```
# requirements/base.in additions
structlog>=23.1.0
```

**Step 2**: Create logging configuration:

```python
# app/core/logging.py - create this file
"""Structured logging configuration."""

import logging
import sys
from typing import Any, Dict, List, Optional, Union

import structlog
from pydantic import BaseModel

from app.core.config import settings


class LogConfig(BaseModel):
    """Logging configuration."""

    LOGGER_NAME: str = "kave"
    LOG_FORMAT: str = "%(levelprefix)s | %(asctime)s | %(message)s"
    LOG_LEVEL: str = "INFO"

    # Logging config
    version: int = 1
    disable_existing_loggers: bool = False
    formatters: Dict[str, Dict[str, str]] = {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": LOG_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }
    handlers: Dict[str, Dict[str, Any]] = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": sys.stderr,
        },
    }
    loggers: Dict[str, Dict[str, Union[str, bool, List[str]]]] = {
        LOGGER_NAME: {"handlers": ["default"], "level": LOG_LEVEL},
    }


def setup_logging() -> None:
    """Set up structured logging."""
    config = LogConfig()

    # Configure processors based on environment
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if settings.DEBUG:
        # In development, format for human readability
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # In production, format as JSON for log aggregation
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.config.dictConfig(config.model_dump())
```

**Step 3**: Initialize logging in main.py:

```python
# app/main.py updates
from app.core.logging import setup_logging

# Initialize structured logging
setup_logging()
logger = structlog.get_logger("kave")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan events for the FastAPI application."""
    # Startup
    logger.info("application_starting")

    # App runs here
    yield

    # Shutdown: Close database connections
    await engine.dispose()
    logger.info("application_shutdown", message="Database connections closed")
```

### 7.2 Request ID Middleware

**Step 1**: Create middleware for request tracking:

```python
# app/core/middleware.py additions
import uuid
from contextvars import ContextVar
from typing import Callable, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

# Create a context variable to store the request ID
request_id_contextvar: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return request_id_contextvar.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to each request/response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request, adding a unique ID."""
        # Get request ID from header or generate a new one
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Store in context for this request
        token = request_id_contextvar.set(request_id)
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Reset the context variable to avoid leaks
            request_id_contextvar.reset(token)
```

**Step 3**: Add middleware to main.py:

```python
# app/main.py additions
from app.core.middleware import RequestIdMiddleware

# Add request ID middleware 
app.add_middleware(RequestIdMiddleware)
```

## 8. Simplified Testing Implementation

### 8.1 Create pytest-docker Configuration

**Step 1**: Add dependencies:

```
# requirements/dev.in additions
pytest-docker>=2.0.0
```

**Step 2**: Create docker-compose for testing:

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  postgres_test:
    image: postgres:15
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=kave_test
    ports:
      - "5433:5432"
```

**Step 3**: Configure pytest for Docker fixtures:

```python
# app/tests/conftest.py additions
import os
import pytest
import pytest_asyncio
import docker_services

# Docker services configuration
@pytest.fixture(scope="session")
def docker_compose_file():
    """Path to the docker-compose.test.yml file."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                         "docker-compose.test.yml")

@pytest.fixture(scope="session")
def postgres_service(docker_services):
    """Ensure that PostgreSQL service is up and running."""
    docker_services.start("postgres_test")
    public_port = docker_services.wait_for_service("postgres_test", 5433)
    return f"postgresql+asyncpg://postgres:postgres@localhost:{public_port}/kave_test"
```

## 9. Background Tasks Implementation

### 9.1 Create Task Manager for Background Tasks

**Step 1**: Create task utility:

```python
# app/core/tasks.py - create this file
"""Utilities for handling background tasks."""

import asyncio
import functools
import logging
from typing import Any, Callable, Dict, TypeVar

import structlog
from fastapi import BackgroundTasks

logger = structlog.get_logger("kave")

T = TypeVar("T")

def log_task_exception(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to log exceptions in background tasks."""
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Log the exception with contextual info
            logger.exception(
                "background_task_failed",
                task_name=func.__name__,
                error=str(e),
                args=args,
                kwargs=kwargs
            )
            # Re-raise to ensure the error is properly handled
            raise
    return wrapper

class TaskManager:
    """Manager for background tasks."""

    @staticmethod
    def add_task(
        background_tasks: BackgroundTasks,
        task_func: Callable,
        *args: Any,
        **kwargs: Any
    ) -> None:
        """Add a task to the background tasks queue.
        
        Args:
            background_tasks: FastAPI BackgroundTasks instance
            task_func: Async function to run in the background
            *args: Arguments to pass to the task function
            **kwargs: Keyword arguments to pass to the task function
        """
        # Wrap the task with exception logging
        @log_task_exception
        async def wrapped_task(*task_args: Any, **task_kwargs: Any) -> None:
            task_name = task_func.__name__
            logger.info("background_task_started", task_name=task_name)
            start_time = asyncio.get_event_loop().time()
            
            await task_func(*task_args, **task_kwargs)
            
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.info(
                "background_task_completed",
                task_name=task_name,
                execution_time_ms=round(execution_time * 1000, 2)
            )

        # Add the wrapped task to the background tasks
        background_tasks.add_task(wrapped_task, *args, **kwargs)
```

**Step 2**: Use TaskManager in endpoints:

```python
# app/api/v1/endpoints/email_webhooks.py updates
from fastapi import BackgroundTasks

from app.core.tasks import TaskManager

@router.post(
    "/mailchimp",
    # ...existing parameters
)
async def receive_mailchimp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    # ...existing parameters
) -> JSONResponse:
    try:
        # Parse webhook data
        webhook_data = await client.parse_webhook(request)

        # Process in background for faster response
        TaskManager.add_task(
            background_tasks,
            email_service.process_webhook,
            webhook_data
        )

        return JSONResponse(
            content={"status": "success", "message": "Email processing started"},
            status_code=status.HTTP_202_ACCEPTED,
        )
    except Exception as e:
        logger.error("webhook_processing_error", error=str(e))
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to process webhook: {str(e)}",
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
```

## 10. Enhanced Error Handling

### 10.1 Create Custom Exception Classes

**Step 1**: Create exceptions module:

```python
# app/core/exceptions.py - create this file
"""Custom exception classes and handlers."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

class KaveBaseException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class WebhookProcessingError(KaveBaseException):
    """Exception for webhook processing errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code)


class AttachmentProcessingError(KaveBaseException):
    """Exception for attachment processing errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code)


class StorageError(KaveBaseException):
    """Exception for storage service errors."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message, status_code)


async def kave_exception_handler(
    request: Request, exc: KaveBaseException
) -> JSONResponse:
    """Handler for application-specific exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.message},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handler for request validation errors."""
    # Extract and format validation errors
    errors = []
    for error in exc.errors():
        error_msg = {
            "loc": " -> ".join([str(loc) for loc in error["loc"]]),
            "msg": error["msg"],
            "type": error["type"],
        }
        errors.append(error_msg)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Request validation error",
            "errors": errors,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI application."""
    app.add_exception_handler(KaveBaseException, kave_exception_handler)
    app.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
```

**Step 2**: Register exception handlers in main.py:

```python
# app/main.py additions
from app.core.exceptions import register_exception_handlers

# Register exception handlers
register_exception_handlers(app)
```

**Step 3**: Use custom exceptions in services:

```python
# app/services/email_service.py updates
from app.core.exceptions import WebhookProcessingError

async def process_webhook(self, webhook_data):
    try:
        # Processing logic
        pass
    except ValueError as e:
        raise WebhookProcessingError(f"Invalid webhook data: {str(e)}")
    except Exception as e:
        raise WebhookProcessingError(
            f"Failed to process webhook: {str(e)}",
            status_code=500
        )
```

## Implementation Sequence

For optimal implementation, follow this sequence:

1. **Dependency Management** - Set up pip-tools and requirements
2. **API Versioning** - Refactor API structure for versioning
3. **Docker Setup** - Create Docker configuration for development
4. **Enhanced Security** - Implement CORS, rate limiting, and auth
5. **Database Optimization** - Improve connection pooling and repositories
6. **API Documentation** - Enhance schemas and endpoint documentation
7. **Error Handling** - Create custom exceptions and handlers
8. **Monitoring** - Implement structured logging and request tracking
9. **Background Tasks** - Add task manager for async operations
10. **Testing** - Simplify testing with Docker

Each step builds on previous steps, minimizing rework and ensuring a smooth implementation process. 