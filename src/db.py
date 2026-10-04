"""DBエンジン・セッションの生成。"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from settings import database_url


def get_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)


def get_sessionmaker() -> sessionmaker:
    return sessionmaker(bind=get_engine())
