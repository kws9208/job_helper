from .base import BaseRepository
from database.models.wanted import (
    RawWantedJob, RawWantedCompany, RawWantedJobDetail, 
    RawWantedJobDetailTag, RawWantedJobSkill, RawWantedJobAttraction, RawWantedJobImage
)

class WantedRepository(BaseRepository):
    def __init__(self, session):
        super().__init__(session, RawWantedJob, RawWantedJob.job_id)

    def save_job(self, data):
        company = RawWantedCompany(
            company_id=data["company_id"],
            company_name=data["company_name"]
        )
        self.session.merge(company)

        job_id = data["job_id"]
        existing_job = self.get_by_id(job_id)

        if existing_job:
            job = existing_job

            job.position = data.get("position")
            job.is_active = data.get("is_active")
            job.deadline = data.get("deadline")
            job.address = data.get("address")
            job.category_tag = data.get("category_tag")
            job.job_url = data.get("job_url")
            job.annual_from = data.get("annual_from")
            job.annual_to = data.get("annual_to")
            job.employment_type = data.get("employment_type")
            
            job.detail_tags.clear()
            job.skills.clear()
            job.attractions.clear()
            job.images.clear()
        else:
            job = RawWantedJob(
                job_id=job_id,
                company_id=data["company_id"],
                position=data.get("position"),
                is_active=True, 
                deadline=data.get("deadline"),
                address=data.get("address"),
                category_tag=data.get("category_tag"),
                job_url=data.get("job_url"),
                annual_from=data.get("annual_from"),
                annual_to=data.get("annual_to"),
                employment_type=data.get("employment_type")
            )
            self.session.add(job)

        detail_data = data.get("detail", {})
        job.detail = RawWantedJobDetail(
            intro=detail_data.get("intro"),
            main_tasks=detail_data.get("main_tasks"),
            requirements=detail_data.get("requirements"),
            preferred_points=detail_data.get("preferred_points"),
            benefits=detail_data.get("benefits"),
            hire_rounds=detail_data.get("hire_rounds")
        )

        detail_tags = data.get("detail_tags", [])
        for tag_text in detail_tags:
            job.detail_tags.append(RawWantedJobDetailTag(tag_name=tag_text))

        for skill in data.get("skill_tags", []):
            job.skills.append(RawWantedJobSkill(skill_name=skill))

        for attr in data.get("attraction_tags", []):
            job.attractions.append(RawWantedJobAttraction(title=attr))
            
        for img in data.get("images", []):
            job.images.append(RawWantedJobImage(image_url=img))
            
        self.session.flush()