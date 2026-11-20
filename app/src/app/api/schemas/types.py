from typing import Annotated

from pydantic import Field, StringConstraints


Username = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{3,50}$")]

Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]

RelPath = Annotated[str, StringConstraints(min_length=1, max_length=255)]
Filename = Annotated[str, StringConstraints(min_length=1, max_length=255)]

FileId = Annotated[int, Field(gt=0, le=2_147_483_647)]
DirectoryId = Annotated[int, Field(gt=0, le=2_147_483_647)]
