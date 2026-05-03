import asyncio
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

class Campaign(Base):
    __tablename__ = 'campaigns'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    posts = relationship("Post", back_populates="campaign", cascade="all, delete-orphan")

class Channel(Base):
    __tablename__ = 'channels'
    
    handle = Column(String, primary_key=True)   # without @
    name = Column(String, nullable=False)
    subscribers = Column(Integer, nullable=True)  # auto from Telethon
    avg_reach = Column(Integer, nullable=True)    # auto: avg views of last 50 posts
    price_excl_vat = Column(Float, nullable=True) # price in UZS without VAT
    price_incl_vat = Column(Float, nullable=True) # price in UZS with VAT
    topic = Column(String, nullable=True)
    geo = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UTMLink(Base):
    __tablename__ = 'utm_links'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    channel_handle = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    full_url = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    campaign = relationship("Campaign")


class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=True)
    channel_handle = Column(String, ForeignKey('channels.handle'), nullable=True)
    post_id = Column(Integer, nullable=False)  # ID in telegram
    name = Column(String, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)  # date of publication from Telegram
    is_tracking_active = Column(Boolean, default=True)
    
    campaign = relationship("Campaign", back_populates="posts")
    metrics_history = relationship("PostMetricsHistory", back_populates="post", cascade="all, delete-orphan")

class PostMetricsHistory(Base):
    __tablename__ = 'post_metrics_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey('posts.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    views = Column(Integer, default=0)
    forwards = Column(Integer, default=0)
    replies = Column(Integer, default=0)
    positive_reactions = Column(Integer, default=0)
    negative_reactions = Column(Integer, default=0)
    subscribers = Column(Integer, default=0)
    
    post = relationship("Post", back_populates="metrics_history")

class Setting(Base):
    __tablename__ = 'settings'
    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    role = Column(String, default='user') # 'admin' or 'user'
    username = Column(String, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'statsbot.db')

# Initialize SQLite engine
engine = create_async_engine(f'sqlite+aiosqlite:///{DB_PATH}', echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Database helper functions
async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
