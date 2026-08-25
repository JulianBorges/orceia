from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.config import settings
from core.db import init_db_pool, close_db_pool
from core.redis_client import init_redis, close_redis
from modules.orcamento import routes as orcamento_routes
from modules.sinapi import routes as sinapi_routes
from modules.auth import routes as auth_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
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

@app.get("/")
async def root():
    return {"message": "OrceIA Backend API V3.0"}
