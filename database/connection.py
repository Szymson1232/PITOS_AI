
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL


def normalize_url(url):
    if url.startswith("postgres://"):
        return url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1
        )

    if url.startswith("postgresql://"):
        return url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1
        )

    return url


engine = create_async_engine(
    normalize_url(DATABASE_URL),
    pool_pre_ping=True
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def init_db():
    from database.models import SportEvent, ScanRun

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
