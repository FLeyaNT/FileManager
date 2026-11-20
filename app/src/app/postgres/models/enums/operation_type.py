import enum


class OperationType(enum.StrEnum):
    CREATE = "create"
    READ = "read"
    MODIFY = "modify"
    DELETE = "delete"
    ARCHIVE = "archive"
    EXTRACT = "extract"
