"""Custom repository exceptions for the Fraud Investigation Agent."""


class RepositoryError(Exception):
    """Base exception for all repository data access errors."""
    pass


class TigerGraphUnavailableError(RepositoryError):
    """Raised when TigerGraph is unavailable and TIGERGRAPH_FALLBACK_POLICY is set to 'fail_closed'."""
    pass


class CheckpointError(Exception):
    """Base exception for checkpoint operations."""
    pass


class CheckpointNotFoundError(CheckpointError):
    """Raised when a requested checkpoint does not exist or has expired."""
    pass
