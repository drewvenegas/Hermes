"""
Database Service

Async database connection management.
"""

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from hermes.config import get_settings
from hermes.models import Base

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    echo=settings.debug,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize database.
    
    In production, tables are managed by Alembic migrations.
    This function just validates the connection works.
    """
    try:
        async with engine.connect() as conn:
            # Just test the connection
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Database connection failed: {e}")
        raise


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
