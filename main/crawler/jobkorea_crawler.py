from .base_crawler import BaseCrawler
import time
import asyncio
import httpx
import json
import traceback
import requests
import pprint
import html2text
from bs4 import BeautifulSoup
import re
import emoji

class JobkoreaCrawler(BaseCrawler):
    def __init__(self, k=5):
        super().__init__(base_url="https://www.jobkorea.co.kr", platform="Jobkorea", k=k)
        self.job_list_url = self.base_url + "/Search/api/display/v2/jobs"
        self.job_detail_url = "https://m.jobkorea.co.kr/Recruit/GIReadDetailContentIframe"
        self.job_summary_info = "https://m.jobkorea.co.kr/Recruit/SwipeGIReadInfo"
        self.job_basic_url = "https://m.jobkorea.co.kr/Recruit/GI_Read"
        self.payload = {
            "page": 0,
            "pageSize": 20,
            "sortProperty": "2",
            "sortDirection": "DESC",
            "keyword": ""
        }

        self.keyword = ['주요업무', '담당업무', '자격요건', '우대사항', '지원자격', '모집부문', '근무조건', '전형절차', \
                          '자격', '우대', '모집', '업무', '지원', '전형', '마감', '근무']

    async def fetch_job_list(self):
        response = await self.request("POST", self.job_list_url, headers=self.header, json=self.payload)
        gnos = [job["id"] for job in response.json().get('content')]
        return gnos
    
    async def fetch_details_by_ids(self, gnos):
        print(f" {self.platform} | 🔍 {len(gnos)}개의 상세 페이지 수집 시작...")
        tasks = [self.fetch_job_detail(gno) for gno in gnos]
        results = await asyncio.gather(*tasks)
        return [job for job in results if job is not None]

    async def fetch_job_detail(self, gno):
        response = await self.request("GET", f'{self.job_detail_url}/{gno}', headers=self.header)
        html_content = response.text

        job_summaray = await self.fetch_job_summary(gno)
        detail_contents = self.get_detailed_contents(html_content)

        return {
            "gno": gno,
            "job_url": f"https://m.jobkorea.co.kr/Recruit/GI_Read/{gno}",
            **job_summaray, 
            **detail_contents
        }
    
    async def fetch_job_summary(self, gno):
        self.header.update({"X-Requested-With": "XMLHttpRequest"})
        response = await self.request("POST", f'{self.job_summary_info}/{gno}', headers=self.header)
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        summary_dict = dict()
        if summary_items := soup.select_one('div#rowGuidelines'):
            for item in summary_items.select('div.field'):
                key = item.select_one('div.label').text.strip()
                value = item.select_one('div.value').get_text(separator=" ", strip=True)
                if key == "경력":
                    summary_dict.update({"career": value})
                elif key == "학력":
                    summary_dict.update({"education": value})
                elif key == "고용형태":
                    summary_dict.update({"employment_type": value})
        else:
            summary_dict.update({
                'career': soup.select_one('ul.view-top-list > li.vl-history').text.strip()
            })

        if dates := soup.select('div.receiptTermDate'):
            deadline = " ".join(dates[-1].stripped_strings).replace("채용시","").replace("마감","").replace("\n","").strip()
            if "시작" in deadline:
                deadline = "상시채용"
        elif dates := soup.select_one('ul.view-top-list > li.vl-date'):
            deadline = dates.contents[0].strip()

        if has_company := soup.select_one('#rowCompany'):
            if has_company.select_one('div.companyHeader'):
                company_name = has_company.select_one('div.companyHeader > div.header > h2').text.strip()
            elif has_company.select_one('div.info-company'):
                company_name = has_company.select_one('div.info-company > p').text.strip()
            summary_dict.update({"company_name": company_name})

            for selector in ['div.row-footer > a', 'div.header_wrap > a']:
                if company_id := has_company.select_one(selector):
                    company_id = company_id.get('href')
                    if "company" in company_id:
                        company_id = company_id.split('/')[2].split('?')[0]
                    elif "Recruit" in company_id:
                        company_id = company_id.split('?')[0].split('/')[-1]
                    else:
                        company_id = company_id.split('?')[0].split('/')[-1]
                    summary_dict.update({"company_id": company_id})
                    break

        if has_tag := soup.select_one('#rowKeyword'):
            related_tags = has_tag.select_one('div.keyword-list').text.strip().split('\n')
        elif has_tag := soup.select_one('#rowTag'):
            tag_items = has_tag.select('ul > li')
            related_tags = [item.text.strip() for item in tag_items]

        has_benefit = soup.select_one('#rowBenefits')
        if has_benefit:
            benefit_items = has_benefit.select('div.benefits-list > div.field')
            benefits = [f"{item.select_one('div.label').text.strip()}: {item.select_one('div.value').text.strip()}" for item in benefit_items]
        elif has_benefit := soup.select('#rowCompany'):
            benefit_items = soup.select('ul.info-company-tag > li')
            benefits = [item.text.strip() for item in benefit_items]

        if has_address := soup.select_one('div.row.rowLocation'):
            address = has_address.select_one('div.workAddr').text.strip()
        elif has_address := soup.select_one('#rowCompany > div.generalSummary'):
            address = None
        elif has_address := soup.select_one('#rowCompany > ul.info-company-list'):
            address = soup.select_one('ul.info-company-list > li:nth-child(4) > dl > dd').contents[0].strip()

        response = await self.request("GET", f'{self.job_basic_url}/{gno}', headers=self.header)
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')

        if has_info := soup.select_one('div.recruit-article-content'):
            position = has_info.select_one('h1.recruit-title').text.strip()
        is_active = not soup.select('div.navbarFooter > button')[-1].get('disabled')

        return {
            **summary_dict,
            "position": position,
            "deadline": deadline,
            "is_active": bool(is_active),
            "related_tags": related_tags if has_tag else None,
            "benefits": benefits if has_benefit else None,
            "address": address if has_address else None,
        }

    def get_detailed_contents(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')

        for element in soup(["script", "style", "noscript"]):
            element.extract()

        images = [f'https:{img.get("src")}' if img.get("src").startswith("//") else img.get("src") for img in soup.find_all('img')]
        has_image = len(images) > 0

        for tag in soup.find_all('p', attrs={'hidden': True}):
            tag.decompose()
    
        hidden_style_pattern = re.compile(r'(font-size:\s*0|height:\s*0|width:\s*0|display:\s*none|visibility:\s*hidden)', re.IGNORECASE)
        hidden_tags = soup.find_all(attrs={"style": hidden_style_pattern})
        for tag in hidden_tags:
            tag.decompose()

        blind_tags = soup.find_all(class_=re.compile(r'(blind|hidden|sr-only)'))
        for tag in blind_tags:
            tag.decompose()

        clean_text = soup.get_text(separator=' ', strip=True)
        text_length = len(clean_text)

        has_keyword = any(keyword in clean_text for keyword in self.keyword)
        has_emoji = len(emoji.emoji_list(clean_text)) > 0

        content_type = "TEXT"

        if text_length < 200:
            content_type = "IMAGE" if has_image else "TEXT"
        
        if not has_keyword and has_image:
            if has_emoji:
                content_type = "TEXT"
            print(f" {self.platform} | ⚠️ 텍스트는 길지만 핵심 키워드가 없어 IMAGE 공고로 판단합니다.")
            content_type = "IMAGE"

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        markdown_text = h.handle(str(soup))

        return {
            "content_type": content_type,
            "text_length": text_length,
            "detail_contents": {
                "image": images,
                "text": markdown_text
            }
        }

    async def run(self):
        print("=== Jobkorea 크롤러 시작 ===")
        gnos = await self.fetch_job_list()
        
        if not gnos:
            print("수집된 공고 ID가 없습니다.")
            return []
        
        print(f"총 {len(gnos)}개의 공고를 수집합니다.")

        tasks = [self.fetch_job_detail(gno) for gno in gnos]
        results = await asyncio.gather(*tasks)

        results = [job for job in results if job is not None]
        
        print(f"=== Jobkorea 크롤러 종료 (성공: {len(results)}건) ===")
        return results

async def main():
    print("🚀 [테스트] 잡코리아 크롤러 실행 중...")
    async with JobkoreaCrawler() as crawler:
        start = time.time()
        results = await crawler.run()
        end = time.time()
        
        if results:
            print(f"\n✅ 총 {len(results)}개의 공고 수집 완료!")
            print("--- [첫 번째 공고 샘플 데이터] ---")
            pprint.pprint(results[0])
            print([res['position'] for res in results])
        else:
            print("\n❌ 수집된 데이터가 없습니다.")
        print("소요시간:", end - start)

if __name__ == "__main__":
    asyncio.run(main())