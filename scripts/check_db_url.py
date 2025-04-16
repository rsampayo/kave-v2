#!/usr/bin/env python3
"""
Script to check database URL configuration.

This script displays the current database URLs from settings
to verify the effective URL being used by the application.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.core.config import settings
    
    print(f"DATABASE_URL: {settings.DATABASE_URL}")
    print(f"KAVE_DATABASE_URL: {settings.KAVE_DATABASE_URL}")
    print(f"effective_database_url: {settings.effective_database_url}")
    
    # Check if DB URL starts with sqlite or postgresql
    if settings.effective_database_url.startswith("sqlite"):
        print("WARNING: Using SQLite database!")
    elif settings.effective_database_url.startswith("postgresql"):
        print("SUCCESS: Using PostgreSQL database!")
    else:
        print(f"UNKNOWN DB TYPE: {settings.effective_database_url[:20]}...")
        
except Exception as e:
    print(f"ERROR: {str(e)}") 