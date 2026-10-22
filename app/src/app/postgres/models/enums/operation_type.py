import enum


class OperationType(enum.StrEnum):
    LOGIN = "login"
    CREATE = "create"
    READ = "read"
    MODIFY = "modify"
    DELETE = "delete"
    ARCHIVE = "archive"
    EXTRACT = "extract"
