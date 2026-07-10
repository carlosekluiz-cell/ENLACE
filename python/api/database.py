"""
ENLACE Database Configuration

SQLAlchemy async engine, session factory, and base model class.
"""

import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator

from python.api.config import settings


# Under pytest each test runs in a fresh event loop; a pooled asyncpg
# connection created in one loop cannot be awaited from another
# ("attached to a different loop"), so tests get NullPool.
_pool_kwargs = (
    {"poolclass": NullPool}
    if "pytest" in sys.modules
    else {"pool_size": 20, "max_overflow": 10}
)

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    **_pool_kwargs,
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Standalone async generator for use outside FastAPI (pipelines, scripts)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async generator dependency for FastAPI.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
