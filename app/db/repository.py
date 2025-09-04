from contextlib import contextmanager
from typing import Generator, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect, event
from datetime import datetime

from app.db.base import SessionLocal, Base, engine
from app.db.models import User, Application, Document, Task, QuestionnaireAnswer
from app.config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Database schema version (increment this for schema changes)
SCHEMA_VERSION = 0

# Configure SQLAlchemy engine logging
echo_logger = get_logger('sqlalchemy.engine')


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        logger.debug("Database session started")
        yield session
        session.commit()
        logger.debug("Database session committed successfully")
    except Exception as e:
        logger.error(f"Session rollback due to error: {str(e)}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()
        logger.debug("Database session closed")

def get_db_version() -> int:
    """Get the current database schema version."""
    try:
        with session_scope() as session:
            # Check if version table exists
            inspector = inspect(engine)
            if 'alembic_version' not in inspector.get_table_names():
                logger.info("Database version table not found, assuming version 0")
                return 0
                
            result = session.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            if result:
                version = int(result[0])
                logger.debug(f"Current database version: {version}")
                return version
            return 0
    except Exception as e:
        logger.error(f"Error getting database version: {str(e)}")
        return 0

def verify_schema() -> Dict[str, Any]:
    """Verify the database schema and return status information."""
    status = {
        'version': 0,
        'tables_exist': False,
        'schema_valid': False,
        'error': None
    }
    
    try:
        with session_scope() as session:
            # Check version
            status['version'] = get_db_version()
            
            # Check if tables exist
            inspector = inspect(engine)
            required_tables = ['users', 'applications', 'documents', 'tasks']
            existing_tables = inspector.get_table_names()
            
            status['tables_exist'] = all(table in existing_tables for table in required_tables)
            status['schema_valid'] = status['version'] >= SCHEMA_VERSION
            
            logger.info(f"Database verification: {status}")
            return status
            
    except Exception as e:
        error_msg = f"Error verifying database schema: {str(e)}"
        logger.error(error_msg, exc_info=True)
        status['error'] = error_msg
        return status

def init_db() -> None:
    """Initialize the database and create all tables if they don't exist."""
    try:
        logger.info("Initializing database...")
        
        # Check if tables exist
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if not existing_tables:
            logger.info("No existing tables found. Creating all tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("All tables created successfully")
        else:
            logger.info(f"Found {len(existing_tables)} existing tables")
            
        # Verify schema
        status = verify_schema()
        
        if status['error']:
            logger.error(f"Database verification failed: {status['error']}")
            raise RuntimeError(f"Database verification failed: {status['error']}")
            
        if not status['tables_exist'] or not status['schema_valid']:
            logger.warning("Database schema is invalid or outdated")
            # Here you could add schema migration logic if needed
            
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.critical(f"Failed to initialize database: {str(e)}", exc_info=True)
        raise