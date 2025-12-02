import requests
from bs4 import BeautifulSoup
import json
import asyncio
from playwright.async_api import async_playwright
import time
from functools import wraps

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

def crawl_job_header(soup, job_id):
    company_name = soup.select_one(f'#content > div.wrap_jview > section.jview.jview-0-{job_id} > div.wrap_jv_cont > div.wrap_jv_header > div.jv_header > div.title_inner > a.company').text.strip()
    job_title = soup.select_one('div.wrap_jv_header > div.jv_header > h1').text.strip()
    return {'회사명': company_name, '포지션명': job_title}

def crawl_job_summary(soup, job_id):
    job_summary = soup.select('div.wrap_jview > section:nth-of-type(1) > div.wrap_jv_cont > div.jv_cont.jv_summary')
    job_sum_dict = dict()
    for job_col in job_summary:
        for dl in job_col.find_all('dl'):
            key = dl.find('dt')
            value = dl.find('dd')
            if value.select_one('div.toolTipWrap') or value.select_one('div.toolTipWrap salary_wrap empty'):
                if key.text in ["우대사항", "자격요건"]:
                    if key.text == "우대사항":
                        prefix = 'preferred'
                    elif key.text == "자격요건":
                        prefix = 'required'
                    freeform_div = soup.select_one(f'#details-{prefix}-{job_id} > div.toolTipTxt.freeform')
                    if freeform_div:
                        value = freeform_div.get_text(separator='\n').strip()
                    else:
                        items = soup.select(f'#details-{prefix}-{job_id} > ul > li')
                        value = dict()
                        for item in items:
                            k = item.find('span').text.strip()
                            v = item.find('span').next_sibling.strip()
                            value.update({k:v})
                elif key.text == "근무형태":
                    jobtype_items = soup.select(f'#details-jobtype-{job_id} > ul > li')
                    value = dl.find('strong').text.strip().split(',')
                    for i, jt_item in enumerate(jobtype_items):
                        k = jt_item.find('span').text.strip()
                        v = jt_item.find('span').next_sibling.strip()
                        if k in value:
                            value[i] += f"({v})"
                    value = ",".join(value)
                elif key.text == "급여":
                    value = value.contents[0].strip()
            else:
                value = dl.find('dd').text.replace("지도","").strip()
            job_sum_dict.update({key.text.strip(): value})
    return job_sum_dict

@async_timer
async def crawl_job_page(context, url, job_id, base_url, semaphore):
    async with semaphore:
        page=None
        try:
            page = await context.new_page()
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state('domcontentloaded', timeout=10000)

            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')

            is_available_job = soup.select('div.page_notification')
            if is_available_job:
                return is_available_job.text.strip()

            return {
                    "job_url": url,
                    "job_header": crawl_job_header(soup, job_id),
                    "job_summary": crawl_job_summary(soup, job_id),
                    "job_detail": await crawl_job_detail(soup, base_url, context),
                    "job_benefit": crawl_job_benefit(soup),
                    "job_location": crawl_job_location(soup),
                    "job_apply_method": crawl_job_apply_method(soup),
                    "company_info": crawl_job_company_info(soup, job_id, base_url)
                }
        except Exception as e:
            print(f"Failed to crawl {url}: {e}")
            return
        finally:
            if page:
                await page.close()

async def crawl_job_detail(soup, base_url, context):
    detail_url = base_url + soup.select_one('#iframe_content_0').get('src')
    print(detail_url)
    try:
        page = await context.new_page()
        await page.goto(detail_url, timeout=60000)
        html_content = await page.content()
        
        inner_soup = BeautifulSoup(html_content, 'html.parser')
        main_contents = inner_soup.select_one('div.user_content')
        has_image = main_contents.select('div img')
        
        texts, images = None, None
        if main_contents.text:
            texts = main_contents.text.strip()
        if has_image:
            images = [contents.get('src') for contents in has_image]

        return {"텍스트": texts, "이미지": images}
    except requests.exceptions.RequestException as e:
        print(f"Failed to crawl {detail_url}: {e}")
        return

