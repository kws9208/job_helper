from .base import BaseRepository
from database.models.wanted import (
    RawWantedJob, RawWantedCompany, RawWantedJobDetail, 
    RawWantedJobDetailTag, RawWantedJobSkill, RawWantedJobAttraction, RawWantedJobImage
)

class WantedRepository(BaseRepository):
    def __init__(self, session, logger):
        super().__init__(session, RawWantedJob, RawWantedJob.job_id, logger)

    def need_job_crawling(self, id_value, expire_days=7):
        return self.need_crawling(id_value, expire_days, RawWantedJob, RawWantedJob.job_id)

    def need_company_crawling(self, id_value, expire_days=30):
        return self.need_crawling(id_value, expire_days, RawWantedCompany, RawWantedCompany.company_id)

    def save_job(self, data):
        if company_data := data["company"]:
            company = RawWantedCompany(**company_data)
            self.session.merge(company)

        job_data = data["job"]
        job_detail = job_data.pop("description")
        detail_tags = job_data.pop("detail_tags", [])
        skill_tags = job_data.pop("skill_tags", [])
        attraction_tags = job_data.pop("attraction_tags", [])
        images = job_data.pop("images", [])

        job = RawWantedJob(**job_data)
        job.detail = RawWantedJobDetail(**job_detail)
        self.session.merge(job)
        
        for tag_text in detail_tags:
            job.detail_tags.append(RawWantedJobDetailTag(tag_name=tag_text))

        for skill in skill_tags:
            job.skills.append(RawWantedJobSkill(skill_name=skill))

        for attr in attraction_tags:
            job.attractions.append(RawWantedJobAttraction(title=attr))
            
        for img in images:
            job.images.append(RawWantedJobImage(image_url=img))

        self.session.flush()