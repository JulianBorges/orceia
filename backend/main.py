from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import os
from contextlib import asynccontextmanager

from core.config import settings
from core.db import init_db_pool, close_db_pool
from core.redis_client import init_redis, close_redis
from modules.orcamento import routes as orcamento_routes
from modules.sinapi import routes as sinapi_routes
from modules.auth import routes as auth_routes
from modules.eap import routes as eap_routes
from modules.auditoria import routes as auditoria_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Guard de deploy: semaforo asyncio nao e distribuido entre processos
    workers = int(os.environ.get("WEB_CONCURRENCY", 1))
    if workers > 1:
        raise RuntimeError(
            f"OrceIA detectou WEB_CONCURRENCY={workers}. "
            "Use WEB_CONCURRENCY=1 e escale via replicas de container (Cloud Run)."
        )
    # Setup antes de receber requisições
    await init_db_pool()
    await init_redis()
    yield
    # Cleanup na hora de desligar
    await close_db_pool()
    await close_redis()

app = FastAPI(title="OrceIA API", version="3.0.0", lifespan=lifespan)

# Setup CORS para permitir a comunicação com o Next.js
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Roteador de autenticação (valida tenants contra o banco)
app.include_router(auth_routes.router)

# Roteador de orçamento (motor principal + SSE)
app.include_router(orcamento_routes.router)

# Roteador de SINAPI (busca manual do usuário)
app.include_router(sinapi_routes.router)

# Roteador EAP (Estruturação de EAP por IA)
app.include_router(eap_routes.router)

# Roteador Auditoria (Pipeline Bidirecional de Memoriais Descritivos)
app.include_router(auditoria_routes.router)

@app.get("/")
async def root():
    return {"message": "OrceIA Backend API V3.0"}
