import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.routers import (
    accounts, analytics, auth, bizums, categories, dashboard,
    export, imports, insights, recurring, transactions,
)
from app.routers.auth import limiter

settings = get_settings()

# Logging estructurado. Nunca se registran descripciones completas, importes,
# números de cuenta ni destinatarios (sección 57).
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("finapp")

app = FastAPI(title="Finanzas Personales API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "environment": settings.environment}


app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(imports.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(bizums.router)
app.include_router(insights.router)
app.include_router(recurring.router)
app.include_router(export.router)
app.include_router(categories.router)
