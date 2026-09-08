import asyncio
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from pde_operator.api.health import router as health_router
from pde_operator.api.metrics import router as metrics_router
from pde_operator.api.router import api_router
from pde_operator.config import Settings
from pde_operator.mcp.embedded import mount_embedded_mcp
from pde_operator.services.job_reconciler import JobReconciler
from pde_operator.services.queue_service import QueueService
from pde_operator.services.retention_service import RetentionService
from pde_operator.ui import mount_ui
from pde_operator.utils.auth_utils import AuthUtils
from pde_operator.utils.input_crypto_utils import InputCryptoUtils
from pde_operator.utils.db_utils import DBUtils
from pde_operator.utils.logging_utils import LoggingUtils


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        mcp_session_manager = getattr(app.state, "mcp_session_manager", None)
        if mcp_session_manager is not None:
            await stack.enter_async_context(mcp_session_manager.run())

        settings: Settings = app.state.settings
        engine = DBUtils.create_engine(settings)
        app.state.engine = engine
        app.state.session_factory = DBUtils.create_session_factory(engine)

        stop_event = asyncio.Event()
        background_tasks: list[asyncio.Task] = []
        if settings.reconciler_enabled and settings.k8s_job_creation_enabled:
            reconciler = JobReconciler(settings, app.state.session_factory)
            background_tasks.append(asyncio.create_task(reconciler.run(stop_event), name="job-reconciler"))
        if settings.queue_enabled and settings.k8s_job_creation_enabled:
            queue = QueueService(settings, app.state.session_factory)
            background_tasks.append(asyncio.create_task(queue.run(stop_event), name="queue-worker"))
        if settings.retention_enabled:
            retention = RetentionService(settings, app.state.session_factory)
            background_tasks.append(asyncio.create_task(retention.run(stop_event), name="retention-cleanup"))

        try:
            yield
        finally:
            stop_event.set()
            if background_tasks:
                await asyncio.gather(*background_tasks)
            await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    AuthUtils.ensure_auth_secrets(settings)
    InputCryptoUtils.ensure_encryption_key(settings)

    app = FastAPI(
        title="PDE Operator",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(api_router, prefix=settings.api_prefix)
    mount_embedded_mcp(app, settings)
    if settings.ui_enabled:
        mount_ui(app)
    LoggingUtils.install_access_log_middleware(app, api_prefix=settings.api_prefix)

    return app
