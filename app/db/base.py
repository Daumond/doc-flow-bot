from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from app.config import settings

engine = create_engine(settings.database_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()