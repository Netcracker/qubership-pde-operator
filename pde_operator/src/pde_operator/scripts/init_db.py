"""Database initialization: create tables and seed default data."""

from __future__ import annotations

import asyncio
import logging
import time

from pde_operator.config import Settings
from pde_operator.db.models.base import Base
from pde_operator.db.models.profile import Profile
from pde_operator.db.models.run import Run  # noqa: F401
from pde_operator.db.models.run_template import RunTemplate  # noqa: F401
from pde_operator.utils.db_utils import DBUtils

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_ID = "default"
_DEFAULT_RETRY_SECONDS = 300.0
_DEFAULT_RETRY_INTERVAL_SECONDS = 5.0


async def init_db(
        settings: Settings | None = None,
        *,
        retry_seconds: float = _DEFAULT_RETRY_SECONDS,
        retry_interval_seconds: float = _DEFAULT_RETRY_INTERVAL_SECONDS,
) -> None:
    settings = settings or Settings()
    deadline = time.time() + retry_seconds
    while True:
        engine = DBUtils.create_engine(settings)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            session_factory = DBUtils.create_session_factory(engine)
            async with session_factory() as session:
                # Absence of the default profile - need to init seed data
                if await session.get(Profile, DEFAULT_PROFILE_ID) is None:
                    session.add(
                        Profile(
                            id=DEFAULT_PROFILE_ID,
                            pde_image=settings.pde_default_image,
                            env_vars={
                                "PIPELINES_DECLARATIVE_EXECUTOR_FAIL_ON_MISSING_SOPS": "false",
                                "PIPELINES_DECLARATIVE_EXECUTOR_ENCRYPT_OUTPUT_SECURE_PARAMS": "false",
                            },
                            resources=settings.k8s_job_resources.model_dump(exclude_none=True),
                        )
                    )
                await session.commit()
            logger.info("Database schema ready")
            return
        except Exception as exc:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise
            logger.warning(
                "Database init failed (%s); retrying in %.1fs (%.0fs left)",
                exc,
                retry_interval_seconds,
                remaining,
            )
            await asyncio.sleep(min(retry_interval_seconds, remaining))
        finally:
            await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    asyncio.run(init_db())
