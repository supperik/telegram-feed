from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_settings
from api.schemas.auth import RefreshIn, TelegramInitDataIn, TokenPair
from shared.auth.initdata import verify_init_data
from shared.auth.jwt import decode_refresh, encode_access, encode_refresh
from shared.config import Settings
from shared.repositories.users import upsert_user_by_tg_id

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=TokenPair)
async def telegram(
    body: TelegramInitDataIn,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    verified = verify_init_data(body.init_data, bot_token=settings.tg_bot_token)
    user = await upsert_user_by_tg_id(
        db,
        tg_user_id=verified.tg_user_id,
        tg_username=verified.tg_username,
        tg_first_name=verified.tg_first_name,
        tg_photo_url=verified.tg_photo_url,
    )
    await db.commit()
    return TokenPair(
        access_token=encode_access(
            user_id=user.id,
            secret=settings.api_jwt_secret,
            ttl_seconds=settings.api_jwt_access_ttl_seconds,
        ),
        refresh_token=encode_refresh(
            user_id=user.id,
            secret=settings.api_jwt_secret,
            ttl_seconds=settings.api_jwt_refresh_ttl_seconds,
        ),
        expires_in=settings.api_jwt_access_ttl_seconds,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshIn,
    settings: Settings = Depends(get_settings),
) -> TokenPair:
    payload = decode_refresh(body.refresh_token, secret=settings.api_jwt_secret)
    return TokenPair(
        access_token=encode_access(
            user_id=payload.user_id,
            secret=settings.api_jwt_secret,
            ttl_seconds=settings.api_jwt_access_ttl_seconds,
        ),
        refresh_token=encode_refresh(
            user_id=payload.user_id,
            secret=settings.api_jwt_secret,
            ttl_seconds=settings.api_jwt_refresh_ttl_seconds,
        ),
        expires_in=settings.api_jwt_access_ttl_seconds,
    )
