import uvicorn

from pde_operator.app import create_app
from pde_operator.config import Settings
from pde_operator.utils.logging_utils import LoggingUtils


def main() -> None:
    settings = Settings()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        timeout_keep_alive=settings.keep_alive_timeout_seconds,
        log_config=LoggingUtils.uvicorn_log_config(settings.log_level),
        access_log=False,
    )


if __name__ == "__main__":
    main()
