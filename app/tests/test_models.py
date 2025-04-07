"""Test models for database verification."""

from sqlalchemy import Column, Integer, String

from app.db.session import Base


class SimpleModel(Base):
    """A simple model for testing database operations."""

    __tablename__ = "simple_test"
    __table_args__ = {"extend_existing": True}  # Allow redefining the table

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __repr__(self) -> str:
        return f"<SimpleModel(id={self.id}, name={self.name})>"
