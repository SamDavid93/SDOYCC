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
        from app.modules.crafting import seed_crafting
        seed_crafting(database)
        database.commit()
    import asyncio
    from app.modules.maintenance import maintenance_loop, maintain
    await asyncio.to_thread(maintain)
    worker_task = None
    app.state.duel_worker = None
    if settings.duel_worker_enabled:
        from app.modules.duel_worker import NativeAdapter, WorkerService
        adapter = await asyncio.to_thread(NativeAdapter)
        app.state.duel_worker = WorkerService(SessionLocal, adapter)
        await app.state.duel_worker.recover_orphans()
        worker_task = asyncio.create_task(app.state.duel_worker.watchdog())
    task = asyncio.create_task(maintenance_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        if worker_task:
            worker_task.cancel()
            try: await worker_task
            except asyncio.CancelledError: pass
            await app.state.duel_worker.close()


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
from app.modules.admin_products import router as admin_products_router
app.include_router(admin_products_router)

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

from app.modules.rare_pulls import router as rare_pulls_router, reveal_router
app.include_router(rare_pulls_router)
app.include_router(reveal_router)
from app.modules.stream_overlay import router as stream_overlay_router
app.include_router(stream_overlay_router)

from app.modules.decks import router as decks_router
app.include_router(decks_router)

from app.modules.duel_lobbies import router as duel_lobbies_router
app.include_router(duel_lobbies_router)

from app.modules.duel_worker import router as duel_worker_router
app.include_router(duel_worker_router)

from app.modules.duel_socket import router as duel_socket_router
app.include_router(duel_socket_router)

from app.modules.duel_operations import router as duel_operations_router
app.include_router(duel_operations_router)
from app.modules.duel_controls import router as duel_controls_router
app.include_router(duel_controls_router)

from app.modules.deck_templates import router as deck_templates_router
app.include_router(deck_templates_router)

from app.modules.duel_history import router as duel_history_router
app.include_router(duel_history_router)

from app.modules.crafting import router as crafting_router, admin_router as crafting_admin_router
app.include_router(crafting_router)
app.include_router(crafting_admin_router)
