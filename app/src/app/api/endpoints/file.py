from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    status,
    UploadFile,
    Form,
    Query,
    Response,
)

from app.api.schemas.dirs import DirContents, DirDeleteQuery, DirIn, DirListQuery, DirOut
from app.api.deps.storage import FileServiceDep, QuotaStorageDep, ReadFileServiceDep, ZipServiceDep
from app.api.schemas.audit import OperationOut
from app.api.schemas.files import FileIn, FileOut, FileRenameIn, StorageUsageOut
from app.api.schemas.json import JsonContent, JsonFileIn
from app.api.schemas.types import DirectoryId, FileId
from app.api.schemas.xml import XmlFileIn, XmlContent
from app.api.schemas.zip import ArchiveOut, ArchiveCreate, ArchiveExtract, ExtractOut

router = APIRouter(
    prefix='/files',
    tags=['Files'],
)


@router.post(
    '/upload',
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED
)
async def upload_file(
    file: UploadFile,
    service: FileServiceDep,
    directory_id: Annotated[DirectoryId, Form()],
):
    return await service.upload_file(
        directory_id=directory_id,
        filename=file.filename or '',
        src=file.file
    )


@router.post(
    '/dirs',
    response_model=DirOut,
    status_code=status.HTTP_201_CREATED
)
async def create_dir(
    body: DirIn,
    service: FileServiceDep,
):
    return await service.create_dir(body.parent_id, body.name)


@router.get('/dirs', response_model=DirContents)
async def list_directory(
    service: ReadFileServiceDep,
    query: Annotated[DirListQuery, Query()],
):
    return await service.list_directory(query.directory_id)


@router.delete(
    '/dirs',
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_dir(
    service: FileServiceDep,
    query: Annotated[DirDeleteQuery, Query()],
) -> Response:
    await service.delete_dir(query.directory_id, recursive=query.recursive)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    '/create',
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED
)
async def create_file(
    body: FileIn,
    service: FileServiceDep
):
    return await service.create_text_file(
        directory_id=body.directory_id,
        filename=body.filename,
        content=body.content
    )


@router.get(
    '/usage',
    response_model=StorageUsageOut,
    status_code=status.HTTP_200_OK
)
async def get_storage_usage(storage: QuotaStorageDep):
    return await storage.usage()


@router.post(
    '/json',
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED
)
async def create_json_file(
    body: JsonFileIn,
    service: FileServiceDep
):
    return await service.create_json_file(
        directory_id=body.directory_id,
        filename=body.filename,
        data=body.data
    )


@router.get(
    '/json',
    response_model=JsonContent,
    status_code=status.HTTP_200_OK
)
async def read_json_file(
    service: ReadFileServiceDep,
    file_id: Annotated[FileId, Query()],
):
    data = await service.read_json_file(file_id)
    return JsonContent(data=data)


@router.post(
    '/xml',
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED
)
async def create_xml_file(
    body: XmlFileIn,
    service: FileServiceDep
):
    return await service.create_xml_file(
        directory_id=body.directory_id,
        filename=body.filename,
        root=body.root
    )


@router.get(
    '/xml',
    response_model=XmlContent
)
async def read_xml_file(
    service: ReadFileServiceDep,
    file_id: Annotated[FileId, Query()],
):
    root = await service.read_xml_file(file_id)
    return XmlContent(root=root)


@router.post(
    "/zip",
    response_model=ArchiveOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_zip(body: ArchiveCreate, service: ZipServiceDep) -> ArchiveOut:
    file, count = await service.create(body.sources, body.directory_id, body.filename)
    return ArchiveOut(
        id=file.id,
        directory_id=file.directory_id,
        filename=file.filename,
        size=file.size,
        files=count,
    )


@router.post(
    "/zip/extract",
    response_model=ExtractOut,
    status_code=status.HTTP_201_CREATED,
)
async def extract_zip(body: ArchiveExtract, service: ZipServiceDep) -> ExtractOut:
    directory_id, files = await service.extract(
        body.file_id, body.directory_id, body.name
    )
    return ExtractOut(directory_id=directory_id, files=[FileOut.model_validate(file) for file in files])


@router.delete(
    '',
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_file(
    service: FileServiceDep,
    file_id: Annotated[FileId, Query()],
) -> Response:
    await service.delete_file(file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/rename', response_model=FileOut)
async def rename_file(body: FileRenameIn, service: FileServiceDep):
    return await service.rename_file(body.file_id, body.new_name)


@router.put('/content', response_model=FileOut)
async def replace_file_content(
    file: UploadFile,
    service: FileServiceDep,
    file_id: Annotated[FileId, Query()],
):
    return await service.replace_file(file_id, file.file)


@router.get('', response_model=list[FileOut])
async def list_files(service: ReadFileServiceDep):
    return await service.list_files()


@router.get('/operations', response_model=list[OperationOut])
async def list_operations(
    service: ReadFileServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await service.list_operations(limit)


@router.get('/{file_id}', response_model=FileOut)
async def get_file(file_id: FileId, service: ReadFileServiceDep):
    return await service.get_file(file_id)


@router.get('/{file_id}/download', response_class=Response)
async def download_file(file_id: FileId, service: ReadFileServiceDep) -> Response:
    filename, content = await service.download_file(file_id)
    return Response(
        content=content,
        media_type='application/octet-stream',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename, safe='')}"},
    )
