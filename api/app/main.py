from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

import app.events  # noqa: F401  registers the audit/outbox flush hook
from app.db import engine
from app.routers import admin, auth, billing, branch, catalog, customers, estimates, files, repairs, workshop

app = FastAPI(title="GermanATO API", version="0.1.0")

for r in (auth.router, admin.router, branch.router, files.router, customers.router, catalog.router, workshop.router, estimates.router, repairs.router, billing.router):
    app.include_router(r)


# Database constraints are the last line of defence against dirty data; when
# one fires, say which rule was broken instead of returning a bare 500.
_CONSTRAINT_MESSAGES = {
    "users_username_key": "That username is taken",
    "users_email_key": "Another user already has that email",
    "roles_name_key": "A role with that name already exists",
    "branches_code_key": "Another branch already uses that code",
    "uq_cars_plate": "Another car already has this plate",
    "uq_cars_vin": "Another car already has this VIN",
    "uq_car_current_owner": "This car already has a current owner",
    "item_codes_branch_id_code_norm_key": "That barcode or part number already belongs to another item",
    "labour_codes_branch_id_code_key": "That labour code is already used",
    "uq_visit_open_car": "This car is already checked in",
}


@app.exception_handler(IntegrityError)
def integrity_error(_: Request, exc: IntegrityError):
    name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    return JSONResponse({"detail": _CONSTRAINT_MESSAGES.get(name, "That would create duplicate or invalid data")},
                        status_code=409)


@app.exception_handler(StaleDataError)
def stale_data(_: Request, __: StaleDataError):
    return JSONResponse({"detail": "Someone else changed this record. Reload and try again."}, status_code=409)


@app.get("/api/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"ok": True}
