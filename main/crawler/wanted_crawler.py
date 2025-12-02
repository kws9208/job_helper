from .base_crawler import BaseCrawler
import time
import asyncio
import httpx
import json
import traceback
import pprint

class WantedCrawler(BaseCrawler):
    def __init__(self, k=5):
        super().__init__(base_url="https://www.wanted.co.kr", platform="Wanted", k=k)
        self.job_list_url = self.base_url + "/api/chaos/navigation/v1/results"
        self.job_detail_url = self.base_url + "/api/chaos/jobs/v4"
        self.payload = {
            str(int(time.time() * 1000)): "",
            "country": "kr",
            "job_sort": "job.latest_order",
            "years": "-1",
            "locations": "all",
            "limit": 20,
            "offset": 0
        }

    async def fetch_job_list(self):
        job_list_response = await self.request('GET', self.job_list_url, headers=self.header, params=self.payload)
        job_ids = [job['id'] for job in job_list_response.json()["data"]]
        return job_ids

    async def fetch_details_by_ids(self, job_ids):
        print(f" {self.platform} | 🔍 {len(job_ids)}개의 상세 페이지 수집 시작...")
        tasks = [self.fetch_job_detail(job_id) for job_id in job_ids]
        results = await asyncio.gather(*tasks)
        return [job for job in results if job is not None]
    
    async def fetch_job_detail(self, job_id):
        job_url = f"{self.job_detail_url}/{job_id}/details"
        try:
            job_detail_response = await self.request('GET', job_url)
        except Exception:
            return None
        return self.parse_job_data(job_detail_response.json(), job_url)

    def parse_job_data(self, details_json, url):
        try:
            if details_json.get('error') is None and details_json.get("message") == "ok":
                job_data = details_json['data']['job']
                job_details_dict = job_data.get('detail', {})

                return {
                    "job_id": job_data.get('id'),
                    "job_url": url,
                    "position": job_details_dict.get('position'),
                    "is_active": True if job_data.get('status') == "active" else False,
                    "deadline": job_data.get('due_time') if job_data.get('due_time') else "상시채용",
                    "detail": job_details_dict,
                    "attraction_tags": [tag['title'] for tag in job_data.get('attraction_tags', [])],
                    "company_id": job_data.get('company', {}).get('id'),
                    "company_name": job_data.get('company', {}).get('name'),
                    "company_logo": job_data.get('company', {}).get('logo_img').get('origin'),
                    "address": job_data.get('address', {}).get('full_location'),
                    "category_tag": job_data.get('category_tag', {}).get('parent_tag').get('text'),
                    "detail_tags": [child_tag['text'] for child_tag in job_data.get('category_tag', {}).get('child_tags', [])],
                    "skill_tags": [skill['text'] for skill in job_data.get('skill_tags', [])],
                    "annual_from": job_data.get('annual_from'),
                    "annual_to": job_data.get('annual_to'),
                    "employment_type": job_data.get('employment_type')
                }
            else:
                print(f"[API 에러] {details_json.get('message')}")
                return None
        except Exception as e:
            print(f"[파싱 에러] id: {job_data.get('id')} / {e}")
            traceback.print_exc()
            return None

    async def run(self):
        print("=== Wanted 크롤러 시작 ===")
        job_ids = await self.fetch_job_list()

        if not job_ids:
            print("수집된 공고 ID가 없습니다.")
            return []
        
        print(f"총 {len(job_ids)}개의 공고를 수집합니다.")

        tasks = [self.fetch_job_detail(job_id) for job_id in job_ids]
        
        results = await asyncio.gather(*tasks)

        final_jobs = [job for job in results if job is not None]
        print(f"=== Wanted 크롤러 종료 (성공: {len(final_jobs)}건) ===")
        return final_jobs

async def main():
    print("🚀 [테스트] 원티드 크롤러 실행 중...")
    async with WantedCrawler() as crawler:
        start = time.time()
        results = await crawler.run()
        end = time.time()
        
        if results:
            print(f"\n✅ 총 {len(results)}개의 공고 수집 완료!")
            print("--- [첫 번째 공고 샘플 데이터] ---")
            pprint.pprint(results[0])
            print([res['deadline'] for res in results])
        else:
            print("\n❌ 수집된 데이터가 없습니다. (API 응답 확인 필요)")
        print("소요시간:", end - start)

if __name__ == "__main__":
    asyncio.run(main())