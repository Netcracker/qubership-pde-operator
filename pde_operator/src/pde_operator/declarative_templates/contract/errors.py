class DeclarativeContractError(ValueError):
    """Invalid declarative template contract or submitted field values."""


class DeclarativeOptionsProviderError(RuntimeError):
    """Enum options provider is unavailable (e.g. no Kubernetes config)."""
