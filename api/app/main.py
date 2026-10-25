from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import Base, engine
from app.routers import auth as auth_router
from app.routers import (
    cars,
    cash_received,
    expenses,
    hr,
    inventory,
    invoices,
    periods,
    repair_orders,
    reports,
    settings as settings_router,
    vendors,
    whatsapp,
)

import app.models  # noqa: F401  (register tables on Base)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="GermanATO API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Match backend/app.py blueprint prefixes
app.include_router(auth_router.router)  # prefix=/api/auth on router
app.include_router(invoices.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(cars.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(whatsapp.router, prefix="/api")
app.include_router(repair_orders.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(cash_received.router, prefix="/api")
app.include_router(vendors.router, prefix="")  # routes already /api/...
app.include_router(hr.router, prefix="")  # /api/... and /iclock/...
app.include_router(settings_router.router, prefix="/api")
app.include_router(periods.router, prefix="/api")


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        body = detail
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
