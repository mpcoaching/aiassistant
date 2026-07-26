from ci_worker.configuration import RegistryConfiguration


class CIWorker:
    """CI Worker capability hosted by the platform bootstrapper.

    This capability receives all dependencies via CapabilityContext constructor injection.
    It owns its configuration contract (RegistryConfiguration) but never reads
    environment variables or .env files directly — the platform resolves them.
    """

    configuration_type = RegistryConfiguration

    def __init__(self, context: CapabilityContext) -> None:
        self._context = context

    def start(self) -> None:
        self._context.logger.info(
            "CI Worker started",
            extra={"worker_name": self._context.configuration.worker_name},
        )

    def stop(self) -> None:
        self._context.logger.info(
            "CI Worker stopped",
            extra={"worker_name": self._context.configuration.worker_name},
        )