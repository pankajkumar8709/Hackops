import ssl as _ssl
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


def _clean_asyncpg_url(url: str) -> tuple[str, dict]:
    """Strip query params that asyncpg doesn't understand and return
    (cleaned_url, connect_args)."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    needs_ssl = "sslmode" in params or "ssl" in params

    # Remove params asyncpg can't handle
    for key in ("sslmode", "ssl", "channel_binding"):
        params.pop(key, None)

    clean_query = urlencode(params, doseq=True)
    clean_url = urlunparse(parsed._replace(query=clean_query))

    connect_args = {}
    if needs_ssl:
        # Use the system trust store with full certificate verification.
        # (Previously disabled with CERT_NONE — re-enabled as a security fix.)
        ctx = _ssl.create_default_context()
        connect_args["ssl"] = ctx

    return clean_url, connect_args


_url, _connect_args = _clean_asyncpg_url(settings.database_url)

engine = create_async_engine(
    _url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
