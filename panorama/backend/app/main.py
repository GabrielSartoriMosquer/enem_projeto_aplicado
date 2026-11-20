from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.services.data_engine import get_engine
from app.services.population import get_population

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Escolhe a fonte ao subir: com o data lake configurado, a gold é baixada (se mudou) antes de
    # a API aceitar requisições, em vez de travar a primeira consulta.
    get_engine(settings)
    get_population(settings)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API analítica do Panorama ENEM. Calcula percentis e estatísticas descritivas "
        "sempre dentro da mesma edição do exame."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
