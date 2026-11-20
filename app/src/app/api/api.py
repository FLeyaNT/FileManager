from fastapi import APIRouter

from .endpoints import file
from .endpoints import auth


router = APIRouter(
    prefix='/api',
)

router.include_router(file.router)
router.include_router(auth.router)
