from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, String, func
import uuid

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
