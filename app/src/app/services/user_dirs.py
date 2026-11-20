from pathlib import Path
from anyio import Path as AsyncPath


class UserDirectories:

    def __init__(
        self,
        storage_root: Path
    ) -> None:
        self._root = AsyncPath(storage_root.resolve())

    def path(self, user_id: int) -> AsyncPath:
        return self._root / str(int(user_id))

    async def create_personal_dir(self, user_id: int) -> AsyncPath:
        await self._root.mkdir(parents=True, exist_ok=True)

        target = self.path(user_id)
        await target.mkdir(mode=0o700)

        return target

    async def remove_empty(self, user_id: int) -> None:
        try:
            await self.path(user_id).rmdir()
        except OSError:
            pass
