from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./output/sourcer.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Candidate(Base):
    __tablename__ = "candidates"
    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False)
    title         = Column(String, default="")
    linkedin_url  = Column(String, unique=True, index=True)
    location      = Column(String, default="")
    role_searched = Column(String, default="")
    open_to_work  = Column(Boolean, default=True)
    snippet       = Column(String, default="")
    created_at    = Column(DateTime, default=datetime.utcnow)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
