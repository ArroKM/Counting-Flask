from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Text, DateTime, create_engine
from sqlalchemy.orm import sessionmaker
import datetime
import os
from dotenv import load_dotenv

# Path absolut ke folder root (di mana .env berada)
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path)

Base = declarative_base()

class ZoneData(Base):
    __tablename__ = 'zone_data'

    zone = Column(String, primary_key=True)  # "hijau" / "merah"
    data = Column(Text)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

def get_engine():
    return create_engine(os.getenv("DATABASE_URL"))

def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def create_tables():
    engine = get_engine()
    Base.metadata.create_all(engine)