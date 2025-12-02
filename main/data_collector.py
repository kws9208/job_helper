import asyncio
import random
import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler
from crawler.wanted_crawler import WantedCrawler
from crawler.saramin_crawler import SaraminCrawler
from crawler.jobkorea_crawler import JobkoreaCrawler
from database.connection import get_session_factory
from repository import RepositoryFactory
from repository.nosql import NoSQLRepository


def setup_logger():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger("IntegratedCrawler")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    
    file_handler = TimedRotatingFileHandler(
        filename=f"{log_dir}/crawler.log", 
        when="midnight", 
        interval=1, 
        encoding="utf-8", 
        backupCount=30
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

logger = setup_logger()

async def run_crawler_task(platform_name, crawler_instance):
    SessionFactory = get_session_factory()
    session = SessionFactory()
    
    try:
        repository = RepositoryFactory.get_repository(platform_name, session)
    except ValueError as e:
        logger.error(f"[{platform_name}] 리포지토리 생성 실패: {e}")
        session.close()
        return
    
    nosql_repository = NoSQLRepository()

    logger.info(f"🚀 [{platform_name}] 크롤링 시작")

    total_saved = 0
    pass_page_count = 0 
    limit = 20

    try:
        async with crawler_instance as crawler:
            while True:
                current_page_info = crawler.payload.get('offset', crawler.payload.get('page', 0))
                logger.info(f"[{platform_name}] 📄 목록 조회 중... (Index: {current_page_info})")

                job_ids = await crawler.fetch_job_list()
                crawler_ids = [str(job_id) for job_id in job_ids]
                
                if not job_ids:
                    logger.info(f"[{platform_name}] ✅ 더 이상 공고가 없습니다. 종료.")
                    break

                existing_ids = repository.get_existing_ids(job_ids)
                existing_ids_set = set(str(db_id) for db_id in existing_ids)
                target_ids = [job_id for job_id in crawler_ids if job_id not in existing_ids_set]

                duplicate_count = len(existing_ids)
                target_count = len(target_ids)

                logger.info(f"[{platform_name}] 조회: {len(job_ids)}건 | 패스: {duplicate_count}건 | 신규: {target_count}건")

                if target_count == 0:
                    pass_page_count += 1
                    if pass_page_count >= 5:
                        logger.warning(f"[{platform_name}] ⛔ 연속 중복 발생으로 최신 공고 수집 완료 간주.")
                        break
                else:
                    pass_page_count = 0

                if target_ids:
                    job_details = await crawler.fetch_details_by_ids(target_ids)
                    
                    logger.info(f"[{platform_name}] 💾 DB 저장 중...")
                    for job_data in job_details:
                        repository.save_job(job_data)
                    
                    session.commit()
                    total_saved += len(job_details)
                    logger.info(f"[{platform_name}] ✅ {len(job_details)}건 저장 완료 (누적: {total_saved}건)")

                    nosql_success_count = 0
                    for job_data in job_details:
                        if nosql_repository.save_raw_job(platform_name, job_data):
                            nosql_success_count += 1
                    
                    if nosql_success_count > 0:
                        logger.info(f"[{platform_name}] ☁️ OCI NoSQL {nosql_success_count}/{len(job_details)}건 적재 완료")

                if platform_name == "WANTED":
                    crawler.payload["offset"] += limit
                else:
                    crawler.payload["page"] += 1
                
                sleep_time = random.uniform(3, 7)
                await asyncio.sleep(sleep_time)
                break

    except Exception as e:
        session.rollback()
        logger.error(f"[{platform_name}] 🔥 에러 발생: {e}", exc_info=True)
    finally:
        session.close()
        nosql_repository.close()
        logger.info(f"[{platform_name}] 🏁 종료 (총 {total_saved}건 저장)")


async def main():
    logger.info("============== [통합 크롤러 시작] ==============")
    
    await asyncio.gather(
        run_crawler_task("WANTED", WantedCrawler()),
        run_crawler_task("SARAMIN", SaraminCrawler()),
        run_crawler_task("JOBKOREA", JobkoreaCrawler())
    )
    
    logger.info("============== [모든 크롤러 종료] ==============")

if __name__ == "__main__":
    asyncio.run(main())