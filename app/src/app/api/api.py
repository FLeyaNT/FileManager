from fastapi import APIRouter

from .endpoints import file


router = APIRouter(
    prefix='/api',
)

router.include_router(file.router)
