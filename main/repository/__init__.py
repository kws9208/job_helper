from .base import BaseRepository
from .wanted import WantedRepository
from .saramin import SaraminRepository
from .jobkorea import JobkoreaRepository

class RepositoryFactory:
    @staticmethod
    def get_repository(platform_name, session, logger):
        platform = platform_name.upper()
        if platform == "WANTED":
            return WantedRepository(session, logger)
        elif platform == "SARAMIN":
            return SaraminRepository(session, logger)
        elif platform == "JOBKOREA":
            return JobkoreaRepository(session, logger)
        else:
            raise ValueError(f"지원하지 않는 플랫폼입니다: {platform_name}")