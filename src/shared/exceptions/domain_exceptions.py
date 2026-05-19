class DomainException(Exception):  # noqa: N818
    """Base domain exception."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class EntityNotFoundException(DomainException):
    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity} with id '{entity_id}' not found",
            code="ENTITY_NOT_FOUND",
        )
        self.entity = entity
        self.entity_id = entity_id


class FieldNotFoundException(EntityNotFoundException):
    def __init__(self, field_id: str) -> None:
        super().__init__("Field", field_id)


class AnalysisNotFoundException(EntityNotFoundException):
    def __init__(self, analysis_id: str) -> None:
        super().__init__("Analysis", analysis_id)


class InvalidGeometryException(DomainException):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Invalid geometry: {reason}",
            code="INVALID_GEOMETRY",
        )


class AnalysisAlreadyRunningException(DomainException):
    def __init__(self, field_id: str) -> None:
        super().__init__(
            message=f"An analysis is already running for field '{field_id}'",
            code="ANALYSIS_ALREADY_RUNNING",
        )


class EarthEngineException(DomainException):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Earth Engine error: {reason}",
            code="EARTH_ENGINE_ERROR",
        )


class CacheException(DomainException):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Cache error: {reason}",
            code="CACHE_ERROR",
        )


class AuthenticationException(DomainException):
    def __init__(self, reason: str = "Invalid credentials") -> None:
        super().__init__(message=reason, code="AUTHENTICATION_FAILED")


class AuthorizationException(DomainException):
    def __init__(self, reason: str = "Insufficient permissions") -> None:
        super().__init__(message=reason, code="AUTHORIZATION_FAILED")


class RateLimitExceededException(DomainException):
    def __init__(self) -> None:
        super().__init__(
            message="Rate limit exceeded. Please slow down.",
            code="RATE_LIMIT_EXCEEDED",
        )
