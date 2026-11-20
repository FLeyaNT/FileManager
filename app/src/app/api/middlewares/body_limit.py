from tempfile import SpooledTemporaryFile

import anyio
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send


class BodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        max_bytes: int,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        with SpooledTemporaryFile[bytes](
            max_size=1024 * 1024,
            mode="w+b",
        ) as buffer:
            total = 0

            while True:
                message = await receive()

                if message["type"] == "http.disconnect":
                    return

                chunk: bytes = message.get("body", b"")
                total += len(chunk)

                if total > self.max_bytes:
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "detail": "Превышен размер HTTP-запроса"
                        },
                    )
                    await response(scope, receive, send)
                    return

                await anyio.to_thread.run_sync(
                    lambda: buffer.write(chunk),
                )

                if not message.get("more_body", False):
                    break

            await anyio.to_thread.run_sync(
                lambda: buffer.seek(0)
            )

            replayed = False

            async def limited_receive():
                nonlocal total, replayed

                if replayed:
                    return await receive()

                data = await anyio.to_thread.run_sync(
                    buffer.read,
                    64 * 1024,
                )

                total -= len(data)
                replayed = total == 0

                return {
                    "type": "http.request",
                    "body": data,
                    "more_body": not replayed,
                }

            await self.app(scope, limited_receive, send)
