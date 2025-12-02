import requests
from bs4 import BeautifulSoup
import json
import asyncio
from playwright.async_api import async_playwright
import time
from functools import wraps
import re

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def async_timer(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"{func.__name__} took {elapsed:.2f} seconds")
        return result
    return wrapper

def crawl_job_header(soup):
    job_header = soup.find('div', attrs={'data-sentry-component':'Title'}) 
    company_name = job_header.select_one('div > div > div > div:nth-child(1)').text.strip()
    job_title = job_header.select_one('div > div > div > div:nth-child(2)').text.strip()
    return {'회사명': company_name, '포지션명': job_title}

def crawl_job_summary(soup):
    job_summary = soup.find_all('div', attrs={'data-sentry-component':'JobInfoItem'})    
    job_sum_dict = dict()
    for job_sm in job_summary:
        key = job_sm.select_one('div > div:nth-child(1) > span').text.strip()
        value = job_sm.select_one('div > div:nth-child(2) > span').text.strip()
        job_sum_dict.update({key:value})
    return job_sum_dict

@async_timer
async def crawl_job_page(context, job_url, base_url, semaphore):
    async with semaphore:
        page=None
        try:
            page = await context.new_page()
            await page.goto(job_url, timeout=60000)
            await page.wait_for_load_state('domcontentloaded', timeout=60000)
            await page.wait_for_selector('[data-sentry-component="JobInfoItem"]', state='attached', timeout=60000)

            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')

            return {
                    "job_url": job_url,
                    "job_header": crawl_job_header(soup),
                    "job_summary": crawl_job_summary(soup),
                    "job_detail": await crawl_job_detail(soup, base_url, context),
                    "job_overview": crawl_job_overview(soup),
                    "job_qualifications": crawl_job_qualifications(soup),
                    "job_apply_method": crawl_job_apply_method(soup),
                    "company_info": crawl_job_company_info(soup),
                    "job_benefit": await crawl_job_benefit(soup, page),
                    "job_tag": crawl_job_tag(soup)                    
                }
        except Exception as e:
            print(f"Failed to crawl {job_url}: {e}")
            return None
        finally:
            if page:
                await page.close()

async def crawl_job_detail(soup, base_url, context):
    detail_url = base_url + soup.select_one('#parent-frame > iframe').get('src')
    print(detail_url)
    try:
        page = await context.new_page()
        await page.goto(detail_url, timeout=60000)
        await page.wait_for_load_state('domcontentloaded', timeout=60000)
        await page.wait_for_selector('.view-content.view-detail.dev-wrap-detailContents', state='attached', timeout=60000)

        html_content = await page.content()
        
        inner_soup = BeautifulSoup(html_content, 'html.parser')
        main_contents = inner_soup.select_one('#detail-content > article')

        has_image = main_contents.select('article img')
        images_urls = [contents.get('src') for contents in has_image]

        texts, images = None, None
        if main_contents.text:
            texts = main_contents.text.strip()
        if has_image:
            images = ['https:'+image_url if image_url.startswith('//') else image_url for image_url in images_urls]

        return {"텍스트": texts, "이미지": images}
    except requests.exceptions.RequestException as e:
        print(f"Failed to crawl {detail_url}: {e}")
        return
   
def crawl_job_overview(soup):
    overview = soup.select_one('body > main > div:nth-child(6) > div:nth-child(2) > div') 
    job_field = overview.select_one('div > div > div > div > div:nth-of-type(2) > span').text.strip()
    overview_dict = dict(모집분야=job_field)
    overview_items = soup.find_all('div', attrs={'data-sentry-component':'RecruitmentItem'})
    for item in overview_items:
        key = item.select_one('div > span:nth-child(1)')
        value = key.find_next_sibling()
        key = key.text.strip()
        has_child = value.find_all(recursive=False)
        if len(has_child) > 1:
            value = [v.text.strip() for v in value]
        else:
            value = value.text
            if key == "근무지주소":
                value = value.replace("지도보기","").strip()
        overview_dict.update({key:value})
    return overview_dict

