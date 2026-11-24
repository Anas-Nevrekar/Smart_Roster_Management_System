class EngineIntegrationError(RuntimeError):
    """An operational failure while invoking the external engine worker."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
