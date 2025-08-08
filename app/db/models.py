from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base
import enum

class UserRole(str, enum.Enum):
    agent = "agent"
    rop = "rop"
    lawyer = "lawyer"
    admin = "admin"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    department_no = Column(String, nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.agent)
    created_at = Column(DateTime, default=datetime.utcnow)

class ApplicationStatus(str, enum.Enum):
    created = "CREATED"
    returned_rop = "RETURNED_ROP"
    to_lawyer = "TO_LAWYER"
    lawyer_task = "LAWYER_TASK"
    closed = "CLOSED"

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True)
    # В MVP без авторизации делаем agent_id nullable и фиксируем agent_name строкой
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rop_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    lawyer_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    deal_type = Column(String, nullable=False)
    contract_no = Column(String, nullable=True)
    protocol_date = Column(String, nullable=True)
    address = Column(String, nullable=True)
    object_type = Column(String, nullable=True)
    head_name = Column(String, nullable=True)
    agent_name = Column(String, nullable=True)

    yandex_folder = Column(String, nullable=True)
    yandex_public_url = Column(String, nullable=True)

    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.created)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class QuestionnaireAnswer(Base):
    __tablename__ = "questionnaire_answers"
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    question_key = Column(String, nullable=False)
    answer_value = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    doc_type = Column(String, nullable=False)  # passport/egrn/other
    file_name = Column(String, nullable=False)
    local_path = Column(String, nullable=False)
    yandex_path = Column(String, nullable=True)
    sha256 = Column(String, nullable=True)
    meta = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)