def crawl_job_qualifications(soup):
    REMOVAL_PATTERN = re.compile(
        r'^(기본우대|우대전공|외국어|자격증)\s*[:]?\s*'
    )
    qualification_dict = dict()
    qualification_items = soup.find_all('div', attrs={'data-sentry-component':'QualificationItem'})
    for item in qualification_items:
        key = item.select_one('div > span')
        value = key.find_next_sibling()
        key = key.text.strip()
        has_child = value.find_all(recursive=False)
        if len(has_child) > 1:
            value = [REMOVAL_PATTERN.sub('', v.text.strip()).strip() for v in value]
        else:
            value = REMOVAL_PATTERN.sub('', value.text.strip()).strip()
        qualification_dict.update({key:value})
    return qualification_dict

def crawl_job_apply_method(soup):
    period = soup.select_one('#application-section > div:first-of-type > div > div:nth-child(1)')
    start_date = period.select_one('div > div:nth-child(1) > div:nth-child(2) > span')
    deadline = period.select_one('div > div:nth-child(2) > div:nth-child(2) > span')
    
    apply = soup.select_one('#application-section > div:first-of-type > div > div:nth-of-type(3) > div')
    apply_method = apply.select_one('div > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2)')
    apply_template = apply.select_one('div > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(2)')
    job_hrm = apply.select_one('div > div:nth-of-type(2) > div > div:nth-child(2) div')

    return {"시작일": start_date.text.strip() if start_date else None, 
            "마감일": deadline.text.strip() if deadline else None, 
            "지원방법": apply_method.text.strip() if apply_method else None, 
            "지원양식": apply_template.text.strip() if apply_template else None, 
            "인사담당자": job_hrm.text.strip() if job_hrm else None}

def crawl_job_company_info(soup):
    company_info = soup.find('div', attrs={'data-sentry-component':'CorpInformation'}).select('div > div:nth-child(2) > div')
    com_info = dict()
    for info in company_info:
        key = info.select_one('div > div > div:nth-child(2)').text.strip()
        value = info.select_one('div > div > div:nth-child(3)').text.strip()
        com_info.update({key:value})
    return com_info

async def crawl_job_benefit(soup, page):
    try:
        await page.locator("button:has-text('복리후생 더보기')").click(timeout=15000)
        html_content = await page.content()
        inner_soup = BeautifulSoup(html_content, 'html.parser')
    except Exception as e:
        inner_soup = soup
        
    has_benefit = inner_soup.find('div', attrs={'data-sentry-component':'BenefitCard'})
    if has_benefit:
        benefit_dict = dict()
        benefits_items = has_benefit.select('div > div > div')
        for item in benefits_items:
            if item.text:
                key = item.select_one('div > div:nth-child(2) > span')
                value = key.next_sibling   
                benefit_dict.update({key.text.strip():value.text.strip()})
        return benefit_dict
    else:
        return None

def crawl_job_tag(soup):
    tag = soup.find('div', attrs={'data-sentry-component':'RelatedTags'}).select_one('div > div:first-of-type')
    tag_items = tag.select('div > div > a')
    return [tag.text.strip() for tag in tag_items]

@async_timer
async def main(url, k):
    try:
        response = requests.get(url, headers={'User-Agent': USER_AGENT})
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return
    
    job_items = BeautifulSoup(response.text, 'html.parser').find_all('div', attrs={'data-sentry-component':'CardJob'})
    if not job_items:
        print("채용 공고를 찾을 수 없습니다. 페이지 구조가 변경되었을 수 있습니다.")
        return
    print(f"총 {len(job_items)}개의 공고를 찾았습니다.")
    
    job_url_list = [item.select_one('div > div > div > div.styles_mb_space2__dk46ts4t > a').get('href') for item in job_items]

    output_filename = "./jobkorea_jobs.jsonl"
    base_url = "https://www.jobkorea.co.kr"
    all_job_data = []
    semaphore = asyncio.Semaphore(k)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        
        tasks = []
        for job_url in job_url_list:
            tasks.append(crawl_job_page(context, job_url, base_url, semaphore))

        results = await asyncio.gather(*tasks)

        await browser.close()

        all_job_data = [job for job in results if job is not None]

        with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(all_job_data, f, ensure_ascii=False, indent=4)

        print(f"Save complete - {len(all_job_data)}.")
    

if __name__ == "__main__":
    BASE_URL = "https://www.jobkorea.co.kr/Search/?stext="
    asyncio.run(main(BASE_URL, k=3))
    