"""Owner-only, audited product overrides, independent of catalogue imports."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import or_, select

from app.api import booster_payload
from app.core.permissions import admin_reader
from app.db.models import BoosterPack, User
from app.modules.admin import Database, Page, PageSize, paged
from app.modules.economy import finish, replay
from app.modules.workflow import AdminCommand, Auth, Key, action, administrator, audit

router = APIRouter(prefix='/api/admin/products', dependencies=[Depends(admin_reader)])


def owner(actor: User = Depends(admin_reader)):
    if actor.role != 'super_admin':
        raise HTTPException(403, 'Nur der Hauptadministrator darf Produktregeln verwalten.')
    return actor


def product(pack):
    data = booster_payload(pack)
    return {key: data[key] for key in ('id', 'name', 'product_type', 'cost', 'cards_per_pack', 'rare_guaranteed')} | {
        'price_override': pack.price_override, 'draw_count_override': pack.draw_count_override,
        'active': pack.active,
    }


@router.get('', dependencies=[Depends(owner)])
def products(database: Database, search: str = Query('', max_length=100),
             page: Page = 1, page_size: PageSize = 20):
    query = select(BoosterPack).order_by(BoosterPack.name, BoosterPack.id)
    if search.strip():
        query = query.where(or_(BoosterPack.name.icontains(search.strip(), autoescape=True),
                               BoosterPack.key.icontains(search.strip(), autoescape=True)))
    return paged(database, query, page, page_size, lambda row: product(row[0]))


class ProductCommand(AdminCommand):
    price_override: int | None = Field(None, ge=0, le=1000000, strict=True)
    draw_count_override: int | None = Field(None, ge=1, le=100, strict=True)
    expected_price_override: int | None = Field(..., ge=0, le=1000000, strict=True)
    expected_draw_count_override: int | None = Field(..., ge=1, le=100, strict=True)


@router.post('/{product_id}')
def update_product(product_id: int, payload: ProductCommand, database: Database,
                   authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload)
    code = f'product:{product_id}:' + action('settings', payload)
    previous = replay(database, actor, idempotency_key, code)
    if previous is not None:
        return previous
    pack = database.scalar(select(BoosterPack).where(BoosterPack.id == product_id).with_for_update())
    if pack is None:
        raise HTTPException(404, 'Produkt nicht gefunden.')
    if pack.product_type == 'structure_deck' and payload.draw_count_override is not None:
        raise HTTPException(409, 'Die Kartenanzahl eines Structure Decks ergibt sich aus seiner festen Deckliste.')
    if (pack.price_override, pack.draw_count_override) != (payload.expected_price_override, payload.expected_draw_count_override):
        raise HTTPException(409, 'Das Produkt wurde inzwischen geändert. Bitte neu laden.')
    before = product(pack)
    pack.price_override = payload.price_override
    pack.draw_count_override = payload.draw_count_override
    after = product(pack)
    audit_id = audit(database, actor, actor.id, 'product_settings', {
        'product_id': product_id, 'reason': payload.reason, 'before': before, 'after': after,
    })
    return finish(database, actor, idempotency_key, code, {'product': after, 'audit_id': audit_id})
