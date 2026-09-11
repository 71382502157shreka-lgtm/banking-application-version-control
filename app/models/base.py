from app import db


class BaseModel(db.Model):
    __abstract__ = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
