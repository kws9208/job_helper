from .base_crawler import BaseCrawler
import time
import asyncio
import json
import pprint
from bs4 import BeautifulSoup
import html2text
import re
import emoji
from utils.logger import setup_logger

class SaraminCrawler(BaseCrawler):
    def __init__(self, logger, k=5):
        super().__init__(base_url="https://www.saramin.co.kr", platform="Saramin", logger=logger, k=k)
        self.job_list_url = self.base_url + "/zf_user/jobs/list/job-category"
        self.job_detail_url = "https://www.saramin.co.kr/zf_user/jobs/relay/view-detail" # "https://m.saramin.co.kr/job-search/view-frame" # 모바일 데이터 로딩 X
        self.job_summary_url = "https://m.saramin.co.kr/job-search/view-card" # https://www.saramin.co.kr/zf_user/jobs/relay/view-ajax POST rec_idx 52323189
        self.payload = {
            "page":1,
            "page_count": 20,
            "searchType": "search",
            "cat_mcls": ",".join([str(i) for i in range(2,23)]),
            "sort": "reg_dt",
        }

        self.logger = logger.getChild("Saramin")
        self.keyword = ['주요업무', '담당업무', '자격요건', '우대사항', '지원자격', '모집부문', '근무조건', '전형절차', \
                          '자격', '우대', '모집', '업무', '지원', '전형', '마감', '근무']
        
    async def fetch_job_list(self):
        url = "https://m.saramin.co.kr/search/get-recruit-list"
        response = await self.request("GET", url, headers=self.header, params=self.payload)
        json_data = response.json()
        return_data = json_data["innerHTML"]

        soup = BeautifulSoup(return_data, "html.parser")
        recruit_items = soup.select('.recruit_container')
        rec_indices = [item.get('data-rec_idx') for item in recruit_items]

        return rec_indices

    async def fetch_details_by_ids(self, job_ids):
        tasks = [self.fetch_job_detail(job_id) for job_id in job_ids]
        results = await asyncio.gather(*tasks)
        return [job for job in results if job is not None]

    async def fetch_job_detail(self, rec_idx):
        response = await self.request("POST", self.job_detail_url, headers=self.header, data={"rec_idx": rec_idx})
        if response is None:
            return None
        html_content = response.text

        job_summaray = await self.fetch_job_summary(rec_idx)
        
        detail_contents = self.get_detailed_contents(html_content)

        company_info = dict()
        if job_summaray["company_info"]:
            if company_url := job_summaray["company_info"]["company_url"]:
                company_info = await self.fetch_company_info(company_url)
            company_info = company_info | job_summaray.pop("company_info")
        else:
            del job_summaray["company_info"]

        return {
            "company": company_info,
            "job": {
                **job_summaray, 
                **detail_contents
            }
        }
    
    async def fetch_job_summary(self, rec_idx):
        self.header.update({"Referer": f"https://m.saramin.co.kr/job-search/view?rec_idx={rec_idx}"})
        response = await self.request("POST", self.job_summary_url, headers=self.header, data={"rec_idx": rec_idx})

        json_data = response.json()
        return_data = json_data["returnData"]
        
        soup = BeautifulSoup(return_data, "html.parser")

        pretty_html = soup.prettify()

        is_active = not soup.select('div.page_notification.closed_job')
        
        company_tag = soup.select_one('.corp_name')
        company_name = company_tag.text.strip()
        csn = soup.select_one('button#favorCompanyBtn').get('csn')

        position = soup.select_one('h1.subject').text.strip()

        basic_info = soup.select_one('dl.list_summary')
        employment_type = " ".join(basic_info.select_one('dd.type').stripped_strings).strip()
        career = " ".join(basic_info.select_one('dd.experience').stripped_strings).strip()
        education = " ".join(basic_info.select_one('dd.education').stripped_strings).strip()
        deadline = soup.select_one('dl.recruit_end_date > dt.tag.end + dd').contents[0].strip()

        has_benefits = soup.find("h2", string=lambda text: text and "복리후생" in text)
        if has_benefits:
            benefit_tags = has_benefits.find_next_sibling()
            benefit_classname = benefit_tags.get('class')[-1]
            if benefit_classname == 'freeform':
                benefits = benefit_tags.text.strip().split("\n")
            else:
                benefit_list = benefit_tags.select('div > dl')
                benefits = []
                for benefit in benefit_list:
                    title = benefit.select_one('dt.tit').text.strip()
                    description = benefit.select_one('dd.desc').text.strip()
                    benefits.append(f"{title}: {description}")

        has_address = soup.find("h2", string=lambda text: text and "근무지위치" in text)
        if has_address:
            address_tags = has_address.find_next_sibling()
            address_classname = address_tags.get('class')[-1]
            if address_classname == 'bonus_location':
                address = address_tags.select_one('dd.desc').text.strip()
            elif address_classname == 'wrap_map_corp':
                address = address_tags.select_one('address.txt_address').text.strip()

        has_company_info = soup.find("h2", string=lambda text: text and "기업정보" in text)
        if has_company_info:
            company_info_list = has_company_info.find_next_sibling().select('div.detail_corp > dl')
            company_info = dict()
            for corp_info in company_info_list:
                key = corp_info.select_one('dt').text.strip()
                value = corp_info.select_one('dd').contents[0].strip()
                if key == "기업형태":
                    company_info.update({"classification": value})
                if key == "사원수":
                    company_info.update({"employees": value.replace("명","")})
                if key == "설립일":
                    company_info.update({"foundation_date": value})
                if key == "주소":
                    company_info.update({"address": value})
            company_info.update({
                "csn": csn,
                "company_name": company_name,
                "company_url": f"https://m.saramin.co.kr/job-search/company-info-view?csn={csn}"
            })

        has_related_tags = soup.find('section', attrs={'data-layer':'relatetags'})
        if has_related_tags:
            relation_tag_list = has_related_tags.select('ul.list_relation_tag > li')
            related_tags = [tag.text.strip() for tag in relation_tag_list if 'location' not in tag.select_one('a').get('class', [])]
        
        return {
            "rec_idx": rec_idx,
            "job_url": f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={rec_idx}",
            "position": position,
            "is_active": bool(is_active),
            "deadline": deadline,
            "csn": company_info.get("csn") if has_company_info else None,
            "company_info": company_info if has_company_info else None,
            "employment_type": employment_type,
            "career": career,
            "education": education,
            "benefits": benefits if has_benefits else None,
            "related_tags": related_tags if has_related_tags else None,
            "address": address.split('\n')[0] if has_address else None,
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

        content_type = "text"

        if text_length < 200:
            content_type = "image" if has_image else "text"
        
        if not has_keyword and has_image:
            if has_emoji:
                content_type = "text"
            self.logger.info(f"⚠️  텍스트는 길지만 핵심 키워드가 없어 IMAGE 공고로 판단합니다.")
            content_type = "IMAGE"

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        markdown_text = h.handle(str(soup))

        return {
            "content_type": content_type,
            "full_text": markdown_text,
            "images": images
        }

    async def fetch_company_info(self, company_url):
        response = await self.request('GET', company_url)
        if response is None:
            return None
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')

        if has_company_logo := soup.select_one('div.common_company_info > div.company_logo > img'):
            company_logo_url = has_company_logo.get('src')
        if has_company_name := soup.select_one('div.common_company_info > .company_name'):
            company_name = has_company_name.text.strip()
        if has_industry := soup.select_one('div.common_company_info > .industry'):
            industry = has_industry.text.strip()

        company_info = dict()
        for item in soup.select('div.tab_company_summary > ul > li'):
            key = item.select_one('div.summary_label').text.strip()
            value = item.select_one('div.summary_value')
            if key == '기업형태':
                company_info.update({'classification': value.select_one('.box_align').contents[0].strip()})
            if key == '사원수':
                company_info.update({'employees': value.select_one('.box_align').contents[0].replace("명","").strip()})
            if key == '설립일':
                company_info.update({'foundation_date': value.select_one('.txt_desc').text.replace("설립","").strip()})
            if key == '주소':
                company_info.update({'address': value.select_one('.addr').text.strip()})

        if has_intro := soup.select_one('div.introduce_txt_box'):
            introduction = has_intro.text.strip()
        
        return {
            "company_url": company_url,
            "company_logo_url": company_logo_url if has_company_logo else None,
            "company_name": company_name,
            "industry": industry if has_industry else None,
            "introduction": introduction if has_intro else None,
            **company_info
        }



    async def run(self):
        self.logger.info("=== Saramin 크롤러 시작 ===")
        recruit_indices = await self.fetch_job_list()
        
        if not recruit_indices:
            self.logger.info("수집된 공고 ID가 없습니다.")
            return []
        
        self.logger.info(f"총 {len(recruit_indices)}개의 공고를 수집합니다.")

        tasks = [self.fetch_job_detail(rec_idx) for rec_idx in recruit_indices]
        results = await asyncio.gather(*tasks)

        results = [job for job in results if job is not None]
        
        self.logger.info(f"=== Saramin 크롤러 종료 (성공: {len(results)}건) ===")
        return results

async def main():
    logger = setup_logger("Crawler")
    logger.info("🚀 [테스트] 사람인 크롤러 실행 중...")
    async with SaraminCrawler(logger=logger) as crawler:
        while crawler.payload['page'] < 2:
            start = time.time()
            results = await crawler.run()
            end = time.time()
            
            if results:
                logger.info(f"\n✅ 총 {len(results)}개의 공고 수집 완료!")
                logger.info("--- [첫 번째 공고 샘플 데이터] ---")
                pprint.pprint(results)
            else:
                logger.info("\n❌ 수집된 데이터가 없습니다.")
            logger.info(f"Page: {crawler.payload['page']}, 소요시간: {end - start}")
            crawler.payload['page'] += 1

if __name__ == "__main__":
    asyncio.run(main())