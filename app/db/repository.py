from contextlib import contextmanager
from typing import Generator, Optional, Dict, Any
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from datetime import datetime

from app.db.base import SessionLocal, Base, engine
from app.db.models import User, Application, Document, Task, QuestionnaireAnswer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database schema version (increment this for schema changes)
SCHEMA_VERSION = 1

@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Session rollback due to error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def get_db_version() -> Optional[int]:
    """Get the current database schema version."""
    with session_scope() as session:
        # Check if version table exists
        inspector = inspect(engine)
        if 'alembic_version' in inspector.get_table_names():
            # Using Alembic for migrations
            result = session.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            if result:
                return int(result[0].split('_')[0])  # Extract numeric version
        elif 'schema_version' in inspector.get_table_names():
            # Using our custom versioning
            result = session.execute(text("SELECT version FROM schema_version LIMIT 1")).fetchone()
            if result:
                return result[0]
    return None

def verify_schema() -> Dict[str, Any]:
    """Verify the database schema and return status information."""
    inspector = inspect(engine)
    result = {
        'tables_ok': True,
        'missing_tables': [],
        'current_version': get_db_version(),
        'expected_version': SCHEMA_VERSION,
        'is_up_to_date': False
    }
    
    # Check for required tables
    required_tables = {
        'users', 'applications', 'documents', 
        'questionnaire_answers', 'tasks', 'schema_version'
    }
    existing_tables = set(inspector.get_table_names())
    missing_tables = required_tables - existing_tables
    
    if missing_tables:
        result['tables_ok'] = False
        result['missing_tables'] = list(missing_tables)
    
    result['is_up_to_date'] = (
        result['tables_ok'] and 
        result['current_version'] is not None and
        result['current_version'] >= SCHEMA_VERSION
    )
    
    return result

def init_db():
    """Initialize the database and create all tables if they don't exist."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create schema version table if it doesn't exist
    with engine.connect() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                upgraded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))
        
        # Insert initial version if not exists
        result = conn.execute(text("SELECT version FROM schema_version LIMIT 1")).fetchone()
        if not result:
            conn.execute(
                text("INSERT INTO schema_version (version) VALUES (:version)"),
                {"version": SCHEMA_VERSION}
            )
    
    logger.info(f"Database initialized with schema version {SCHEMA_VERSION}")
    
    # Verify the schema
    status = verify_schema()
    if not status['tables_ok']:
        logger.warning(f"Missing tables: {', '.join(status['missing_tables'])}")
    
    return status