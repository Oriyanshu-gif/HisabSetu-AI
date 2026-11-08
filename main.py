"""HisabSetu AI — FastAPI application.

Run locally:  uvicorn main:app --reload
Docs:         http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import json
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import Depends, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from audio_utils import AudioError, find_ffmpeg, prepare_for_stt
from config import BASE_DIR, settings, gnani_key_source
from database import SessionLocal, get_db, init_db
from languages import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    UnsupportedLanguage,
    catalogue,
    normalize as normalize_language,
    stt_format_for,
    voice_for,
)
from messages import language_key
from gnani_client import (
    GnaniError,
    GnaniNotConfigured,
    is_configured,
    require_configured,
    synthesize,
    transcribe,
)
from schemas import (
    CommandRequest,
    ConfirmRequest,
    CustomerCreate,
    ManualProposalRequest,
    TtsRequest,
)
from seed import seed_sample_data
from services import (
    ServiceError,
    cancel_pending,
    confirm_pending,
    create_customer,
    daily_summary,
    dashboard,
    get_pending,
    handle_command,
    list_customers,
    list_transactions,
    manual_proposal,
    top_debtors,
)

APP_VERSION = "1.0.0"

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.seed_sample_data:
        with SessionLocal() as session:
            seed_sample_data(session)
    yield


app = FastAPI(
    title="HisabSetu AI — Bolo. Likho. Hisaab Rakho.",
    version=APP_VERSION,
    description=(
        "Bolo. Likho. Hisaab Rakho. "
        "Voice-first khata for kirana shopkeepers, in Hindi/Hinglish and nine "
        "more Indian languages; transactions are only posted after explicit "
        "confirmation."
    ),
    lifespan=lifespan,
)

class _NoCacheStaticFiles(StaticFiles):
    """Serve static assets with a revalidation hint.

    Without a Cache-Control header browsers apply heuristic freshness and can
    keep running a stale app.js/app.css across restarts. `no-cache` still allows
    304 revalidation (so it stays fast) but forces the browser to check for a
    newer copy each load, which matters for the theme/language frontend code.
    """

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers.setdefault("Cache-Control", "no-cache")
        return response


app.mount("/static", _NoCacheStaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Evaluation artifacts — served read-only alongside the app for review
# ---------------------------------------------------------------------------


@app.get("/report.md", include_in_schema=False)
def eval_markdown():
    """Most recent HisabSetu AI STT + parser eval report.

    Regenerate with ``python eval_report.py --markdown report.md`` from the
    project root, then reload this page.  The report is a static file served
    from the project directory; it is not a live API call and does not depend
    on the Gnani key or the database.
    """
    return FileResponse(BASE_DIR / "report.md", media_type="text/markdown")


@app.get("/report.csv", include_in_schema=False)
def eval_csv():
    """CSV variant of the same eval report."""
    return FileResponse(BASE_DIR / "report.csv", media_type="text/csv")



# ---------------------------------------------------------------------------
# Error handling and a tiny in-process rate limit
# ---------------------------------------------------------------------------


def error_response(error: ServiceError | GnaniError | AudioError) -> JSONResponse:
    payload = {
        "error": {
            "code": error.code,
            "message": error.message,
            "hint": getattr(error, "hint", None),
        }
    }
    return JSONResponse(payload, status_code=error.status_code, headers={"Cache-Control": "no-store"})


@app.exception_handler(ServiceError)
async def service_error_handler(_request: Request, exc: ServiceError):
    return error_response(exc)


@app.exception_handler(GnaniError)
async def gnani_error_handler(_request: Request, exc: GnaniError):
    return error_response(exc)


@app.exception_handler(AudioError)
async def audio_error_handler(_request: Request, exc: AudioError):
    return error_response(exc)


class _RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window = window_seconds
        self.hits: deque[float] = deque()

    def check(self) -> bool:
        now = time.monotonic()
        while self.hits and now - self.hits[0] > self.window:
            self.hits.popleft()
        if len(self.hits) >= self.limit:
            return False
        self.hits.append(now)
        return True


_stt_limiter = _RateLimiter(limit=40)
_tts_limiter = _RateLimiter(limit=40)


def _language_or_400(code: str | None) -> str:
    """Validate a requested language against the allow-list (HTTP 400 if not).

    The provider is never called with a code this app has not whitelisted.
    An absent value means "use the configured default".
    """
    try:
        return normalize_language(code)
    except UnsupportedLanguage as exc:
        raise ServiceError(
            "invalid_language",
            str(exc),
            400,
            hint="Supported: " + ", ".join(SUPPORTED_LANGUAGES),
        ) from exc


def _enforce(limiter: _RateLimiter, label: str) -> None:
    if not limiter.check():
        raise ServiceError(
            "rate_limited",
            f"Bahut zyada {label} requests. Ek minute ruk kar try karein.",
            429,
        )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(TEMPLATES_DIR / "index.html", media_type="text/html")


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/manifest.webmanifest", include_in_schema=False)
def web_manifest(lang: str | None = Query(default=None, description="Active language")):
    """PWA manifest with the instalment name in the active language.

    Served from the root so `scope` can cover the whole app.  The interface
    strings already hold the translated names, so the manifest reuses them and
    falls back to the English manifest file when a language has no entry.
    """
    path = STATIC_DIR / "manifest.webmanifest"
    data = json.loads(path.read_text(encoding="utf-8"))
    code = language_key(lang)
    strings_path = STATIC_DIR / "i18n" / f"{code}.json"
    if strings_path.exists():
        strings = json.loads(strings_path.read_text(encoding="utf-8"))
        data["name"] = strings.get("app_title", data.get("name"))
        data["short_name"] = strings.get("voice_khata", data.get("short_name"))
        if strings.get("tagline"):
            data["description"] = strings["tagline"]
        data["lang"] = code
    return Response(
        content=json.dumps(data, ensure_ascii=False),
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    """Service worker at the root path, so its scope is `/` and not `/static/`."""
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache",
        },
    )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["system"], summary="Health, Gnani and FFmpeg configuration")
def health(db: Session = Depends(get_db)):
    from sqlalchemy import text

    database_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    configured = is_configured()
    return {
        "status": "ok" if database_status == "ok" else "degraded",
        "app": "HisabSetu AI",
        "version": APP_VERSION,
        "time_ist": datetime.now(settings.ist).isoformat(),
        "database": database_status,
        "gnani": {
            "configured": configured,
            # Diagnostic only: where the key was loaded from (never the value),
            # so "configured: false" can be explained instead of guessed.
            "config_source": gnani_key_source(),
            "stt_configured": configured,
            "tts_configured": configured,
            "stt_language": settings.gnani_stt_language,
            "tts_model": settings.gnani_tts_model,
            "tts_voice": settings.gnani_tts_voice,
            "tts_language": settings.gnani_tts_language,
            "mode": "live" if configured else "unconfigured",
        },
        "audio": {
            "ffmpeg_available": find_ffmpeg() is not None,
            "max_record_seconds": settings.max_record_seconds,
            "max_upload_mb": round(settings.max_audio_bytes / 1_000_000, 1),
        },
        "ledger_convention": "credit increases outstanding; payment decreases it",
    }


# ---------------------------------------------------------------------------
# Ledger reads
# ---------------------------------------------------------------------------


@app.get("/api/dashboard", tags=["ledger"], summary="Totals, today's activity and counts")
def api_dashboard(db: Session = Depends(get_db)):
    return dashboard(db)


@app.get("/api/customers", tags=["ledger"], summary="Customers with derived balances")
def api_customers(
    search: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
):
    customers = list_customers(db)
    if search:
        needle = search.strip().lower()
        customers = [
            customer
            for customer in customers
            if needle in customer["name"].lower() or needle in customer["name"].lower().replace(" ", "")
        ]
    return {"customers": customers, "count": len(customers)}


@app.post(
    "/api/customers",
    tags=["ledger"],
    status_code=201,
    summary="Explicitly add a customer (never automatic)",
)
def api_create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    return {"customer": create_customer(db, payload.name)}


@app.get("/api/customers/{customer_id}", tags=["ledger"], summary="One customer with balance")
def api_customer(customer_id: int, db: Session = Depends(get_db)):
    from services import get_balance_paise, serialize_customer
    from models import Customer

    customer = db.get(Customer, customer_id)
    if customer is None:
        raise ServiceError("unknown_customer", "Yeh customer ledger mein nahi mila.", 404)
    balance = get_balance_paise(db, customer.id)
    return {
        "customer": serialize_customer(customer, balance),
        "transactions": list_transactions(db, limit=200, customer_id=customer.id),
    }


@app.get("/api/transactions", tags=["ledger"], summary="Recent transaction history")
def api_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    customer_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return {"transactions": list_transactions(db, limit=limit, customer_id=customer_id)}


@app.get("/api/top-debtors", tags=["insights"], summary="Customers with the highest outstanding")
def api_top_debtors(limit: int = Query(default=5, ge=1, le=20), db: Session = Depends(get_db)):
    return {"customers": top_debtors(db, limit=limit)}


@app.get("/api/daily-summary", tags=["insights"], summary="Daily summary in IST")
def api_daily_summary(
    day: date | None = Query(default=None, alias="date"),
    lang: str | None = Query(default=None, description="Active language, e.g. ta-IN"),
    db: Session = Depends(get_db),
):
    return daily_summary(db, day, _language_or_400(lang))


# ---------------------------------------------------------------------------
# Voice + commands
# ---------------------------------------------------------------------------


@app.get("/api/languages", tags=["voice"], summary="Accepted voice languages")
def api_languages():
    """Allow-list plus, per language, what the app can honestly do with it.

    ``spoken_numbers`` is true where a tested number-word table exists,
    ``stt_format`` is the Prisma format chosen for that language by
    ``eval_langs.py``, and ``voice_available`` is false when Timbre speech has
    to fall back to another language.
    """
    return {"languages": catalogue(), "default": DEFAULT_LANGUAGE}


@app.post("/api/stt", tags=["voice"], summary="Transcribe recorded audio with Gnani Prisma")
async def api_stt(
    file: UploadFile = File(..., description="Browser recording (WebM/MP4) or WAV/MP3/OGG"),
    language: str | None = Form(default=None, description="Active voice language, e.g. hi-IN"),
):
    _enforce(_stt_limiter, "speech")
    require_configured("speech-to-text")
    requested = _language_or_400(language)

    raw = await file.read()
    prepared = prepare_for_stt(raw, file.content_type, file.filename)
    # Per-request override only: settings.gnani_stt_language is never written.
    result = transcribe(
        prepared.data, language=requested, audio_format=stt_format_for(requested)
    )

    return {
        "transcript": result.transcript,
        "provider": "gnani-prisma",
        "language": requested,
        "requested_language": requested,
        "request_id": result.request_id,
        "model": result.model,
        "audio": {
            "original_format": prepared.original_format,
            "converted": prepared.converted,
            "duration_seconds": prepared.duration_seconds,
            "sample_rate": prepared.sample_rate,
            "channels": prepared.channels,
            "bytes": len(prepared.data),
        },
    }


@app.post("/api/command", tags=["voice"], summary="Parse a transcript and preview the action")
def api_command(payload: CommandRequest, db: Session = Depends(get_db)):
    language = _language_or_400(payload.language)
    return handle_command(db, payload.text, payload.source, payload.customer_id, language)


@app.post("/api/manual-proposal", tags=["voice"], summary="Correct details by hand, then confirm")
def api_manual_proposal(payload: ManualProposalRequest, db: Session = Depends(get_db)):
    return manual_proposal(
        db,
        customer_id=payload.customer_id,
        txn_type=payload.type,
        amount_rupees=payload.amount_rupees,
        transcript=payload.transcript,
        language=_language_or_400(payload.language),
    )


@app.post("/api/pending/{pending_id}/confirm", tags=["ledger"], summary="Confirm and post once")
def api_confirm(
    pending_id: str,
    payload: ConfirmRequest | None = None,
    lang: str | None = Query(default=None, description="Active language, e.g. ta-IN"),
    db: Session = Depends(get_db),
):
    acknowledge = bool(payload.acknowledge_overpayment) if payload else False
    return confirm_pending(
        db,
        pending_id,
        acknowledge_overpayment=acknowledge,
        language=_language_or_400(lang),
    )


@app.post("/api/pending/{pending_id}/cancel", tags=["ledger"], summary="Cancel without ledger impact")
def api_cancel(
    pending_id: str,
    lang: str | None = Query(default=None, description="Active language, e.g. ta-IN"),
    db: Session = Depends(get_db),
):
    return cancel_pending(db, pending_id, language=_language_or_400(lang))


@app.get("/api/pending/{pending_id}", tags=["ledger"], summary="Pending confirmation status")
def api_pending(pending_id: str, db: Session = Depends(get_db)):
    return get_pending(db, pending_id)


# ---------------------------------------------------------------------------
# Text to speech
# ---------------------------------------------------------------------------


@app.post(
    "/api/tts",
    tags=["voice"],
    summary="Speak a reply with Gnani Timbre",
    response_class=Response,
    responses={200: {"content": {"audio/wav": {}}}},
)
def api_tts(payload: TtsRequest):
    """Speak a reply with Gnani Timbre.

    Status contract (documented and covered by tests):

    * ``200`` — real audio bytes, ``content-type`` from the provider (``audio/wav``).
    * ``422`` — reply text empty or longer than ``MAX_TTS_CHARS``.
    * ``429`` — local rate limit.
    * ``502`` — provider/network failure (code ``gnani_*``).
    * ``503`` — ``GNANI_API_KEY`` missing (code ``gnani_not_configured``).

    A 200 is never returned unless the provider actually handed back audio.
    """
    _enforce(_tts_limiter, "voice reply")
    require_configured("text-to-speech")
    requested = _language_or_400(payload.language)
    # No verified voice for this language -> speak in en-IN and say so, rather
    # than passing a guessed voice name to the provider.
    voice, spoken_language, fell_back = voice_for(requested)
    if len(payload.text) > settings.max_tts_chars:
        raise ServiceError(
            "tts_text_too_long",
            f"Reply {settings.max_tts_chars} characters se chhota rakhein.",
            422,
        )
    result = synthesize(payload.text, language=spoken_language, voice=voice)
    if not result.audio:
        # Defensive: synthesize() already refuses empty bodies, but a 200 here
        # would tell the UI that speech was produced when none was.
        raise GnaniError(
            "gnani_empty_audio",
            "Gnani ne khaali audio bheja.",
            "Phir try karein; text reply screen par dikh raha hai.",
            502,
        )
    return Response(
        content=result.audio,
        media_type=result.content_type,
        headers={
            "Cache-Control": "no-store",
            "X-Voice-Provider": "gnani-timbre",
            "X-Voice-Language": spoken_language,
            "X-Voice-Requested-Language": requested,
            "X-Voice-Fallback": "true" if fell_back else "false",
        },
    )
