'''DeepSecure SDK Package'''

__version__ = "0.1.12"

from .client import Client
from .exceptions import (
    DeepSecureError,
    ApiError,
    VaultError,
    IdentityManagerError,
    DeepSecureClientError,
)
from ._core.bootstrap import bootstrap, BootstrapClient, BootstrapResult, Platform

__all__ = [
    "Client",
    "bootstrap",
    "BootstrapClient",
    "BootstrapResult",
    "Platform",
    "DeepSecureError",
    "ApiError",
    "VaultError",
    "IdentityManagerError",
    "DeepSecureClientError",
    "__version__",
]

# Placeholder for package initialization 

# deepsecure package 
