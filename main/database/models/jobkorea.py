from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, func, Boolean
from sqlalchemy.orm import relationship
from .base import Base


class RawJobkoreaCompany(Base):
    __tablename__ = 'RAW_JOBKOREA_COMPANIES'

    company_id = Column(String(100), primary_key=True)
    company_name = Column(String(200), nullable=False)

    jobs = relationship("RawJobkoreaJob", back_populates="company")


class RawJobkoreaJob(Base):
    __tablename__ = 'RAW_JOBKOREA_JOBS'

    gno = Column(Integer, primary_key=True)
    company_id = Column(String(100), ForeignKey('RAW_JOBKOREA_COMPANIES.company_id'), nullable=False)
    
    position = Column(String(300), nullable=False)
    is_active = Column(Boolean, default=True)
    job_url = Column(String(1000))

    content_type = Column(String(20))
    full_text = Column(Text)

    employment_type = Column(String(200))
    deadline = Column(String(50))
    address = Column(String(500))
    career = Column(String(100))
    education = Column(String(100))
    crawled_at = Column(TIMESTAMP, server_default=func.now())

    company = relationship("RawJobkoreaCompany", back_populates="jobs")
    images = relationship("RawJobkoreaJobImage", back_populates="job", cascade="all, delete-orphan")
    tags = relationship("RawJobkoreaJobTag", back_populates="job", cascade="all, delete-orphan")
    benefits = relationship("RawJobkoreaJobBenefit", back_populates="job", cascade="all, delete-orphan")


class RawJobkoreaJobImage(Base):
    __tablename__ = 'RAW_JOBKOREA_JOB_IMAGES'
    img_id = Column(Integer, primary_key=True, autoincrement=True)
    gno = Column(Integer, ForeignKey('RAW_JOBKOREA_JOBS.gno'), nullable=False)
    image_url = Column(Text)

    job = relationship("RawJobkoreaJob", back_populates="images")


class RawJobkoreaJobTag(Base):
    __tablename__ = 'RAW_JOBKOREA_JOB_TAGS'
    tag_id = Column(Integer, primary_key=True, autoincrement=True)
    gno = Column(Integer, ForeignKey('RAW_JOBKOREA_JOBS.gno'), nullable=False)
    tag_name = Column(String(100))

    job = relationship("RawJobkoreaJob", back_populates="tags")


class RawJobkoreaJobBenefit(Base):
    __tablename__ = 'RAW_JOBKOREA_JOB_BENEFITS'
    benefit_id = Column(Integer, primary_key=True, autoincrement=True)
    gno = Column(Integer, ForeignKey('RAW_JOBKOREA_JOBS.gno'), nullable=False)
    benefit_text = Column(String(500))

    job = relationship("RawJobkoreaJob", back_populates="benefits")
    