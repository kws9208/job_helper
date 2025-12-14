from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, func, Boolean
from sqlalchemy.orm import relationship
from .base import Base


class RawWantedCompany(Base):
    __tablename__ = 'RAW_WANTED_COMPANIES'

    company_id = Column(Integer, primary_key=True)
    company_name = Column(String(200), nullable=False)
    introduction = Column(Text)
    founded_year = Column(Integer)
    industry = Column(String(200))
    employees = Column(String(100))
    classification = Column(String(100))
    address = Column(String(500))
    company_url = Column(String(500))
    company_logo_url = Column(String(500))
    reg_no_hash = Column(String(200))
    crawled_at = Column(TIMESTAMP, server_default=func.now())

    jobs = relationship("RawWantedJob", back_populates="company")


class RawWantedJob(Base):
    __tablename__ = 'RAW_WANTED_JOBS'

    job_id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('RAW_WANTED_COMPANIES.company_id'), nullable=False)
    
    position = Column(String(300), nullable=False)
    is_active = Column(Boolean, default=True)
    deadline = Column(String(50))
    address = Column(String(500))
    category_tag = Column(String(200))

    annual_from = Column(Integer)
    annual_to = Column(Integer)
    employment_type = Column(String(50))
    job_url = Column(String(1000))
    crawled_at = Column(TIMESTAMP, server_default=func.now())

    company = relationship("RawWantedCompany", back_populates="jobs")
    detail = relationship("RawWantedJobDetail", uselist=False, back_populates="job", cascade="all, delete-orphan")
    detail_tags = relationship("RawWantedJobDetailTag", back_populates="job", cascade="all, delete-orphan")
    skills = relationship("RawWantedJobSkill", back_populates="job", cascade="all, delete-orphan")
    attractions = relationship("RawWantedJobAttraction", back_populates="job", cascade="all, delete-orphan")
    images = relationship("RawWantedJobImage", back_populates="job", cascade="all, delete-orphan")


class RawWantedJobDetail(Base):
    __tablename__ = 'RAW_WANTED_JOB_DETAILS'

    job_id = Column(Integer, ForeignKey('RAW_WANTED_JOBS.job_id'), primary_key=True)
    
    intro = Column(Text)
    main_tasks = Column(Text)
    requirements = Column(Text)
    preferred_points = Column(Text)
    benefits = Column(Text)
    hire_rounds = Column(Text)

    job = relationship("RawWantedJob", back_populates="detail")

class RawWantedJobDetailTag(Base):
    __tablename__ = 'RAW_WANTED_JOB_DETAIL_TAGS'

    detail_tag_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('RAW_WANTED_JOBS.job_id'), nullable=False)
    
    tag_name = Column(String(200))

    job = relationship("RawWantedJob", back_populates="detail_tags")

class RawWantedJobSkill(Base):
    __tablename__ = 'RAW_WANTED_JOB_SKILLS'
    skill_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('RAW_WANTED_JOBS.job_id'), nullable=False)

    skill_name = Column(String(100))

    job = relationship("RawWantedJob", back_populates="skills")


class RawWantedJobAttraction(Base):
    __tablename__ = 'RAW_WANTED_JOB_ATTRACTIONS'
    attr_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('RAW_WANTED_JOBS.job_id'), nullable=False)

    title = Column(String(100))

    job = relationship("RawWantedJob", back_populates="attractions")

class RawWantedJobImage(Base):
    __tablename__ = 'RAW_WANTED_JOB_IMAGES'
    img_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('RAW_WANTED_JOBS.job_id'), nullable=False)

    image_url = Column(String(2048))
    
    job = relationship("RawWantedJob", back_populates="images")
    