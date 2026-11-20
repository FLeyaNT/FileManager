from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.postgres.models.enums.operation_type import OperationType


class OperationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime = Field(validation_alias='created_at')
    operation_type: OperationType
    file_id: int | None = Field(validation_alias='file_id_snapshot')
