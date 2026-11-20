from collections.abc import Iterable

from sqlalchemy import Text, case, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import CTE

from app.core.exceptions import NotFoundError, PathConflictError
from app.postgres.models import Directory


class DirectoryRepository:
    def __init__(self, session: AsyncSession, owner_id: int) -> None:
        self._session = session
        self._owner_id = owner_id

    def tree(self, directory_id: int | None = None, *, path: str = '') -> CTE:
        start = Directory.parent_id.is_(None) if directory_id is None else Directory.id == directory_id
        tree = (
            select(Directory.id, literal(path, type_=Text()).label('path'))
            .where(Directory.owner_id == self._owner_id, start)
            .cte(recursive=True)
        )
        child_path = case(
            (tree.c.path == '', Directory.name),
            else_=tree.c.path + '/' + Directory.name,
        )
        return tree.union_all(
            select(Directory.id, child_path)
            .join(tree, Directory.parent_id == tree.c.id)
            .where(Directory.owner_id == self._owner_id)
        )

    async def get(
        self, *, directory_id: int | None = None, path: str = ''
    ) -> tuple[Directory, str]:
        tree = self.tree()
        selector = tree.c.path == path if directory_id is None else Directory.id == directory_id
        stmt = select(Directory, tree.c.path).join(tree, Directory.id == tree.c.id).where(selector)
        entry = (await self._session.execute(stmt)).tuples().one_or_none()
        if entry is None:
            raise NotFoundError('Папка не найдена')
        return entry

    async def list_children(self, directory_id: int) -> list[Directory]:
        stmt = (
            select(Directory)
            .where(Directory.owner_id == self._owner_id, Directory.parent_id == directory_id)
            .order_by(Directory.name, Directory.id)
        )
        return list(await self._session.scalars(stmt))

    async def create(self, parent_id: int, name: str) -> Directory:
        stmt = (
            insert(Directory)
            .values(owner_id=self._owner_id, parent_id=parent_id, name=name)
            .on_conflict_do_nothing(index_elements=[Directory.parent_id, Directory.name])
            .returning(Directory)
        )
        directory = await self._session.scalar(stmt)
        if directory is None:
            raise PathConflictError()
        return directory

    async def ensure_paths(self, paths: Iterable[str]) -> dict[str, int]:
        tree = self.tree()
        rows = await self._session.execute(select(tree.c.path, tree.c.id))
        ids = {path: directory_id for path, directory_id in rows.tuples()}
        if '' not in ids:
            raise NotFoundError('Корневая папка не найдена')

        for path in paths:
            current = ''
            for name in path.split('/') if path else ():
                parent = current
                current = f'{parent}/{name}' if parent else name
                if current not in ids:
                    directory = await self.create(ids[parent], name)
                    ids[current] = directory.id
        return ids

    async def remove(self, directory: Directory) -> None:
        await self._session.flush()
        await self._session.delete(directory)
