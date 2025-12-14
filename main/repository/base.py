from sqlalchemy import select

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