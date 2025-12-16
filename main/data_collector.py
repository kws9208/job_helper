import asyncio
import random
import logging
import sys
import os
from utils.logger import setup_logger
from crawler.wanted_crawler import WantedCrawler
from crawler.saramin_crawler import SaraminCrawler
from crawler.jobkorea_crawler import JobkoreaCrawler
from database.connection import get_session_factory
from repository import RepositoryFactory
from repository.nosql import NoSQLRepository
from collections import Counter


async def run_crawler_task(platform_name, crawler_instance, logger, nosql_repository, max_page_count=100):
    logger = logger.getChild(platform_name)
    SessionFactory = get_session_factory()
    session = SessionFactory()
    
    try:
        child_logger = logger.getChild("Repository")
        repository = RepositoryFactory.get_repository(platform_name, session, child_logger)
    except ValueError as e:
        logger.error(f"리포지토리 생성 실패: {e}")
        session.close()
        return

    logger.info(f"🚀 크롤링 시작")

    total_saved = 0
    pass_page_count = 0 
    limit = 20

    try:
        async with crawler_instance as crawler:
            while True:
                current_page_info = crawler.payload.get('offset', crawler.payload.get('page', 0))
                logger.info(f"📄 목록 조회 중... (Index: {current_page_info})")

                job_ids = await crawler.fetch_job_list()
                crawler_ids = [str(job_id) for job_id in job_ids]
                
                if not job_ids:
                    logger.info(f"✅ 더 이상 공고가 없습니다. 종료.")
                    break

                need_crawling_flags = [repository.need_job_crawling(job_id, expire_days=7) for job_id in job_ids]
                
                target_ids = [job_id for job_id, flag in zip(job_ids, need_crawling_flags) if flag in ("new", "renew")]
                target_count = len(target_ids)

                counter = Counter(need_crawling_flags)
                logger.info(f"조회: {len(job_ids)}건 | 신규: {counter["new"]}건 | 패스: {counter["pass"]}건 | 갱신: {counter["renew"]}")

                if target_count == 0:
                    pass_page_count += 1
                    if pass_page_count >= max_page_count:
                        logger.warning(f"⛔ {max_page_count} 페이지 이상 연속 중복 발생으로 최신 공고 수집 완료 간주.")
                        break
                else:
                    pass_page_count = 0

                if target_ids:
                    tasks = [process_single_job(platform_name, crawler, repository, target_id) for target_id in target_ids]
                    results = await asyncio.gather(*tasks)
                    job_details = [res for res in results if res is not None]

                    logger.info(f"💾 DB 저장 중...")
                    for job_data in job_details:
                        repository.save_job(job_data)
                    
                    session.commit()
                    total_saved += len(job_details)
                    logger.info(f"✅ {len(job_details)}건 저장 완료 (누적: {total_saved}건)")

                    nosql_success_count = 0
                    for job_data in job_details:
                        if nosql_repository.save_raw_job(platform_name, job_data.get("job")):
                            nosql_success_count += 1
                    
                    if nosql_success_count > 0:
                        logger.info(f"☁️ OCI NoSQL {nosql_success_count}/{len(job_details)}건 적재 완료")

                if platform_name == "WANTED":
                    crawler.payload["offset"] += limit
                else:
                    crawler.payload["page"] += 1
                
                sleep_time = random.uniform(3, 7)
                await asyncio.sleep(sleep_time)

    except Exception as e:
        session.rollback()
        logger.error(f"🔥 에러 발생: {e}", exc_info=True)
    finally:
        session.close()
        logger.info(f"🏁 종료 (총 {total_saved}건 저장)")

async def process_single_job(platform_name, crawler, repository, target_id):
    if platform_name == "JOBKOREA":
        job_summaray = await crawler.fetch_job_summary(target_id)
        if job_summaray is None:
            return
        detail_contents = await crawler.fetch_job_detail(target_id)
        company_id = job_summaray.get("company_id")
        if job_summaray["company_info"] is not None and repository.need_company_crawling(company_id, expire_days=7) in ("new", "renew"):
            if company_url := job_summaray["company_info"]["company_url"]:
                company_info = await crawler.fetch_company_info(company_url)
            else:
                company_info = dict()
            company_info = company_info | job_summaray.pop("company_info")
        else:
            del job_summaray["company_info"]
            company_info = None

        data = {
            "company": company_info,
            "job": {
                **job_summaray, 
                **detail_contents
            }
        }

    elif platform_name == "SARAMIN":
        job_summaray = await crawler.fetch_job_summary(target_id)
        if job_summaray is None:
            return
        detail_contents = await crawler.fetch_job_detail(target_id)
        csn = job_summaray.get("csn")
        if job_summaray["company_info"] is not None and  repository.need_company_crawling(csn, expire_days=7) in ("new", "renew"):
            if company_url := job_summaray["company_info"]["company_url"]:
                company_info = await crawler.fetch_company_info(company_url)
            else:
                company_info = dict()
            company_info = company_info | job_summaray.pop("company_info")
        else:
            del job_summaray["company_info"]
            company_info = None

        data = {
            "company": company_info,
            "job": {
                **job_summaray, 
                **detail_contents
            }
        }

    elif platform_name == "WANTED":
        job_detail_data = await crawler.fetch_job_detail(target_id)
        company_id = job_detail_data.get("company_id")
        if repository.need_company_crawling(company_id, expire_days=7) in ("new", "renew"):
            if company_id := job_detail_data.get('company_id'):
                company_info_data = await crawler.fetch_company_info(company_id)
        else:
            company_info_data = None

        data = {
            "company": company_info_data if company_id else None,
            "job": job_detail_data,
        }

    return data

async def main():
    logger = setup_logger("Crawler")
    logger.info("============== [통합 크롤러 시작] ==============")

    nosql_repository = NoSQLRepository(logger)
    try:
        await asyncio.gather(
            run_crawler_task("WANTED", WantedCrawler(logger=logger), logger, nosql_repository),
            run_crawler_task("SARAMIN", SaraminCrawler(logger=logger), logger, nosql_repository),
            run_crawler_task("JOBKOREA", JobkoreaCrawler(logger=logger), logger, nosql_repository)
        )
    finally:
        nosql_repository.close()
        logger.info("============== [모든 크롤러 종료] ==============")

if __name__ == "__main__":
    asyncio.run(main())