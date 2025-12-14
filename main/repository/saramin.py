from .base import BaseRepository
from database.models.saramin import (
    RawSaraminJob, RawSaraminCompany, 
    RawSaraminJobImage, RawSaraminJobTag, RawSaraminJobBenefit
)

class SaraminRepository(BaseRepository):
    def __init__(self, session, logger):
        super().__init__(session, RawSaraminJob, RawSaraminJob.rec_idx, logger)

    def save_job(self, data):
        if company_data := data["company"]:
            company = RawSaraminCompany(**company_data)
            self.session.merge(company)

        job_data = data["job"]
        images = job_data.pop("images", []) or []
        tags = job_data.pop("related_tags", []) or []
        benefits = job_data.pop("benefits", []) or []

        job = RawSaraminJob(**job_data)
        self.session.merge(job)

        for img in images:
            job.images.append(RawSaraminJobImage(image_url=img))

        for tag in tags:
            job.tags.append(RawSaraminJobTag(tag_name=tag))

        for benefit in benefits:
            job.benefits.append(RawSaraminJobBenefit(benefit_text=benefit))

        self.session.flush()