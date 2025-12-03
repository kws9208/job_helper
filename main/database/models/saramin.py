from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, func, Boolean
from sqlalchemy.orm import relationship
from .base import Base


class RawSaraminCompany(Base):
    __tablename__ = 'RAW_SARAMIN_COMPANIES'

    csn = Column(String(100), primary_key=True)
    company_name = Column(String(200), nullable=False)

    jobs = relationship("RawSaraminJob", back_populates="company")


class RawSaraminJob(Base):
    __tablename__ = 'RAW_SARAMIN_JOBS'

    rec_idx = Column(Integer, primary_key=True)
    csn = Column(String(100), ForeignKey('RAW_SARAMIN_COMPANIES.csn'), nullable=True)
    
    position = Column(String(300), nullable=False)
    is_active = Column(Boolean, default=True)
    job_url = Column(String(1000))

    content_type = Column(String(20))
    full_text = Column(Text)

    employment_type = Column(String(100))
    deadline = Column(String(50))
    address = Column(String(500))
    career = Column(String(100))
    education = Column(String(100))
    crawled_at = Column(TIMESTAMP, server_default=func.now())

    company = relationship("RawSaraminCompany", back_populates="jobs")
    images = relationship("RawSaraminJobImage", back_populates="job", cascade="all, delete-orphan")
    tags = relationship("RawSaraminJobTag", back_populates="job", cascade="all, delete-orphan")
    benefits = relationship("RawSaraminJobBenefit", back_populates="job", cascade="all, delete-orphan")


class RawSaraminJobImage(Base):
    __tablename__ = 'RAW_SARAMIN_JOB_IMAGES'
    img_id = Column(Integer, primary_key=True, autoincrement=True)
    rec_idx = Column(Integer, ForeignKey('RAW_SARAMIN_JOBS.rec_idx'), nullable=False)
    image_url = Column(Text)

    job = relationship("RawSaraminJob", back_populates="images")


class RawSaraminJobTag(Base):
    __tablename__ = 'RAW_SARAMIN_JOB_TAGS'
    tag_id = Column(Integer, primary_key=True, autoincrement=True)
    rec_idx = Column(Integer, ForeignKey('RAW_SARAMIN_JOBS.rec_idx'), nullable=False)
    tag_name = Column(String(100))

    job = relationship("RawSaraminJob", back_populates="tags")


class RawSaraminJobBenefit(Base):
    __tablename__ = 'RAW_SARAMIN_JOB_BENEFITS'
    benefit_id = Column(Integer, primary_key=True, autoincrement=True)
    rec_idx = Column(Integer, ForeignKey('RAW_SARAMIN_JOBS.rec_idx'), nullable=False)
    benefit_text = Column(String(1000))

    job = relationship("RawSaraminJob", back_populates="benefits")
    