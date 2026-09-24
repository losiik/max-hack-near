from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from max_assist.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=5,
    pool_timeout=10,
    pool_recycle=300,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {
            "application_name": "ryadom-api",
            "statement_timeout": "30000",
            "idle_in_transaction_session_timeout": "60000",
            "idle_session_timeout": "600000",
        }
    },
)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
