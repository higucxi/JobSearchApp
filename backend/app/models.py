from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Float, Index, func, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import relationship, mapped_column
from datetime import datetime, UTC
import uuid
from .database import Base

# Tables in DB

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key = True, default = uuid.uuid4)
    normalized_company = Column(String(255), nullable = False, index = True)
    normalized_title = Column(String(255), nullable = False, index = True)
    original_title = Column(String(255), nullable = False)
    description = Column(Text, nullable = False)
    location = Column(String(255), index = True)
    date_posted = Column(DateTime(timezone=True), nullable = False, index = True)
    created_at = Column(DateTime(timezone=True), default = datetime.now(UTC), nullable = False)

    # PostgreSQL full-text search
    search_vector = mapped_column(
        TSVECTOR().with_variant(Text(), "sqlite"),
        nullable=True
    )

    # Relationships
    sources = relationship("JobSource", back_populates = "job", cascade = "all, delete-orphan")
    application = relationship("Application", back_populates = "job", uselist = False, cascade = "all, delete-orphan")

    # Indexes for search performance
    __table_args__ = (
        Index('idx_search_vector', 'search_vector', postgresql_using = 'gin'),
        Index('idx_company_title', 'normalized_company', 'normalized_title'),
        Index('idx_date_posted_desc', date_posted.desc()),
    )

class JobSource(Base):
    __tablename__ = "job_sources"

    id = Column(Integer, primary_key = True, autoincrement = True)
    job_id = Column(UUID(as_uuid = True), ForeignKey('jobs.id', ondelete = 'CASCADE'), nullable = False)
    source = Column(String(50), nullable = False, index = True)
    source_job_id = Column(String(255), nullable = False)
    url = Column(Text, nullable = False)
    created_at = Column(DateTime(timezone=True), default = datetime.now(UTC), nullable = False)

    # relationship
    job = relationship("Job", back_populates = "sources")

    __table_args__ = (
        Index('idx_source_job_id', 'source', 'source_job_id', unique = True),
    )

class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid = True), primary_key = True, default = uuid.uuid4)
    job_id = Column(UUID(as_uuid = True), ForeignKey('jobs.id', ondelete = 'CASCADE'), nullable = False, unique = True)
    status = Column(String(50), nullable = False, default = 'Not Applied', index = True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default = datetime.now(UTC), nullable = False)
    updated_at = Column(DateTime(timezone=True), default = datetime.now(UTC), onupdate = datetime.now(UTC), nullable = False)

    # Relationship
    job = relationship("Job", back_populates = "application")

class SearchCache(Base):
    __tablename__ = "search_cache"
    
    id = Column(Integer, primary_key = True, autoincrement = True)
    query_hash = Column(String(64), unique = True, nullable = False, index = True)
    query_params = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False
    )
    results = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False
    )
    hit_count = Column(Integer, default = 1)
    created_at = Column(DateTime(timezone=True), default = datetime.now(UTC), nullable = False)
    updated_at = Column(DateTime(timezone=True), default = datetime.now(UTC), onupdate = datetime.now(UTC), nullable = False)