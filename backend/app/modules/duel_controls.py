"""Versioned, audited rule approvals and time-limited duel-only restrictions."""
from datetime import date, datetime, timedelta
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select
from app.core.permissions import admin_reader
from app.db.models import DuelRuleProfile, DuelProfileReview, DuelRestriction, User
from app.modules.admin import Database
from app.modules.duel_rules import profile_payload
from app.modules.economy import replay, finish
from app.modules.workflow import AdminCommand, Auth, Key, action, administrator, audit

router = APIRouter(prefix='/api/admin/duels', dependencies=[Depends(admin_reader)])


class ProfileCommand(AdminCommand):
    version: int = Field(ge=1, strict=True)
    engine_approved: bool = Field(strict=True)
    region_approved: bool = Field(strict=True)
    evidence: str = Field(min_length=10, max_length=2000)


class RestrictionCommand(AdminCommand):
    version: int = Field(ge=1, strict=True)
    hours: int = Field(ge=0, le=8760, strict=True)


def official_reference(profile):
    try:
        sources = json.loads(profile.sources_json)
        effective = date.fromisoformat(sources['regional_effective'])
        digest = sources['regional_list_sha256']
        return profile.region == 'TCG-EU' and effective <= datetime.utcnow().date() and bool(re.fullmatch('[0-9a-f]{64}', digest))
    except (ValueError, TypeError, KeyError):
        return False


@router.get('/rule-profiles')
def profiles(request: Request, database: Database):
    runtime = getattr(request.app.state, 'duel_worker', None)
    rows = database.scalars(select(DuelRuleProfile).order_by(DuelRuleProfile.created_at.desc()).limit(100)).all()
    result = []
    for profile in rows:
        review = database.get(DuelProfileReview, profile.id)
        compatible = False
        if runtime:
            try:
                runtime.adapter.check({'sources': json.loads(profile.sources_json), 'players': []})
                compatible = True
            except (HTTPException, ValueError, TypeError, KeyError):
                pass
        result.append({**profile_payload(profile), 'version': review.version if review else 1,
            'evidence': review.evidence if review else '', 'worker_compatible': compatible,
            'official_regional_reference': official_reference(profile)})
    return {'items': result}


@router.post('/rule-profiles/{profile_id}')
def review_profile(profile_id: str, body: ProfileCommand, request: Request, database: Database,
                   authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, body)
    operation = action('duel_profile:' + profile_id, body)
    previous = replay(database, actor, idempotency_key, operation)
    if previous is not None: return previous
    profile = database.get(DuelRuleProfile, profile_id)
    if not profile: raise HTTPException(404, 'Regelprofil nicht gefunden.')
    review = database.get(DuelProfileReview, profile_id)
    if body.version != (review.version if review else 1): raise HTTPException(409, 'Regelfreigabe wurde verändert. Bitte aktualisieren.')
    if body.region_approved and not profile.region_approved and not official_reference(profile):
        raise HTTPException(409, 'Regionsfreigabe benötigt einen eindeutig zugeordneten offiziellen EU-Listenimport mit gültigem Datum.')
    if body.engine_approved and not profile.engine_approved:
        runtime = getattr(request.app.state, 'duel_worker', None)
        if not runtime: raise HTTPException(503, 'Der installierte Worker ist für den Paketabgleich nicht verfügbar.')
        runtime.adapter.check({'sources': json.loads(profile.sources_json), 'players': []})
    before = {'engine_approved': profile.engine_approved, 'region_approved': profile.region_approved}
    if review is None:
        review = DuelProfileReview(profile_id=profile_id, version=1); database.add(review)
    profile.engine_approved = body.engine_approved; profile.region_approved = body.region_approved
    review.version += 1; review.evidence = body.evidence
    audit(database, actor, actor.id, 'duel_profile_review', {'profile_id': profile_id, 'before': before,
        'engine_approved': body.engine_approved, 'region_approved': body.region_approved,
        'evidence': body.evidence, 'reason': body.reason, 'version': review.version})
    database.flush()
    return finish(database, actor, idempotency_key, operation, {**profile_payload(profile), 'version': review.version})


def restriction_payload(database, user_id):
    user = database.get(User, user_id)
    if not user: raise HTTPException(404, 'Konto nicht gefunden.')
    row = database.get(DuelRestriction, user_id)
    return {'user_id': user.id, 'username': user.username, 'display_name': user.display_name,
        'active': bool(row and row.until > datetime.utcnow()),
        'until': row.until.isoformat() + 'Z' if row else None,
        'reason': row.reason if row else '', 'version': row.version if row else 1}


@router.get('/restrictions/{user_id}')
def restriction(user_id: int, database: Database):
    return restriction_payload(database, user_id)


@router.post('/restrictions/{user_id}')
def restrict(user_id: int, body: RestrictionCommand, database: Database,
             authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, body, ids=(user_id,))
    operation = action('duel_restriction:' + str(user_id), body)
    previous = replay(database, actor, idempotency_key, operation)
    if previous is not None: return previous
    current = restriction_payload(database, user_id)
    if body.version != current['version']: raise HTTPException(409, 'Duellsperre wurde verändert. Bitte aktualisieren.')
    row = database.get(DuelRestriction, user_id)
    if row is None:
        row = DuelRestriction(user_id=user_id, version=1); database.add(row)
    row.until = datetime.utcnow() + timedelta(hours=body.hours); row.reason = body.reason; row.version += 1
    audit(database, actor, user_id, 'duel_restriction',
        {'hours': body.hours, 'until': row.until.isoformat() + 'Z', 'reason': body.reason, 'version': row.version})
    database.flush()
    return finish(database, actor, idempotency_key, operation, restriction_payload(database, user_id))
