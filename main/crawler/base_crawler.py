from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import httpx

class BaseCrawler(ABC):
    def __init__(self, base_url, platform, logger, k=5):
        self.base_url = base_url
        self.platform = platform
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        self.header = {'User-Agent': self.user_agent}

        self.logger = logger

        self.client = None
        self.semaphore = asyncio.Semaphore(k)

    async def request(self, method, url, **kwargs):
        if self.client is None:
            raise RuntimeError("Client Session is not initialized. Use 'async with' context.")

        retries = 5
        for attempt in range(1, retries + 1):
            async with self.semaphore:
                try:
                    response = await self.client.request(method, url, **kwargs)
                    if response.status_code in [302, 404, 503]:
                        self.logger.warning(f"🚫 [Pass] 공고가 삭제되거나 검수 중입니다.\n"
                                            f"(Request URL: {url})\n"
                                            f"(Status Code: {response.status_code})\n"
                                            f"(Location: {response.headers.get('Location')})")
                        return None
                        
                    response.raise_for_status()
                    return response
                except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
                    if attempt == retries:
                        self.logger.error(f"🔥 [최종 실패] {self.platform} | URL: {url}\n"
                                          f"   ㄴ 에러: {e}\n"
                                          f"   ㄴ 요청 데이터(Payload): {kwargs}")
                        raise
                    wait_time = 2 ** attempt # 2초, 4초...
                    self.logger.warning(f"⚠️ [재시도 {attempt}/{retries}] {self.platform} | 연결 지연 발생. {wait_time}초 후 재시도... ({e})"
                                        f"   ㄴ 요청 URL: {url}")
                    await asyncio.sleep(wait_time)
                except httpx.RequestError as e:
                    self.logger.error(
                        f"[요청 에러] {e.request.url!r} - {e}\n"
                        f"   ㄴ 요청 데이터(Payload): {kwargs}"
                    )
                    raise
                except httpx.HTTPStatusError as e:
                    self.logger.error(
                        f"[상태 코드 에러] {e.response.status_code} - {e.request.url!r}\n"
                        f"   ㄴ 요청 데이터(Payload): {kwargs}"
                    )
                    raise
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            headers=self.header,
            timeout=httpx.Timeout(15.0, connect=15.0),
            follow_redirects=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    @abstractmethod
    async def fetch_job_list(self, *args, **kwargs):
        pass

    @abstractmethod
    async def fetch_job_detail(self, *args, **kwargs):
        pass

    @abstractmethod    
    async def fetch_company_info(self, *args, **kwargs):
        pass

    async def close(self, *args, **kwargs):
        if self.client and not self.client.is_closed:
            await self.client.aclose()
            self.logger.info("HTTP Client closed.")