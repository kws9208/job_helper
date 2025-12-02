from .base import BaseRepository
from database.models.saramin import (
    RawSaraminJob, RawSaraminCompany, 
    RawSaraminJobImage, RawSaraminJobTag, RawSaraminJobBenefit
)

class SaraminRepository(BaseRepository):
    def __init__(self, session):
        super().__init__(session, RawSaraminJob, RawSaraminJob.rec_idx)

    def save_job(self, data):
        company = RawSaraminCompany(
            csn=data["csn"],
            company_name=data["company_name"]
        )
        self.session.merge(company)

        rec_idx = data["rec_idx"]
        existing_job = self.get_by_id(rec_idx)

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
            job = RawSaraminJob(
                rec_idx=rec_idx,
                csn=data["csn"],
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
            job.images.append(RawSaraminJobImage(image_url=img))

        for tag in data.get("related_tags") or []:
            job.tags.append(RawSaraminJobTag(tag_name=tag))

        for benefit in data.get("benefits") or []:
            job.benefits.append(RawSaraminJobBenefit(benefit_text=benefit))

        self.session.flush()