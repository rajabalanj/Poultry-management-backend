from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, with_loader_criteria
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Database connection settings
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_SERVER = os.getenv("POSTGRES_SERVER", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "poultry_db")

# Create SQLAlchemy database URL
SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Create SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

@event.listens_for(Session, "do_orm_execute")
def add_soft_delete_filter(execute_state):
    if (
        execute_state.is_select
        and not execute_state.is_relationship_load
    ):
        for entity in execute_state.statement.column_descriptions:
            if hasattr(entity['type'], 'deleted_at'):
                execute_state.statement = execute_state.statement.options(
                    with_loader_criteria(
                        entity['type'].deleted_at.is_(None),
                        include_aliases=True
                    )
                )

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()