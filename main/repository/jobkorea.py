from .base import BaseRepository
from database.models.jobkorea import (
    RawJobkoreaJob, RawJobkoreaCompany, 
    RawJobkoreaJobImage, RawJobkoreaJobTag, RawJobkoreaJobBenefit
)

class JobkoreaRepository(BaseRepository):
    def __init__(self, session):
        super().__init__(session, RawJobkoreaJob, RawJobkoreaJob.gno)

    def save_job(self, data):
        company = RawJobkoreaCompany(
            company_id=data["company_id"],
            company_name=data["company_name"]
        )
        self.session.merge(company)

        gno = data["gno"]
        existing_job = self.get_by_id(gno)

        if existing_job:
            job = existing_job
            job.position = data.get("position")
            job.is_active = data.get("is_active")
            job.job_url = data.get("job_url")
            job.full_text = data.get("detail_contents", {}).get("text")
            
            job.images.clear()
            job.tags.clear()
            job.benefits.clear()
        else:
            job = RawJobkoreaJob(
                gno=gno,
                company_id=data["company_id"],
                position=data.get("position"),
                is_active=True,
                job_url=data.get("job_url"),
                content_type=data.get("content_type"),
                full_text=data.get("detail_contents", {}).get("text"),
                employment_type=data.get("employment_type"),
                deadline=data.get("deadline"),
                address=data.get("address"),
                career=data.get("career"),
                education=data.get("education")
            )
            self.session.add(job)

        for img in data.get("detail_contents", {}).get("image") or []:
            job.images.append(RawJobkoreaJobImage(image_url=img))

        for tag in data.get("related_tags") or []:
            job.tags.append(RawJobkoreaJobTag(tag_name=tag))

        for benefit in data.get("benefits") or []:
            job.benefits.append(RawJobkoreaJobBenefit(benefit_text=benefit))

        self.session.flush()