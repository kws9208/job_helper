from sqlalchemy import select
from datetime import datetime, timedelta

class BaseRepository:
    def __init__(self, session, model_cls, pk_column, logger):
        self.session = session
        self.model = model_cls
        self.pk_column = pk_column
        self.logger = logger

    def get_by_id(self, id_value):
        stmt = select(self.model).where(self.pk_column == id_value)
        return self.session.execute(stmt).scalars().first()

    def exists_by_id(self, id_value):
        stmt = select(self.pk_column).where(self.pk_column == id_value)
        result = self.session.execute(stmt).first()
        return result is not None

    def get_existing_ids(self, id_list):
        if not id_list:
            return set()
        stmt = select(self.pk_column).where(self.pk_column.in_(id_list))
        result = self.session.execute(stmt).scalars().all()
        return set(result)

    def need_crawling(self, id_value, expire_days, model_cls, pk_column):
        stmt = select(model_cls.crawled_at).where(pk_column == id_value)
        stored_time = self.session.execute(stmt).scalars().first()

        if stored_time is None:
            return "new"

        limit_date = datetime.now() - timedelta(days=expire_days)
        if stored_time < limit_date:
            return "renew"

        return "pass"