from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import Base, engine
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.hooks import install_foundation_hooks
from app.routers import auth as auth_router
from app.routers import (
    cars,
    cash_received,
    deposits,
    entities,
    expenses,
    gate_passes,
    hr,
    inventory,
    invoices,
    job_cards,
    labour_codes,
    money_facade,
    periods,
    pipeline_status,
    public_quotes,
    qc,
    repair_orders,
    reports,
    settings as settings_router,
    variations,
    vendors,
    whatsapp,
)

import app.models  # noqa: F401  (register tables on Base)

_UPLOAD_DIR = Path(__file__).resolve().parent / "static" / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    install_foundation_hooks()
    Base.metadata.create_all(bind=engine)
    from app.db import SessionLocal
    from app.foundation.branch import ensure_default_branch

    db = SessionLocal()
    try:
        ensure_default_branch(db)
        from app.foundation.settings import ensure_default_settings
        from app.visits import ensure_default_inspection_template

        ensure_default_settings(db)
        ensure_default_inspection_template(db)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
    yield


app = FastAPI(title="GermanATO API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def foundation_request_context(request: Request, call_next):
    """Bind branch + audit reason for the duration of each request."""
    import re

    from app.foundation.context import current_branch_id, current_reason, current_user_obj

    raw = (request.headers.get("X-Branch-Id") or "").strip().lower()
    bid = raw if re.fullmatch(r"[0-9a-f]{8}", raw) else DEFAULT_BRANCH_ID
    reason = (request.headers.get("X-Audit-Reason") or "").strip() or None
    t_branch = current_branch_id.set(bid)
    t_reason = current_reason.set(reason)
    t_user = current_user_obj.set(None)
    try:
        return await call_next(request)
    finally:
        current_branch_id.reset(t_branch)
        current_reason.reset(t_reason)
        current_user_obj.reset(t_user)

# Match backend/app.py blueprint prefixes
app.include_router(auth_router.router)  # prefix=/api/auth on router
app.include_router(invoices.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(cars.router, prefix="/api")
app.include_router(entities.router)  # prefix=/api/entities on router
app.include_router(reports.router, prefix="/api")
app.include_router(whatsapp.router, prefix="/api")
app.include_router(repair_orders.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(cash_received.router, prefix="/api")
app.include_router(vendors.router, prefix="")  # routes already /api/...
app.include_router(hr.router, prefix="")  # /api/... and /iclock/...
app.include_router(settings_router.router, prefix="/api")
app.include_router(periods.router, prefix="/api")
app.include_router(labour_codes.router, prefix="/api")
app.include_router(job_cards.router, prefix="/api")
app.include_router(public_quotes.router, prefix="/api")
app.include_router(deposits.router, prefix="/api")
app.include_router(variations.router, prefix="/api")
app.include_router(qc.router, prefix="/api")
app.include_router(gate_passes.router, prefix="/api")
app.include_router(pipeline_status.router, prefix="/api")
app.include_router(money_facade.router, prefix="/api")
app.mount("/uploads", StaticFiles(directory=str(_UPLOAD_DIR)), name="uploads")


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        body = detail
    elif isinstance(detail, dict):
        body = {"error": detail.get("msg") or detail.get("message") or "Request failed", **detail}
    else:
        body = {"error": detail if isinstance(detail, str) else "Request failed"}
    return JSONResponse(body, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if not errors:
        return JSONResponse({"error": "No data provided"}, status_code=400)
    first = errors[0]
    loc = [part for part in first.get("loc", ()) if part != "body"]
    if not loc:
        return JSONResponse({"error": "No data provided"}, status_code=400)
    field = str(loc[-1])
    if first.get("type") == "missing":
        return JSONResponse({"error": f"{field} is required"}, status_code=400)
    return JSONResponse({"error": f"{field} is invalid"}, status_code=400)


@app.get("/api/health")
def health():
    return {"status": "ok"}
