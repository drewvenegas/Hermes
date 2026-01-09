"""
Hermes API Application

FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app

from hermes.api import analytics, benchmark_suites, benchmarks, collaboration, health, prompts, search, templates, versions
from hermes.auth.oidc import router as auth_router
from hermes.services.nursery_sync import sync_router as nursery_router
from hermes.config import get_settings
from hermes.services.database import init_db, close_db

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Prometheus metrics
REQUEST_COUNT = Counter(
    "hermes_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "hermes_request_latency_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Hermes API", version=settings.app_version)
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Hermes API")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI app
app = FastAPI(
    title="Hermes API",
    description="Bravo Zero Prompt Engineering Platform",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging and metrics middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests and record metrics."""
    import time
    
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate latency
    latency = time.time() - start_time
    
    # Record metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(latency)
    
    # Log request
    logger.info(
        "Request processed",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        latency_ms=round(latency * 1000, 2),
    )
    
    return response


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Include routers
app.include_router(auth_router, tags=["Authentication"])
app.include_router(health.router, tags=["Health"])
app.include_router(prompts.router, prefix="/api/v1", tags=["Prompts"])
app.include_router(versions.router, prefix="/api/v1", tags=["Versions"])
app.include_router(benchmarks.router, prefix="/api/v1", tags=["Benchmarks"])
app.include_router(search.router, prefix="/api/v1", tags=["Search"])
app.include_router(benchmark_suites.router, prefix="/api/v1", tags=["Benchmark Suites"])
app.include_router(templates.router, prefix="/api/v1", tags=["Templates"])
app.include_router(collaboration.router, prefix="/api/v1", tags=["Collaboration"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])
app.include_router(nursery_router, tags=["Nursery Sync"])

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


def cli():
    """CLI entry point."""
    import uvicorn
    
    logging.basicConfig(level=getattr(logging, settings.log_level))
    
    uvicorn.run(
        "hermes.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
    )


if __name__ == "__main__":
    cli()
