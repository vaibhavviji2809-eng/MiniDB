class MiniDBError(Exception):
    """Base class for MiniDB errors."""


class LexerError(MiniDBError):
    pass


class ParseError(MiniDBError):
    pass


class PlanningError(MiniDBError):
    pass


class StorageError(MiniDBError):
    pass


class TransactionError(MiniDBError):
    pass

