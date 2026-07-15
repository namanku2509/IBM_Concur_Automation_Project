"""
main.py
-------
FastAPI application factory for the SAP Concur Stub.

Responsibilities:
- Create the FastAPI application instance with full OpenAPI metadata.
- Register all domain routers under their correct path prefixes.
- Run the lifespan startup sequence:
    1. Create all database tables (idempotent).
    2. Run the seed script to populate reference data.
- Expose GET /health for liveness probes and smoke testing.

Architecture note:
    Route handlers are thin — they delegate immediately to service or
    repository functions. No business logic lives in this file.
"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import Base, engine


# ------------------------------------------------------------------ #
# Lifespan                                                             #
# ------------------------------------------------------------------ #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown lifecycle handler.

    On startup:
    - Import all model modules so SQLAlchemy's metadata registry is
      populated before create_all() runs.
    - Create all tables (no-op if they already exist).
    - Run seed.py to populate reference data if the DB is empty.

    On shutdown:
    - Nothing needed for SQLite / uvicorn local dev.
    """
    # --- Import all models so Base.metadata knows about every table ---
    # These imports MUST happen before create_all().
    import models.employee            # noqa: F401
    import models.travel_policy       # noqa: F401
    import models.trip                # noqa: F401
    import models.expense_report      # noqa: F401
    import models.expense             # noqa: F401
    import models.hotel_itemization   # noqa: F401
    import models.airfare_detail      # noqa: F401
    import models.taxi_detail         # noqa: F401
    import models.meal_detail         # noqa: F401
    import models.corporate_card_transaction  # noqa: F401
    import models.receipt             # noqa: F401
    import models.audit_log           # noqa: F401

    # --- Create all tables ---
    Base.metadata.create_all(bind=engine)

    # --- Seed reference data ---
    from seed import run_seed
    run_seed()

    yield
    # Shutdown — nothing to tear down for local SQLite dev.


# ------------------------------------------------------------------ #
# Application factory                                                  #
# ------------------------------------------------------------------ #

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=settings.app_description,
    lifespan=lifespan,
    redoc_url=None,
    openapi_tags=[
        {"name": "health",              "description": "Liveness probe"},
        {"name": "employees",           "description": "Employee profiles"},
        {"name": "travel-policies",     "description": "Travel policy rules"},
        {"name": "trips",               "description": "Business trip management"},
        {"name": "expense-reports",     "description": "Expense report lifecycle"},
        {"name": "expenses",            "description": "Bulk expense submission and validation pipeline"},
        {"name": "receipts",            "description": "Receipt metadata registration"},
        {"name": "card-transactions",   "description": "Corporate card transaction feed"},
        {"name": "admin",               "description": "Admin dashboard and test-harness endpoints"},
    ],
)

# ------------------------------------------------------------------ #
# CORS                                                                 #
# ------------------------------------------------------------------ #
_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ #
# Static files                                                         #
# ------------------------------------------------------------------ #

app.mount("/static", StaticFiles(directory="static"), name="static")


# ------------------------------------------------------------------ #
# Router registration                                                  #
# ------------------------------------------------------------------ #
# Routers are registered here after all models and schemas are loaded.
# Each router file is responsible for its own APIRouter instance.
#
# Concur-facing routes: /api/v4/...
# Admin / test-harness routes: /admin/...

def _register_routers() -> None:
    """
    Import and register all domain routers.
    Deferred import prevents circular imports at module load time.
    """
    from routers import (
        employees,
        travel_policies,
        trips,
        expense_reports,
        expenses,
        receipts,
        card_transactions,
        admin,
    )

    app.include_router(employees.router,         prefix="/api/v4")
    app.include_router(travel_policies.router,   prefix="/api/v4")
    app.include_router(trips.router,             prefix="/api/v4")
    app.include_router(expense_reports.router,   prefix="/api/v4")
    app.include_router(expenses.router,          prefix="/api/v4")
    app.include_router(receipts.router,          prefix="/api/v4")
    app.include_router(card_transactions.router, prefix="/api/v4")
    app.include_router(admin.router)  # /admin/* — no /api/v4 prefix


_register_routers()


# ------------------------------------------------------------------ #
# Health check                                                         #
# ------------------------------------------------------------------ #

@app.get(
    "/health",
    tags=["health"],
    summary="Liveness probe",
    response_description="Service is up and database is reachable",
)
def health_check():
    """
    Returns 200 OK if the service is running and the database file exists.
    Used by smoke tests and monitoring to confirm the stub is ready.
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "service": settings.app_title,
        "version": settings.app_version,
    }


from fastapi.responses import HTMLResponse, RedirectResponse

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/redoc", include_in_schema=False)
def redoc_local():
    """
    Serve ReDoc using a locally downloaded JS bundle (static/redoc.standalone.js).
    This bypasses the broken CDN URL (redoc@next returns 404) and works fully offline.
    """
    return HTMLResponse(f"""<!DOCTYPE html>
<html>
  <head>
    <title>{app.title} — ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body {{ margin: 0; padding: 0; }}</style>
  </head>
  <body>
    <redoc spec-url="/openapi.json"></redoc>
    <script src="/static/redoc.standalone.js"> </script>
  </body>
</html>""")