class AppError(Exception):
    status_code: int = 400
    default_detail: str = 'Некорректный запрос'

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class UnsafePathError(AppError):
    status_code = 400
    default_detail = 'Недопустимый путь'


class FileTooLargeError(AppError):
    status_code = 413
    default_detail = 'Файл превышает допустимый размер'


class ArchiveLimitError(AppError):
    status_code = 422
    default_detail = 'Архив превышает допустимые ограничения'


class InvalidDocumentError(AppError):
    status_code = 422
    default_detail = 'Некорректный документ'
