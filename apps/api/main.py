from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.database import Base, engine
from apps.api.routers import graph, health, ingestion, resources
from apps.api.security import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup for development baseline
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="OpenRobo API",
    description="Open-Source Global Robotics Commons API & Metadata Registry",
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    lifespan=lifespan
)

# Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured Error Handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred processing your request.",
            "path": request.url.path
        }
    )

# Routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(resources.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(ingestion.router, prefix="/api/v1")

@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "OpenRobo API Service",
        "version": "0.1.0",
        "docs": "/api/v1/docs",
        "health": "/api/v1/health"
    }
