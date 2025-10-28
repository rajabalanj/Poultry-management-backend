"""
Database Configuration Module

This module handles the database configuration and connection setup for the Poultry Management System.
It uses SQLAlchemy for ORM (Object-Relational Mapping) with PostgreSQL as the database.

The module includes:
- Database connection setup
- Session management
- Base model class definition
- Soft delete filter implementation
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, with_loader_criteria
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Database connection settings
# These settings can be configured via environment variables
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_SERVER = os.getenv("POSTGRES_SERVER", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "poultry_db")

# Create SQLAlchemy database URL
# Format: postgresql+psycopg2://user:password@server:port/database
SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Create SQLAlchemy engine
# The engine is the entry point to the SQLAlchemy ORM
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create SessionLocal class
# SessionLocal is a factory for creating new Session objects
# autocommit=False means we need to explicitly commit transactions
# autoflush=False means we need to explicitly flush changes to the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
# Base is the declarative base class that our ORM models will inherit from
Base = declarative_base()

@event.listens_for(Session, "do_orm_execute")
def add_soft_delete_filter(execute_state):
    """
    Event listener that automatically filters out "soft-deleted" records.

    This function adds a filter to all SELECT queries to exclude records
    where the 'deleted_at' field is not NULL. This implements a "soft delete"
    pattern where records are marked as deleted rather than actually removed
    from the database.

    Args:
        execute_state: The current execution state of the query
    """
    if (
        execute_state.is_select
        and not execute_state.is_relationship_load
    ):
        for entity in execute_state.statement.column_descriptions:
            if hasattr(entity['type'], 'deleted_at'):
                execute_state.statement = execute_state.statement.options(
                    with_loader_criteria(
                        entity['type'],
                        lambda cls: cls.deleted_at.is_(None),
                        include_aliases=True
                    )
                )

# Dependency to get database session
def get_db():
    """
    Dependency function that provides a database session.

    This function creates a new database session for each request and ensures
    that the session is properly closed after the request is completed.

    Yields:
        Session: A SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
