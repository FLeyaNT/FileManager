from pydantic import BaseModel


class DriveInfo(BaseModel):
    device: str
    mountpoint: str
    fstype: str
    options: str
    is_ready: bool
    total: int | None = None
    used: int | None = None
    free: int | None = None
    percent: float | None = None