def crawl_job_benefit(soup):
    has_benefit = soup.select_one(f'div.jv_cont.jv_benefit')
    if has_benefit:
        freeform_div = has_benefit.select_one(f'div.jv_cont.jv_benefit > div > div')
        freeform_class_name = freeform_div.get('class', [])

        if freeform_class_name[-1] == 'freeform':
            return freeform_div.text.strip()
        elif freeform_class_name[-1] == 'details':
            items = freeform_div.find('div')
            benefits = dict()
            for item in items:
                key = item.find('dt').text.strip()
                value = item.find('dd').get('data-origin', None)
                benefits.update({key: value})
            return benefits
    else:
        return None

def crawl_job_location(soup):
    has_job_location = soup.select_one('div.jv_cont.jv_location')
    if has_job_location:
        has_subway = has_job_location.select_one(f'div > div.cont.box > address > span.spr_jview.txt_subway')
        address = has_job_location.select_one(f'div > div.cont.box > address > span.spr_jview.txt_adr').text.strip()
        if has_subway:
            subway = has_subway.text.strip()
            return {"회사 주소": address, "오시는 길": subway}
        else:
            return {"회사 주소": address}
    else:
        return None

def crawl_job_apply_method(soup):
    period = soup.select(f'div.jv_cont.jv_howto > div.cont.box > div.status > dl.info_period > dd')
    start_date = period[0].text.strip()
    deadline = period[-1].text.strip()
    apply_method = soup.select_one(f'div.jv_cont.jv_howto > div.cont.box > dl.guide > dd.method').text.strip()
    apply_template = soup.select_one(f'div.jv_cont.jv_howto > div.cont.box > dl.guide > dd.template')
    if apply_template:
        if apply_template.select_one('div.toolTipWrap'):
            key = apply_template.find('strong').text.strip()
            value = apply_template.find('p').text.strip()
            apply_template = {key: value}
        else:
            apply_template = apply_template.text.strip()
    return {"시작일": start_date, "마감일": deadline, "지원방법": apply_method, "지원형식": apply_template}

def crawl_job_company_info(soup, job_id, base_url):
    has_company_info = soup.select_one(f'section.jview.jview-0-{job_id} > div.wrap_jv_cont > div.jv_cont.jv_company.company_info_wrap_{job_id}')
    if has_company_info:
        company_title = soup.select_one(f'div.jv_cont.jv_company.company_info_wrap_{job_id} > div.cont.box > div.wrap_info > div.tit_area > div.basic_info > h3 > a')
        company_url = base_url + company_title.get('href')
        company_title = company_title.text.strip()
        
        company_info = soup.select(f'div.jv_cont.jv_company.company_info_wrap_{job_id} > div.cont.box > div.wrap_info > div.info_area > dl')
        com_info = dict()
        for info in company_info:
            key = info.find('dt').text.strip()
            value = info.find('dd').get('title').strip()
            com_info.update({key:value})
        return {"회사명": company_title, "회사URL": company_url, "회사정보": com_info}
    else:
        return None
    
@async_timer
async def main(url, k):
    try:
        response = requests.get(url, headers={'User-Agent': USER_AGENT})
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return
    
    job_items = BeautifulSoup(response.text, 'html.parser').select('div[id^="rec-"]')
    if not job_items:
        print("채용 공고를 찾을 수 없습니다. 페이지 구조가 변경되었을 수 있습니다.")
        return
    print(f"총 {len(job_items)}개의 공고를 찾았습니다.")
    
    base_url = "https://www.saramin.co.kr"
    job_ids = [item.get('id')[4:] for item in job_items]
    job_url_list = [base_url+item.select_one(f'#rec_link_{item.get('id')[4:]}').get('href') for item in job_items]

    output_filename = "./saramin_jobs.jsonl"

    all_job_data = []
    semaphore = asyncio.Semaphore(k)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        
        tasks = []
        for job_id, job_url in zip(job_ids, job_url_list):
            tasks.append(crawl_job_page(context, job_url, job_id, base_url, semaphore))

        results = await asyncio.gather(*tasks)

        await browser.close()

        all_job_data = [job for job in results if job is not None]

        with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(all_job_data, f, ensure_ascii=False, indent=4)

        print(f"Save complete - {len(all_job_data)}.")

# --- 스크립트 실행 ---
if __name__ == "__main__":
    BASE_URL = "https://www.saramin.co.kr/zf_user/jobs/list/domestic?loc_mcd=101000"
    asyncio.run(main(BASE_URL, k=3))
    