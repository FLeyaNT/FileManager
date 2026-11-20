from sqlalchemy import Select, Text, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import CTE

from app.core.exceptions import NotFoundError
from app.postgres.models import File, Operation
from app.postgres.models.enums.operation_type import OperationType
from app.postgres.repositories.directory_repo import DirectoryRepository


class FileRepository:

    def __init__(self, session: AsyncSession, owner_id: int) -> None:
        self._session = session
        self._owner_id = owner_id
        self.directories = DirectoryRepository(session, owner_id)

    def _files_with_paths(self, tree: CTE) -> Select[tuple[File, str]]:
        path = func.concat_ws('/', func.nullif(tree.c.path, ''), File.filename, type_=Text())
        return (
            select(File, path)
            .join(tree, File.directory_id == tree.c.id)
            .where(File.owner_id == self._owner_id)
        )

    async def get(self, file_id: int) -> tuple[File, str]:
        stmt = self._files_with_paths(self.directories.tree()).where(File.id == file_id)
        entry = (await self._session.execute(stmt)).tuples().one_or_none()
        if entry is None:
            raise NotFoundError('Файл не найден')
        return entry

    async def list_files(self) -> list[File]:
        stmt = select(File).where(File.owner_id == self._owner_id).order_by(File.id)
        return list(await self._session.scalars(stmt))

    async def list_with_paths(self) -> list[tuple[File, str]]:
        stmt = self._files_with_paths(self.directories.tree()).order_by(File.id)
        return list((await self._session.execute(stmt)).tuples())

    async def list_in(self, directory_id: int) -> list[File]:
        stmt = (
            select(File)
            .where(File.owner_id == self._owner_id, File.directory_id == directory_id)
            .order_by(File.filename, File.id)
        )
        return list(await self._session.scalars(stmt))

    async def list_under(self, directory_id: int, path: str) -> list[tuple[File, str]]:
        stmt = self._files_with_paths(self.directories.tree(directory_id, path=path))
        return list((await self._session.execute(stmt)).tuples())

    async def upsert(self, directory_id: int, filename: str, size: int) -> File:
        stmt = insert(File).values(
            owner_id=self._owner_id,
            directory_id=directory_id,
            filename=filename,
            size=size,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[File.directory_id, File.filename],
            set_={
                'size': stmt.excluded.size,
                'updated_at': func.now(),
            },
        ).returning(File)
        result = await self._session.execute(
            stmt, execution_options={'populate_existing': True}
        )
        return result.scalar_one()

    def record(
        self,
        kind: OperationType,
        file: File,
    ) -> None:
        self._session.add(Operation(
            operation_type=kind,
            user_id=self._owner_id,
            file_id=None if kind == OperationType.DELETE else file.id,
            file_id_snapshot=file.id,
        ))

    async def remove(self, file: File) -> None:
        await self._session.delete(file)

    async def list_operations(self, limit: int) -> list[Operation]:
        stmt = (
            select(Operation)
            .where(Operation.user_id == self._owner_id)
            .order_by(Operation.id.desc())
            .limit(limit)
        )
        return list(await self._session.scalars(stmt))

    async def commit(self) -> None:
        await self._session.commit()
