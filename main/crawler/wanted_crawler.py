from .base_crawler import BaseCrawler
import time
import asyncio
import json
import pprint
from utils.logger import setup_logger

class WantedCrawler(BaseCrawler):
    def __init__(self, logger, k=5):
        super().__init__(base_url="https://www.wanted.co.kr", platform="Wanted", logger=logger, k=k)
        self.job_list_url = self.base_url + "/api/chaos/navigation/v1/results"
        self.job_detail_url = self.base_url + "/api/chaos/jobs/v4"
        self.company_url = "https://insight.wanted.co.kr/api"
        self.payload = {
            str(int(time.time() * 1000)): "",
            "country": "kr",
            "job_sort": "job.latest_order",
            "years": "-1",
            "locations": "all",
            "limit": 20,
            "offset": 0
        }
        self.logger = logger.getChild("Wanted")

    async def fetch_job_list(self):
        job_list_response = await self.request('GET', self.job_list_url, headers=self.header, params=self.payload)
        job_ids = [job['id'] for job in job_list_response.json()["data"]]
        return job_ids

    async def fetch_details_by_ids(self, job_ids):
        self.logger.info(f"🔍 {len(job_ids)}개의 상세 페이지 수집 시작...")
        tasks = [self.fetch_job_detail(job_id) for job_id in job_ids]
        results = await asyncio.gather(*tasks)
        return [job for job in results if job is not None]
    
    async def fetch_job_detail(self, job_id):
        job_url = f"{self.job_detail_url}/{job_id}/details"
        try:
            job_detail_response = await self.request('GET', job_url)
            job_detail_data = self.parse_job_data(job_detail_response.json(), job_url)
            if company_id := job_detail_data.get('company_id'):
                company_info_data = await self.fetch_company_info(company_id)
        except Exception:
            return None
        return {
            "company": company_info_data if company_id else None,
            "job": job_detail_data,
        }

    def parse_job_data(self, details_json, url):
        try:
            if details_json.get('error') is None and details_json.get("message") == "ok":
                job_data = details_json['data']['job']
                job_details_dict = job_data.get('detail', {})
                del job_details_dict["id"]

                return {
                    "job_id": job_data.get('id'),
                    "job_url": url,
                    "position": job_details_dict.pop('position'),
                    "is_active": True if job_data.get('status') == "active" else False,
                    "deadline": job_data.get('due_time') if job_data.get('due_time') else "상시채용",
                    "address": job_data.get('address', {}).get('full_location'),
                    "annual_from": job_data.get('annual_from'),
                    "annual_to": job_data.get('annual_to'),
                    "employment_type": job_data.get('employment_type'),
                    "attraction_tags": [tag['title'] for tag in job_data.get('attraction_tags', [])],
                    "category_tag": job_data.get('category_tag', {}).get('parent_tag').get('text'),
                    "detail_tags": [child_tag['text'] for child_tag in job_data.get('category_tag', {}).get('child_tags', [])],
                    "skill_tags": [skill['text'] for skill in job_data.get('skill_tags', [])],
                    "description": job_details_dict,
                    "company_id": job_data.get('company').get('id')
                }
            else:
                self.logger.warning(f"[API 에러] {details_json.get('message')}")
                return None
        except Exception as e:
            self.logger.error(f"[파싱 에러] id: {job_data.get('id')} / {e}", exc_info=True)
            return None
    
    async def fetch_company_info(self, company_id):
        try:
            company_url = f"{self.company_url}/company/{company_id}/info-for-wanted"
            company_info_response = await self.request('GET', company_url)
            company_info_data = self.parse_company_data(company_info_response.json(), company_url)
            pprint.pprint(company_info_data)
            if company_info_data.get('reg_no_hash'):
                employee_info_response = await self.request('GET', f"{self.company_url}/wanted/{company_info_data.get('reg_no_hash')}/employees")
                employees_info_data = employee_info_response.json()
                pprint.pprint(employees_info_data)
                if employee_info := employees_info_data.get('employees'):
                    employees = employee_info.get(employees_info_data.get('defaultSource')).get('employee')
                    company_info_data['employees'] = employees
        except Exception as e:
            self.logger.error(f"⚠️  파싱 중 에러 (ID: {company_id}): {e}")
            return None
        return company_info_data

    def parse_company_data(self, data_json, company_url):
        try:
            if data_json.get('error') and data_json.get("message") == "Item Not Found":
                self.logger.warning(f"[API 에러] {data_json.get('status')}")
                return None
            else:
                return {
                    "company_id": data_json.get('wantedCompanyId'),
                    "company_name": data_json.get('name'),
                    "company_logo_url": data_json.get('logo'),
                    "founded_year": data_json.get('foundedYear'),
                    "address": data_json.get('address').get('full_location'),
                    "introduction": data_json.get('description'),
                    "industry": data_json.get('industryName'),
                    "reg_no_hash": data_json.get('regNoHash'),
                }

        except Exception as e:
            self.logger.warning(f"[파싱 에러] id: {data_json.get('wantedCompanyId')} / {e}",  exc_info=True)
            return None

    async def run(self):
        self.logger.info("=== Wanted 크롤러 시작 ===")
        job_ids = await self.fetch_job_list()

        if not job_ids:
            self.logger.info("수집된 공고 ID가 없습니다.")
            return []
        
        self.logger.info(f"총 {len(job_ids)}개의 공고를 수집합니다.")

        tasks = [self.fetch_job_detail(job_id) for job_id in job_ids]
        
        results = await asyncio.gather(*tasks)

        final_jobs = [job for job in results if job is not None]
        self.logger.info(f"=== Wanted 크롤러 종료 (성공: {len(final_jobs)}건) ===")
        return final_jobs

async def main():
    logger = setup_logger("Crawler")
    logger.info("🚀 [테스트] 원티드 크롤러 실행 중...")
    async with WantedCrawler(logger=logger) as crawler:
        offset = crawler.payload['limit']
        while crawler.payload['offset'] < 1*offset:
            start = time.time()
            results = await crawler.run()
            end = time.time()
            
            if results:
                logger.info(f"\n✅ 총 {len(results)}개의 공고 수집 완료!")
                logger.info("--- [첫 번째 공고 샘플 데이터] ---")
                pprint.pprint(results[0])
            else:
                logger.info("\n❌ 수집된 데이터가 없습니다. (API 응답 확인 필요)")
            logger.info(f"Page: {crawler.payload['offset']}, 소요시간: {end - start}")
            crawler.payload['offset'] += offset

if __name__ == "__main__":
    asyncio.run(main())