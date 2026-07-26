"""
Platform Bootstrapper

Orchestrates the hosting of capabilities by the platform.
Provides the lifecycle management and dependency injection for hosted capabilities.
"""

from __future__ import annotations

from typing import Type, Any

from configuration.manager import ConfigurationManager
from configuration.providers import EnvironmentProvider
from capability import Capability, CapabilityContext

# Import platform dependencies
# These are platform services that capabilities receive via context
# They are assumed to be available from the platform infrastructure
class Logger:
    """Minimal logger interface for platform services."""
    def info(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...

class EventBus:
    """Minimal event bus interface for platform services."""
    def publish(self, routing_key: str, payload: dict) -> None: ...

def bootstrap(capability_type: Type[Capability]) -> Capability:
    """Bootstrap a hosted capability with platform dependencies.
    
    This function implements the platform orchestration lifecycle:
    1. Creates ConfigurationManager with platform providers
    2. Dynamically resolves the capability's configuration contract
    3. Constructs platform services (logger, event_bus)
    4. Creates CapabilityContext with resolved dependencies  
    5. Constructs and starts the capability via constructor injection
    
    Args:
        capability_type: Concrete class implementing Capability protocol
        
    Returns:
        Started capability instance
        
    Raises:
        ConfigurationResolutionFailed if required configuration is missing
    """
    # 1. Create ConfigurationManager with appropriate providers
    provider = EnvironmentProvider()
    manager = ConfigurationManager(provider)
    
    # 2. Determine configuration contract dynamically from capability type
    config_contract = capability_type.configuration_type
    
    # 3. Resolve configuration using manager (fails fast on missing config)
    configuration = manager.resolve(config_contract)
    
    # 4. Create platform services
    logger = Logger()
    event_bus = EventBus()
    
    # 5. Assemble CapabilityContext with resolved dependencies
    context = CapabilityContext(
        configuration=configuration,
        logger=logger,
        event_bus=event_bus,
    )
    
    # 6. Construct capability instance via constructor injection
    capability = capability_type(context=context)
    
    # 7. Start the capability
    capability.start()
    
    # 8. Return the started capability
    return capability