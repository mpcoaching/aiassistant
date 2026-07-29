from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from configuration.config import ConfigurationManagerConfig
from configuration.routes.contracts import router as contracts_router
from configuration.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Configuration Manager", version="0.1.0")
    app.include_router(contracts_router, prefix="/contracts")
    app.include_router(health_router, prefix="/health")
    return app


app = create_app()


if __name__ == "__main__":
    config = ConfigurationManagerConfig()
    uvicorn.run(app, host=config.host, port=config.port)