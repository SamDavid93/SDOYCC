"""Admin-only, inventory-neutral test duels using the regular native lifecycle."""
from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
from itertools import combinations, islice
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import (CardDetails, DuelCardRule, DuelLobby, DuelLobbySeat, DuelPreparation,
    DuelRuleProfile, DuelWorkerRun, DuelWorkerParticipant, DuelWorkerLease)
from app.modules.workflow import writer, audit


def require_admin(user):
    if user.role not in ('admin', 'super_admin'):
        raise HTTPException(403, 'Testduelle gegen die KI sind nur für Administratoren verfügbar.')


def begin(db, deck_id, _version, authorization, key, instance, check_snapshot, manifest=None):
    from app.modules.duel_admission import require_player, require_slot
    from app.modules.duel_lobbies import chosen_deck, cleanup_lobbies
    from app.modules.duel_rules import validate_deck
    from app.modules.economy import replay, finish
    from app.modules.duel_worker_state import authorize_run
    user = writer(db, authorization, key)
    require_admin(user)
    operation = 'duel:practice:' + deck_id
    previous = replay(db, user, key, operation)
    if previous is not None:
        authorize_run(db, previous['id'], authorization)
        return previous['id'], None
    require_player(db, user.id)
    require_slot(db)
    cleanup_lobbies(db)
    if db.get(DuelLobbySeat, user.id):
        raise HTTPException(409, 'Verlasse zuerst deine bestehende Lobby oder beende dein laufendes Duell.')
    deck = chosen_deck(db, user.id, deck_id)
    profile = db.get(DuelRuleProfile, deck.profile_id)
    check = validate_deck(db, user.id, json.loads(deck.entries_json), profile)
    if not check['ready']:
        raise HTTPException(409, 'Dein Deck benötigt gültige Regeln, verfügbare Karten und einen freigegebenen Regelstand.')
    sections = {section: [check['rules'][entry['card_id']]['passcode']
        for entry in json.loads(deck.entries_json) if entry['section'] == section
        for _ in range(entry['quantity'])] for section in ('main', 'extra', 'side')}
    # A deliberately simple deck avoids requiring an external AI engine or scripts.
    rows = db.execute(select(DuelCardRule, CardDetails).join(CardDetails, CardDetails.card_id == DuelCardRule.card_id).where(
        DuelCardRule.profile_id == profile.id, DuelCardRule.status == 'mapped', DuelCardRule.type_bits == 17,
        DuelCardRule.copy_limit > 0, CardDetails.level.between(1,4), CardDetails.atk.between(0,2500)
    ).order_by(CardDetails.atk.desc(), DuelCardRule.passcode)).all()
    bot, used = [], Counter()
    for rule, _details in rows:
        amount = min(rule.copy_limit - used[rule.identity], 40 - len(bot))
        if amount > 0:
            bot.extend([rule.passcode] * amount)
            used[rule.identity] += amount
        if len(bot) == 40: break
    if len(bot) != 40:
        raise HTTPException(409, 'Für diesen Regelstand sind noch nicht genügend einfache KI-Testkarten verfügbar.')
    now = datetime.utcnow()
    lobby_id, run_id, preparation_id = str(uuid4()), str(uuid4()), str(uuid4())
    snapshot = {'schema':1, 'mode':'single', 'practice':True, 'profile_id':profile.id,
        'sources':json.loads(profile.sources_json), 'players':[
            {'user_id':user.id, 'seat':0, 'sections':sections, 'entries':[]},
            {'user_id':None, 'seat':1, 'sections':{'main':bot,'extra':[],'side':[]}, 'entries':[]}]}
    check_snapshot(snapshot)
    encoded = json.dumps(snapshot,sort_keys=True,separators=(',',':'))
    db.add(DuelLobby(id=lobby_id,code=uuid4().hex[:8].upper(),host_id=user.id,profile_id=profile.id,
        state='starting',version=1,expires_at=now+timedelta(hours=1)))
    db.flush()
    db.add(DuelLobbySeat(user_id=user.id,lobby_id=lobby_id,seat=0,accepted=True,deck_id=deck.id,
        deck_version=deck.version,session_hash=user._authenticated_session))
    db.add(DuelPreparation(id=preparation_id,lobby_id=lobby_id,profile_id=profile.id,state='starting',
        snapshot_json=encoded,snapshot_hash=sha256(encoded.encode()).hexdigest(),expires_at=now+timedelta(minutes=2)))
    db.flush()
    db.add(DuelWorkerRun(id=run_id,preparation_id=preparation_id,lobby_id=lobby_id,owner_instance=instance,state='starting',
        participants_json=json.dumps([{'user_id':user.id,'seat':0,'session_hash':user._authenticated_session,
            'practice':True,'consent_expires_at':(now+timedelta(minutes=2)).isoformat()}])))
    db.flush()
    db.add(DuelWorkerParticipant(run_id=run_id,user_id=user.id,seat=0))
    if manifest is not None: db.add(DuelWorkerLease(run_id=run_id,manifest_json=json.dumps(manifest)))
    audit(db,user,user.id,'duel_practice_start',{'run_id':run_id,'deck_id':deck.id,'opponent':'basic'})
    finish(db,user,key,operation,{'id':run_id})
    return run_id,snapshot


def answer(projection, acted):
    """Use only the bot's filtered view; every candidate passes native prompt validation."""
    prompt = projection.prompt
    owner, prompt_id = prompt['owner'], prompt['id']
    public = projection.view(owner)['prompt']
    choices = public['choices']
    candidates = []
    if prompt.get('counter'):
        remaining = prompt['counter_total']; counts=[]
        for limit in prompt['counter_limits']:
            amount=min(limit,remaining);counts.append(amount);remaining-=amount
        candidates=[(counts,False)]
    elif prompt.get('select'):
        minimum,maximum=prompt['minimum'],min(prompt['maximum'],len(choices))
        if prompt.get('_response_kind') == 'sort':
            candidates=[(list(range(len(choices))),False)]
        else:
            candidates=((list(items),False) for size in range(minimum,maximum+1)
                for items in combinations(range(len(choices)),size))
    else:
        def priority(index):
            choice=choices[index];action=choice.get('action');label=choice['label']
            location=choice.get('location') or {}
            identity=(action,location.get('zone'),location.get('sequence'))
            if identity in acted and action: return (90,index)
            attack=(choice.get('card') or {}).get('atk') or 0
            if action=='summon': return (0,-attack)
            if action=='attack': return (1,-attack)
            if label=='Kampfphase': return (3,index)
            if label=='Zug beenden': return (4,index)
            if label in ('Nicht anketten','Nein'): return (0,index)
            if action in ('activate','position'): return (95,index)
            return (2,attack)
        indexes=sorted(range(len(choices)),key=priority)
        candidates=[([index],False) for index in indexes]
        if prompt.get('cancel'): candidates.insert(0,([],True))
    for selected,cancel in islice(candidates,10000):
        try: response=projection.respond(owner,prompt_id,selected,cancel)
        except (ValueError,TypeError): continue
        if not prompt.get('select') and not prompt.get('counter') and selected:
            choice=choices[selected[0]];location=choice.get('location') or {}
            if choice.get('action'): acted.add((choice['action'],location.get('zone'),location.get('sequence')))
        return response
    if prompt.get('cancel'): return projection.respond(owner,prompt_id,[],True)
    raise ValueError('No supported legal test-bot response')
