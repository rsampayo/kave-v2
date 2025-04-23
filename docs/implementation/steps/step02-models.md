# Step 2: Define AttachmentTextContent Model & Relationship

## Goal
Create the SQLAlchemy model structure for storing OCR results and establish relationships with existing models.

## TDD (RED)
Write a failing test in `app/tests/test_unit/test_models_documentation.py` (or a new `test_models.py`) that attempts to import and instantiate the `AttachmentTextContent` model and verify its relationship with `Attachment`.

```python
# app/tests/test_unit/test_models.py (or append to existing test file)
import pytest
from sqlalchemy import Text
from sqlalchemy.orm import relationship

def test_attachment_text_content_model():
    """Test that AttachmentTextContent model exists and has the expected attributes."""
    try:
        # Import the model - this will fail until it's implemented
        from app.models.attachment_text_content import AttachmentTextContent
        from app.models.email_data import Attachment
        
        # Create an instance with test data
        text_content = AttachmentTextContent(
            attachment_id=1,
            page_number=1,
            text_content="Test OCR content"
        )
        
        # Verify attributes
        assert hasattr(text_content, "id")
        assert hasattr(text_content, "attachment_id")
        assert hasattr(text_content, "page_number")
        assert hasattr(text_content, "text_content")
        assert hasattr(text_content, "attachment")
        
        # Verify values
        assert text_content.attachment_id == 1
        assert text_content.page_number == 1
        assert text_content.text_content == "Test OCR content"
        
        # Check relationship with Attachment
        attachment = Attachment(id=1)
        assert hasattr(attachment, "text_contents")
        
    except ImportError:
        pytest.fail("Could not import AttachmentTextContent model")
    except Exception as e:
        pytest.fail(f"Failed to create AttachmentTextContent instance: {e}")
```

## Implementation (GREEN)

### 1. Create AttachmentTextContent Model

Create a new file `app/models/attachment_text_content.py` with the following content:

```python
# app/models/attachment_text_content.py
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.email_data import Attachment


class AttachmentTextContent(Base):
    """
    Stores OCR-extracted text content from PDF attachments, page by page.
    
    This model maintains a one-to-many relationship with the Attachment model,
    where each record represents the text content of a single page from a PDF attachment.
    """
    __tablename__ = "attachment_text_content"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    attachment_id: Mapped[int] = mapped_column(ForeignKey("attachments.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(nullable=False)
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationship back to Attachment
    attachment: Mapped["Attachment"] = relationship("Attachment", back_populates="text_contents")
```

### 2. Update Attachment Model

Modify `app/models/email_data.py` to add the relationship to the `Attachment` model:

```python
# Inside app/models/email_data.py, in the Attachment class
# Add this import at the top if needed
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.attachment_text_content import AttachmentTextContent

# Add this relationship property to the Attachment class
text_contents: Mapped[List["AttachmentTextContent"]] = relationship(
    "AttachmentTextContent", back_populates="attachment", cascade="all, delete-orphan"
)
```

### 3. Update Models Init File

Ensure the new model is imported and exposed in `app/models/__init__.py`:

```python
# app/models/__init__.py - update with the following import
from app.models.attachment_text_content import AttachmentTextContent
```

## Quality Check (REFACTOR)
Run the following code quality tools and fix any issues:
```bash
black .
isort .
flake8 .
mypy app
```

## Testing (REFACTOR)
Run the test to verify the model has been implemented correctly:
```bash
pytest app/tests/test_unit/test_models.py::test_attachment_text_content_model
```

The test should now pass.

## Self-Verification Checklist
- [ ] Does the `AttachmentTextContent` model file exist with the correct content?
- [ ] Does the model have the correct columns, types, and relationships?
- [ ] Is the relationship added to the `Attachment` model?
- [ ] Is the new model imported in `app/models/__init__.py`?
- [ ] Do all the tests pass?
- [ ] Do all quality checks pass?

After completing this step, stop and request approval before proceeding to Step 3. 