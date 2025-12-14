from .base import BaseRepository
from database.models.jobkorea import (
    RawJobkoreaJob, RawJobkoreaCompany, 
    RawJobkoreaJobImage, RawJobkoreaJobTag, RawJobkoreaJobBenefit
)

class JobkoreaRepository(BaseRepository):
    def __init__(self, session, logger):
        super().__init__(session, RawJobkoreaJob, RawJobkoreaJob.gno, logger)

    def save_job(self, data):
        if company_data := data["company"]:
            company = RawJobkoreaCompany(**company_data)
            self.session.merge(company)

        job_data = data["job"]
        images = job_data.pop("images", []) or []
        tags = job_data.pop("related_tags", []) or []
        benefits = job_data.pop("benefits", []) or []

        job = RawJobkoreaJob(**job_data)
        self.session.merge(job)

        for img_url in images:
            job.images.append(RawJobkoreaJobImage(image_url=img_url))

        for tag in tags:
            job.tags.append(RawJobkoreaJobTag(tag_name=tag))

        for benefit in benefits:
            job.benefits.append(RawJobkoreaJobBenefit(benefit_text=benefit))

        self.session.flush()