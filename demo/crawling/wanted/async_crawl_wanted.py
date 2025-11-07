import json
from bs4 import BeautifulSoup
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

def crawl_job_image(soup):
    image_elements = soup.select('div.JobDetail_contentWrapper__G_lzy > header img')
    image_urls = [img.get('src') for img in image_elements if img.get('src')]
    return image_urls

def crawl_job_header(soup):
    header_contents = soup.select_one('div.JobDetail_contentWrapper__G_lzy > div > section > header > div > div:nth-child(1)').text.strip().split('∙')
    position_name = soup.select_one('div.JobDetail_contentWrapper__G_lzy > div > section > header > h1').text.strip()
    return {"회사명": header_contents[0],
            "회사위치": header_contents[1] if len(header_contents) > 1 else None,
            "모집경력": header_contents[2] if len(header_contents) > 2 else None,
            "근무형태": header_contents[3] if len(header_contents) > 3 else "정규직",
            "포지션": position_name}

def crawl_job_intro(soup):
    company_intro = soup.select_one("div.JobDescription_JobDescription__paragraph__wrapper__WPrKC > span > span").text.strip()
    return {"회사소개": company_intro}

def crawl_job_description(soup):
    description_sections = soup.select("div.JobDescription_JobDescription__paragraph__87w8I")
    detail_dict = dict()
    for section in description_sections:
        title_tag = section.select_one("h3")
        content_tag = section.select_one("span > span")

        if title_tag and content_tag:
            title_text = title_tag.text.strip()
            content_text = content_tag.text.strip()

            if title_text:
                detail_dict.update({title_text:content_text})
    return detail_dict

def crawl_job_skill_tag(soup):
    skill_tag_elements = soup.select("li.SkillTagItem_SkillTagItem__MAo9X span")
    return {"기술 스택 • 툴": [skill_tag.text.strip() for skill_tag in skill_tag_elements]}

def crawl_job_tag(soup):
    tag_elements = soup.select("li.CompanyTags_CompanyTagItem__zYRM2 span > span")
    return {"태그": [tag.text.strip() for tag in tag_elements]}

def crawl_job_deadline(soup):
    deadline = soup.select_one("article.JobDueTime_JobDueTime__yvhtg span").text.strip()
    return {"마감일": deadline}

def crawl_job_address(soup):
    address = soup.select_one('article.JobWorkPlace_JobWorkPlace__xPlGe > div > div > span').text.strip()
    return {"근무지역": address}

@async_timer
async def crawl_job_page(context, job_url, semaphore):
    async with semaphore:
        page = None
        try:
            page = await context.new_page()
            await page.goto(job_url, timeout=60000)
            await page.wait_for_load_state('domcontentloaded', timeout=60000)

            try:
                await page.locator("button:has-text('상세 정보 더 보기')").click(timeout=3000)
            except Exception as e:
                pass 

            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            print(job_url)

            return {'job_id': job_url.split('/')[-1], 
                    'job_url': job_url, 
                    'job_images': crawl_job_image(soup),
                    'job_header': crawl_job_header(soup),
                    'job_intro': crawl_job_intro(soup),
                    'job_description': crawl_job_description(soup),
                    'job_skill_tag': crawl_job_skill_tag(soup),
                    'job_tag': crawl_job_tag(soup),
                    'job_deadline': crawl_job_deadline(soup),
                    'job_address': crawl_job_address(soup)
                }
        except Exception as e:
            print(f"Failed to crawl {job_url}: {e}")
            return None
        finally:
            if page:
                await page.close()

@async_timer
async def main(url):
    output_filename = "./wanted_jobs.jsonl"

    all_job_data = []
    semaphore = asyncio.Semaphore(5)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)

        page = await context.new_page()
        await page.goto(url, timeout=10000)

        job_list_selector = "ul[data-cy='job-list'] li.Card_Card__aaatv a[href^='/wd/']"
        await page.wait_for_selector(job_list_selector, timeout=10000)

        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        urls = soup.select(job_list_selector)

        job_urls = ['https://www.wanted.co.kr' + url.get('href') for url in urls]
        print(f"Found {len(job_urls)} job urls.")
        await page.close()

        tasks = []
        for url in job_urls:
            tasks.append(crawl_job_page(context, url, semaphore))

        print(f"Starting crawling {len(tasks)} jobs concurrently...")
        results = await asyncio.gather(*tasks)
        
        await browser.close()

        all_job_data = [job for job in results if job is not None]
        
        print(f"\nScraping complete. Saving all {len(all_job_data)} jobs to {output_filename}...")
        
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(all_job_data, f, ensure_ascii=False, indent=4)
            
        print("Save complete.")

if __name__ == "__main__":
    BASE_URL = "https://www.wanted.co.kr/wdlist?country=kr&job_sort=job.popularity_order&years=-1&locations=all"
    asyncio.run(main(BASE_URL))