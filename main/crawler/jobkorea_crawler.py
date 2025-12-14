from .base_crawler import BaseCrawler
import time
import asyncio
import json
import pprint
import html2text
from bs4 import BeautifulSoup
import re
import emoji
from utils.logger import setup_logger

class JobkoreaCrawler(BaseCrawler):
    def __init__(self, logger, k=5):
        super().__init__(base_url="https://m.jobkorea.co.kr", platform="Jobkorea", logger=logger, k=k)
        self.job_list_url = "https://www.jobkorea.co.kr/Search/api/display/v2/jobs"
        self.job_detail_url = f"{self.base_url}/Recruit/GIReadDetailContentIframe"
        self.job_summary_info = f"{self.base_url}/Recruit/SwipeGIReadInfo"
        self.job_basic_url = f"{self.base_url}/Recruit/GI_Read"
        self.payload = {
            "page": 0,
            "pageSize": 20,
            "sortProperty": "2",
            "sortDirection": "DESC",
            "keyword": ""
        }
        
        self.logger = logger.getChild("Jobkorea")
        self.keyword = ['주요업무', '담당업무', '자격요건', '우대사항', '지원자격', '모집부문', '근무조건', '전형절차', \
                          '자격', '우대', '모집', '업무', '지원', '전형', '마감', '근무']

    async def fetch_job_list(self):
        response = await self.request("POST", self.job_list_url, headers=self.header, json=self.payload)
        gnos = [job["id"] for job in response.json().get('content')]
        return gnos
    
    async def fetch_details_by_ids(self, gnos):
        self.logger.info(f"🔍 {len(gnos)}개의 상세 페이지 수집 시작...")
        tasks = [self.fetch_job_detail(gno) for gno in gnos]
        results = await asyncio.gather(*tasks)
        return [job for job in results if job is not None]

    async def fetch_job_detail(self, gno):
        response = await self.request("GET", f'{self.job_detail_url}/{gno}', headers=self.header)
        html_content = response.text

        job_summaray = await self.fetch_job_summary(gno)
        if job_summaray is None:
            return None

        detail_contents = self.get_detailed_contents(html_content)
        if company_url := job_summaray["company_info"]["company_url"]:
            company_info = await self.fetch_company_info(company_url)
        else:
            company_info = dict()
        company_info = company_info | job_summaray.pop("company_info")

        return {
            "company": company_info,
            "job": {
                **job_summaray, 
                **detail_contents
            }
        }
    
    async def fetch_job_summary(self, gno):
        self.header.update({"X-Requested-With": "XMLHttpRequest"})
        response = await self.request("POST", f'{self.job_summary_info}/{gno}', headers=self.header)
        html_content = response.text
        
        if "채용공고가 존재하지 않습니다." in html_content or "채용공고가 삭제되어 상세 내용을 확인할 수 없습니다." in html_content:
            self.logger.warning(f"🚫 [Skip] 유효하지 않은 공고입니다. (GNO: {gno})")
            return None

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
            company_info = dict()
            if has_company.select_one('div.companyHeader'):
                company_name = has_company.select_one('div.companyHeader > div.header > h2').text.strip()
                for item in has_company.select('div.generalSummary > div.field.ellipsis'):
                    key = item.select_one('.label').text.strip()
                    value = item.select_one('.value')
                    if key == "산업":
                        company_info.update({"industry": value.text.strip()})
                    if key == "사원수":
                        company_info.update({"employees": value.contents[0].strip().replace("명","")})
                    if key == "기업구분":
                        company_info.update({"classification": value.contents[0].strip()})
                    if key == "설립일":
                        company_info.update({"foundation_date": value.contents[0].strip()})
            elif has_company.select_one('div.info-company'):
                company_name = has_company.select_one('div.info-company > p').contents[0].strip()
                for item in has_company.select('ul.info-company-list > li'):
                    key = item.select_one('dl > :nth-child(1)').text.strip()
                    value = item.select_one('dl > :nth-child(2)').text.strip()
                    if key == "직원수":
                        company_info.update({"employees": value})
                    if key == "기업구분":
                        company_info.update({"classification": value.replace("명","")})
                    if key == "산업":
                        company_info.update({"industry": value})
                    if key == "위치":
                        company_info.update({"address": value})
            company_info.update({"company_name": company_name})

            for selector in ['div.row-footer > a', 'div.header_wrap > a']:
                if company_id := has_company.select_one(selector):
                    company_id = company_id.get('href')
                    company_url = self.base_url + company_id
                    if "company" in company_id:
                        company_id = company_id.split('/')[2].split('?')[0]
                    elif "Recruit" in company_id:
                        company_id = company_id.split('?')[0].split('/')[-1]
                    else:
                        company_id = company_id.split('?')[0].split('/')[-1]
                    company_info.update({"company_id": company_id})
                    company_info.update({"company_url": company_url})
                    break

        if has_tag := soup.select_one('#rowKeyword'):
            tag_items = has_tag.select('div.keyword-list > span')
            related_tags = [item.text.strip() for item in tag_items]
        elif has_tag := soup.select_one('#rowTag'):
            tag_items = has_tag.select('ul > li')
            related_tags = [item.text.strip() for item in tag_items if item.get('class') == 'job']

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
            "gno": gno,
            "job_url": f"https://m.jobkorea.co.kr/Recruit/GI_Read/{gno}",
            "position": position,
            "deadline": deadline,
            "is_active": bool(is_active),
            "address": address if has_address else None,
            "related_tags": related_tags if has_tag else None,
            "benefits": benefits if has_benefit else None,
            "company_id": company_info.get("company_id", None),
            "company_info": company_info,
            **summary_dict
        }

    def get_detailed_contents(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')

        for element in soup(["script", "style", "noscript"]):
            element.extract()
        images = [f'https:{img.get("src")}' if img.get("src").startswith("//") else img.get("src") for img in soup.find_all('img') if img.get("src")]
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
            content_type = "image"

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
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
    
        company_info = dict()
        if any(pattern in company_url for pattern in ['company', 'Company', 'Recruit']):
            has_company_logo = soup.select_one('div.logo img')
            if has_company_logo:
                company_logo = has_company_logo.get('src')
                company_logo_url = f'https:{company_logo}' if company_logo.startswith('//') else company_logo
            company_name = soup.select_one('div.company-header-branding-body > div.name').text.strip()
            info_items = soup.select('.company-body-wrapper > div')
            for info_item in info_items:
                info_item_class_name = info_item.get('class')[-1]
                if info_item_class_name == 'company-body-container-basic-infomation':
                    for item in soup.select('div.table-basic-infomation > div.field'):
                        key = item.select_one('div.field-label').text.strip()
                        value = item.select_one('div.field-value').contents[0].strip()
                        if key == '산업':
                            company_info.update({'industry': value})
                        if key == '사원수':
                            company_info.update({'employees': value.replace("명","")})
                        if key == '기업구분':
                            company_info.update({'classification': value})
                        if key == '설립일':
                            company_info.update({'foundation_date': value})
                        if key == '주소':
                            company_info.update({'address': value})
                elif info_item_class_name == 'company-body-container-working-environment':
                    if comapny_intro := info_item.select('div.container-body > introduce-body'):
                        company_info.update({'introduction': comapny_intro.text.strip()})
        else:
            if has_company_logo := soup.select_one('.logo img'):
                company_logo = has_company_logo.get('src')
                company_logo_url = f'https:{company_logo}' if company_logo.startswith('//') else company_logo
            elif has_company_logo:= soup.select_one('.info_cont > div.sc.inf > h2'):
                if img := has_company_logo.find('img'):
                    url = img.get('src')
                else:
                    url = re.search(r'url\((.*?)\)', has_company_logo.get("style")).group(1)
                company_logo_url =  f"https:{url}" if url.startswith("//") else url.strip("'\"")
            company_name = soup.select_one('div.jkHeadInner > h1.headTit').text.strip()
            for item in soup.select('.info_cont > div.sc.inf > ul > li'):
                key = item.select_one(':nth-child(3)').text.strip()
                value = item.select_one(':nth-child(2)').text.strip()
                if any("설립" in v for v in (key, value)):
                    company_info.update({'foundation_date': key.replace("설립","").strip()})
                if "사원" in key:
                    company_info.update({'employees': value.replace("명","").strip()})
                if key == '기업형태':
                    company_info.update({'classification': value})

        return {
            "company_url": company_url,
            "company_logo_url": company_logo_url if has_company_logo else None,
            "company_name": company_name,
            **company_info
        }

    async def run(self):
        self.logger.info("=== Jobkorea 크롤러 시작 ===")
        gnos = await self.fetch_job_list()
        
        if not gnos:
            self.logger.info("수집된 공고 ID가 없습니다.")
            return []
        
        self.logger.info(f"총 {len(gnos)}개의 공고를 수집합니다.")

        tasks = [self.fetch_job_detail(gno) for gno in gnos]
        results = await asyncio.gather(*tasks)

        results = [job for job in results if job is not None]
        
        self.logger.info(f"=== Jobkorea 크롤러 종료 (성공: {len(results)}건) ===")
        return results

async def main():
    logger = setup_logger("Crawler")
    logger.info("🚀 [테스트] 잡코리아 크롤러 실행 중...")
    async with JobkoreaCrawler(logger=logger) as crawler:
        while crawler.payload['page'] < 1:
            start = time.time()
            results = await crawler.run()
            end = time.time()
            
            if results:
                logger.info(f"\n✅ 총 {len(results)}개의 공고 수집 완료!")
                logger.info("--- [첫 번째 공고 샘플 데이터] ---")
                pprint.pprint(results[0])
            else:
                logger.info("\n❌ 수집된 데이터가 없습니다.")
            logger.info(f"Page: {crawler.payload['page']}, 소요시간: {end - start}")
            crawler.payload['page'] += 1

if __name__ == "__main__":
    asyncio.run(main())