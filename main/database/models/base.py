from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def __repr__(self):
        cols = ', '.join([f'{c.name}={getattr(self, c.name)}' for c in self.__table__.columns])
        return f"<{self.__class__.__name__}({cols})>"