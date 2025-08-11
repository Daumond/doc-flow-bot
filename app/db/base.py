from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.session import Session
from typing import Generator
from app.config.config import settings

# Create the SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    pool_pre_ping=True
)

# Create a scoped session factory
SessionLocal = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        future=True  # Enable 2.0 style API
    )
)

# Base class for all models
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.
    Use this in FastAPI route dependencies.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize the database by creating all tables."""
    from app.db.models import User, Application, Document, Task, QuestionnaireAnswer  # noqa: F401
    
    # Import all models here to ensure they are registered with the Base
    Base.metadata.create_all(bind=engine)