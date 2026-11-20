class AppError(Exception):
    status_code: int = 400
    default_detail: str = 'Некорректный запрос'
    headers: dict[str, str] | None = None

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class UnsafePathError(AppError):
    status_code = 400
    default_detail = 'Недопустимый путь'


class PathConflictError(AppError):
    status_code = 409
    default_detail = 'Файл или папка с таким именем уже существуют'


class FileTooLargeError(AppError):
    status_code = 413
    default_detail = 'Файл превышает допустимый размер'


class ArchiveLimitError(AppError):
    status_code = 422
    default_detail = 'Архив превышает допустимые ограничения'


class InvalidDocumentError(AppError):
    status_code = 422
    default_detail = 'Некорректный документ'


class UserAlreadyExistsError(AppError):
    status_code = 409
    default_detail = 'Пользователь уже существует'


class AuthenticationError(AppError):
    status_code = 401
    default_detail = 'Неверный логин или пароль'
    headers = {'WWW-Authenticate': 'Bearer'}


class NotFoundError(AppError):
    status_code = 404
    default_detail = 'Ресурс не найден'


class ForbiddenOriginError(AppError):
    status_code = 403
    default_detail = 'Запрос с недопустимого адреса'


class StorageError(AppError):
    status_code = 500
    default_detail = 'Хранилище временно недоступно'


class QuotaExceededError(AppError):
    status_code = 507
    default_detail = "Превышена квота личного хранилища"


class StorageBusyError(AppError):
    status_code = 503
    default_detail = (
        "Хранилище занято другой операцией. Повторите запрос"
    )
