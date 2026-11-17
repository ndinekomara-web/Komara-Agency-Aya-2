"""
Aya — application web autonome (sans Telegram).

Lancement :
    python app.py                 # http://localhost:8000
    uvicorn app:app --reload      # développement

L'interface est une PWA : elle s'installe sur ordinateur et sur téléphone
depuis le navigateur, comme une application classique.
"""
from __future__ import annotations

import logging
import os
import secrets
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import chat_store
import rag_engine
from config import (
    APP_ACCESS_TOKEN,
    APP_NAME,
    APP_PORT,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
)
from language_detector import change_language, detect_language, get_language
from message_router import handle_greeting, route_message
from utils import GENERIC_MESSAGES

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("aya.web")

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title=APP_NAME, docs_url="/api/docs", redoc_url=None)
chat_store.init_db()


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=80)
    lang: str | None = None


class SessionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)
    lang: str | None = None


class LoginRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# Accès (facultatif)
# ---------------------------------------------------------------------------
def _authorized(request: Request) -> bool:
    if not APP_ACCESS_TOKEN:
        return True
    supplied = request.headers.get("x-access-token") or request.cookies.get("aya_access") or ""
    return secrets.compare_digest(supplied, APP_ACCESS_TOKEN)


def require_access(request: Request) -> None:
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Accès protégé par mot de passe.")


# ---------------------------------------------------------------------------
# Logique de conversation
# ---------------------------------------------------------------------------
def _answer(session_id: str, text: str) -> dict:
    """Traite un message et renvoie la réponse (exécuté dans un thread)."""
    lang = detect_language(text, session_id)
    replies: list[str] = []

    def send(_session: str, message: str) -> None:
        if message and message not in replies:
            replies.append(message)

    # Petite touche d'accueil : première visite de la session
    previous = chat_store.history(session_id, limit=1)
    if not previous:
        greeting = handle_greeting(text, lang)
        if greeting:
            replies.append(greeting)

    route_message(session_id, text, send)

    reply = "\n\n".join(replies).strip()
    if not reply:
        reply = GENERIC_MESSAGES.get(lang, GENERIC_MESSAGES["fr"])["no_understand"]
    return {"reply": reply, "lang": lang}


# ---------------------------------------------------------------------------
# Routes API
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": APP_NAME,
        "auth": bool(APP_ACCESS_TOKEN),
        "rag": rag_engine.stats(),
        "store": chat_store.stats(),
    }


@app.post("/api/login")
def login(payload: LoginRequest, response: Response) -> dict:
    if not APP_ACCESS_TOKEN:
        return {"ok": True}
    if not secrets.compare_digest(payload.token, APP_ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect.")
    response.set_cookie(
        "aya_access",
        APP_ACCESS_TOKEN,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return {"ok": True}


@app.post("/api/chat", dependencies=[Depends(require_access)])
async def chat(payload: ChatRequest) -> dict:
    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message vide.")

    session_id = payload.session_id or str(uuid.uuid4())
    if payload.lang in SUPPORTED_LANGUAGES:
        change_language(session_id, payload.lang)

    chat_store.touch_session(session_id, payload.lang)
    chat_store.add_message(session_id, "user", text, payload.lang)

    try:
        result = await run_in_threadpool(_answer, session_id, text)
    except Exception:  # pragma: no cover - garde-fou
        logger.exception("Erreur pendant le traitement du message")
        lang = get_language(session_id)
        result = {
            "reply": GENERIC_MESSAGES.get(lang, GENERIC_MESSAGES["fr"])["no_understand"],
            "lang": lang,
        }

    chat_store.add_message(session_id, "assistant", result["reply"], result["lang"])
    return {"reply": result["reply"], "lang": result["lang"], "session_id": session_id}


@app.get("/api/history", dependencies=[Depends(require_access)])
def history(session_id: str, limit: int = 100) -> dict:
    limit = max(1, min(limit, 500))
    return {"messages": chat_store.history(session_id, limit)}


@app.post("/api/reset", dependencies=[Depends(require_access)])
def reset(payload: SessionRequest) -> dict:
    removed = chat_store.clear(payload.session_id)
    return {"removed": removed}


@app.post("/api/language", dependencies=[Depends(require_access)])
def set_language(payload: SessionRequest) -> dict:
    if payload.lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Langue non supportée.")
    change_language(payload.session_id, payload.lang)
    return {"lang": payload.lang, "current": get_language(payload.session_id)}


@app.get("/api/config")
def client_config() -> dict:
    return {
        "app_name": APP_NAME,
        "default_language": DEFAULT_LANGUAGE,
        "languages": SUPPORTED_LANGUAGES,
        "auth_required": bool(APP_ACCESS_TOKEN),
    }


# ---------------------------------------------------------------------------
# Interface (PWA)
# ---------------------------------------------------------------------------
if (WEB_DIR / "static").is_dir():
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(WEB_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/service-worker.js", include_in_schema=False)
def service_worker():
    return FileResponse(
        WEB_DIR / "service-worker.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.exception_handler(404)
def not_found(_request: Request, _exc):  # pragma: no cover
    return JSONResponse({"detail": "Introuvable"}, status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=APP_PORT, reload=False)
