from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes.crawl import router as crawl_router
from .api.routes.daily_summaries import router as daily_summaries_router
from .api.routes.delivery_logs import router as delivery_logs_router
from .api.routes.health import router as health_router
from .api.routes.issues import router as issues_router
from .api.routes.runtime_profile import router as runtime_profile_router
from .config import settings
from .database import init_db
from .services.runtime.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(runtime_profile_router)
app.include_router(crawl_router)
app.include_router(issues_router)
app.include_router(delivery_logs_router)
app.include_router(daily_summaries_router)
