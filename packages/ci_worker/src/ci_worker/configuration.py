from pydantic import BaseModel


class RegistryConfiguration(BaseModel):
    """Configuration contract owned by the CI Worker capability.

    This contract defines the configuration required by the CI Worker.
    The platform resolves this contract via ConfigurationManager;
    the CI Worker itself never reads environment variables or .env files.
    """

    registry_username: str
    registry_password: str
    registry_url: str = "https://registry.example.com"
    worker_name: str = "ci-worker"