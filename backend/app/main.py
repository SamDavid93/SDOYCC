from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.modules.german_images import router as images_router

from app.core.config import settings
from app.api import router
from app.db.seed import seed_database
from app.db.session import SessionLocal, migrate_local_schema
from app.modules.accounts import router as accounts_router
from app.modules.streamerbot import router as streamerbot_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate_local_schema()
    if settings.demo_enabled:
        with SessionLocal() as database:
            seed_database(database)
    from app.modules.card_data.structure_decks import import_structure_decks
    with SessionLocal() as database:
        import_structure_decks(database)
        from app.modules.inventory import migrate_inventory
        migrate_inventory(database)
        database.commit()
    import asyncio
    from app.modules.maintenance import maintenance_loop, maintain
    await asyncio.to_thread(maintain)
    task = asyncio.create_task(maintenance_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="SDOYCC – SamDavidOfficial's Yu-Gi-Oh Card Collector API", version="0.2.0", lifespan=lifespan)


@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    if "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router)
app.include_router(accounts_router)
app.include_router(streamerbot_router)

app.include_router(images_router)
app.add_middleware(GZipMiddleware, minimum_size=1000)

from app.modules.collection import router as collection_router
app.include_router(collection_router)

from app.modules.admin import router as admin_router
app.include_router(admin_router)

from app.modules.admin_actions import router as admin_actions_router
app.include_router(admin_actions_router)

from app.modules.inventory_api import router as inventory_router
app.include_router(inventory_router)

from app.modules.grants import router as grants_router
from app.modules.notifications import router as notifications_router
app.include_router(grants_router)
app.include_router(notifications_router)

from app.modules.admin_extended import router as advanced_router, art_router
from app.modules.trading import router as trading_router
from app.modules.seasons import router as seasons_router, admin_router as season_admin_router
app.include_router(advanced_router)
app.include_router(art_router)
app.include_router(trading_router)
app.include_router(seasons_router)
app.include_router(season_admin_router)

from app.modules.rare_pulls import router as rare_pulls_router
app.include_router(rare_pulls_router)
