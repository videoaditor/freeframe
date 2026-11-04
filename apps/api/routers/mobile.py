"""Mobile feedback backend: dictation and the Telegram link/webhook."""
import secrets
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..middleware.auth import get_current_user
from ..middleware.rate_limit import rate_limit
from ..models.user import User
from ..services import dictation, telegram

router = APIRouter(tags=["mobile"])


@router.post("/dictate", dependencies=[Depends(rate_limit("dictate", 60, 600))])
async def dictate(audio: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    data = await audio.read(dictation.MAX_BYTES + 1)
    return {"text": dictation.transcribe(data, audio.filename or "", audio.content_type or "")}


@router.post("/me/telegram/link")
def telegram_link(current_user: User = Depends(get_current_user)):
    if not settings.telegram_bot_username:
        raise HTTPException(503, "telegram_unavailable")
    return {"url": telegram.link_url(current_user.id)}


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    secret = settings.telegram_webhook_secret
    presented = request.headers.get("x-telegram-bot-api-secret-token", "")
    if not secret or not secrets.compare_digest(presented, secret):
        raise HTTPException(401, "invalid_secret")
    update: Any = await request.json()
    message = update.get("message") if isinstance(update, dict) else None
    text = (message or {}).get("text") or ""
    chat = ((message or {}).get("chat") or {}).get("id")
    if chat is not None and text.startswith("/start "):
        ok = telegram.bind_chat(db, text.split(maxsplit=1)[1].strip(), chat)
        telegram.send(str(chat), "Connected. You will get a message here when a video is ready for your review." if ok
                      else "That link has expired. Create a new one in AutoReview.")
    return {"ok": True}
