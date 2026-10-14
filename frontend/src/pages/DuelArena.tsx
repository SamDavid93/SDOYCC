import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import type { EngineCard, Side } from './DuelWorkerTable'
import type { DuelLocation, WorkerPrompt } from './DuelDecisions'
import cardBack from '../assets/card-back.jpg'
import { DuelPhaseControl } from './DuelPhaseControl'
import { effectAvailableAt } from './duelFeedback'
import { DuelPlayerHUD } from './DuelPlayerHUD'
import { DuelActionLabel } from './DuelActionLabel'
import { DuelPile } from './DuelPile'

type Props = { sides: Side[]; seat: number; card: (value: EngineCard | null, key: string, covered?: boolean, location?: DuelLocation) => ReactNode;
  activeLocation: DuelLocation | null; chooseLocation: (location: DuelLocation, complete?: boolean) => void; children?: ReactNode;
  confirmSelection: () => void; selectionValid: boolean; selectionLabel: string;
  prompt?: WorkerPrompt | null; disabled: boolean; zoneSelection: number[]; chooseZone: (index: number) => void;
  chooseAction: (index: number, target?: DuelLocation) => void; phase: number; turn: number; turnNumber: number }
export function DuelArena({ sides, seat, card, prompt, disabled, zoneSelection, chooseZone, chooseAction, phase, turn, turnNumber, activeLocation, chooseLocation, children, confirmSelection, selectionValid, selectionLabel }: Props) {
  const [dragging, setDragging] = useState<number | null>(null)
  const [drop, setDrop] = useState<{ index: number; target: DuelLocation } | null>(null)
  useEffect(() => { setDrop(null); setDragging(null) }, [prompt?.id])
  const actions = (index: number, zone?: number) => prompt?.choices.map((choice, choiceIndex) => ({ ...choice, choiceIndex })).filter(choice =>
    choice.location?.owner === seat && choice.location.zone === 2 && choice.location.sequence === index &&
    (zone === 8 ? choice.action === 'set_spell' : zone === 4 ? ['summon', 'special_summon', 'set_monster'].includes(choice.action || '') : ['summon', 'special_summon', 'set_monster', 'set_spell', 'activate'].includes(choice.action || ''))) || []
  const optionsAt = (owner: number, zone: number, sequence: number) => prompt?.choices.map((choice, index) => ({ ...choice, index })).filter(choice => choice.location?.owner === owner && choice.location.zone === zone && choice.location.sequence === sequence) || []
  const activeAt = (owner: number, zone: number, sequence: number) => activeLocation?.owner === owner && (activeLocation.zone & 127) === zone && activeLocation.sequence === sequence
  function slot(owner: number, zone: number, sequence: number, label: string, physicalKey = `${owner}:${zone}:${sequence}`) {
    const entry = sides[owner].field.find(value => value.zone === zone && value.sequence === sequence)
    const options = !disabled && prompt?.kind !== 'zones' ? optionsAt(owner, zone, sequence) : []
    const attackReady = options.some(choice => choice.action === 'attack')
    const effectReady = !disabled && effectAvailableAt(prompt, {owner, zone, sequence})
    const selected = options.some(choice => zoneSelection.includes(choice.index))
    const zoneChoice = prompt?.kind === 'zones' ? prompt.choices.findIndex(choice => choice.location?.owner === owner && choice.location.zone === zone && choice.location.sequence === sequence) ?? -1 : -1
    const canDrop = !disabled && owner === seat && !entry && (zone === 4 || zone === 8) && dragging !== null && actions(dragging, zone).length > 0
    return <div key={physicalKey} className={'arena-slot' + (zone === 4 && entry && (entry.position & 12) ? ' defense-position' : '') + (entry?.disabled ? ' zone-disabled' : '') + (zoneChoice >= 0 && !disabled ? ' zone-selectable' : '') + (zoneSelection.includes(zoneChoice) || selected ? ' zone-selected' : '') + (canDrop ? ' zone-droppable' : '') + (options.length ? ' action-available' : '') + (attackReady ? ' attack-ready' : '') + (effectReady ? ' effect-available' : '') + (activeAt(owner,zone,sequence) ? ' action-focused' : '')}
      onDragOver={event => { if (canDrop) { event.preventDefault(); event.dataTransfer.dropEffect = 'move' } }}
      onDrop={event => { event.preventDefault(); if (canDrop && dragging !== null) setDrop({ index: dragging, target: { owner, zone, sequence } }); setDragging(null) }}
      data-duel-owner={owner} data-duel-zone={zone} data-duel-sequence={sequence} aria-label={`${owner === seat ? 'Deine' : 'Gegnerische'} ${label}`}>
      {zoneChoice >= 0 && <button className="arena-zone-choice" aria-label={`${label} auswählen`} disabled={disabled} aria-pressed={zoneSelection.includes(zoneChoice)} onClick={() => chooseZone(zoneChoice)} />}
      {options.length > 0 && <button className="arena-action-hotspot" aria-label={`${label} ${prompt?.select ? 'auswählen' : 'Aktionen'}`} aria-pressed={selected} onClick={event => { if(event.detail < 2) chooseLocation({owner,zone,sequence}) }} onDoubleClick={() => { if(prompt?.select) chooseLocation({owner,zone,sequence},true) }} />}
      {options.length > 0 && <span className="arena-action-badge" aria-hidden="true">{attackReady ? '⚔' : prompt?.select ? selected ? '✓' : '◎' : '✦'}</span>}
      {activeAt(owner,zone,sequence) && options.length > 0 && !prompt?.select && !prompt?.counter && <div className="arena-card-actions" aria-label="Kartenaktionen">{options.map(choice => <button key={choice.index} className="duel-action-button" data-duel-action={choice.action} disabled={disabled} onClick={() => chooseAction(choice.index)}><DuelActionLabel action={choice.action} label={choice.label} /></button>)}</div>}
      {activeAt(owner,zone,sequence) && selected && prompt?.select && <div className="arena-card-actions" aria-label="Auswahl auf dem Feld"><button disabled={disabled || !selectionValid} onClick={confirmSelection}>{selectionLabel}</button><button disabled={disabled} onClick={()=>chooseLocation({owner,zone,sequence})}>Abwählen</button></div>}
      <span className="arena-zone-label">{label}</span>
      {entry ? card(entry.card, `${owner}:${zone}:${sequence}`, Boolean(entry.position & 10), {owner,zone,sequence}) : <span className="arena-empty-mark">◇</span>}
      {entry?.card && <div className="arena-card-stats">{zone === 4 && entry.card.atk !== undefined && <strong>{entry.card.atk} / {entry.card.defense ?? '—'}</strong>}
        {entry.materials?.length ? <details><summary>{entry.materials.length} Materialien</summary>{entry.materials.map((value, index) => card(value, `material:${index}`))}</details> : null}
        {entry.counters?.map(value => <small key={value}>Zähler {value & 65535}: {value >>> 16}</small>)}
        {entry.equip?.zone ? <small>Ausrüstung → {entry.equip.owner === seat ? 'deine' : 'gegnerische'} Zone {entry.equip.sequence + 1}</small> : null}
        {entry.targets?.map((target, index) => <small key={index}>Ziel → {target.owner === seat ? 'deine' : 'gegnerische'} Zone {target.sequence + 1}</small>)}
      </div>}
      {entry?.disabled && <span>Gesperrt</span>}
    </div>
  }
  function pile(owner: number, zone: number, label: string, values: (EngineCard | null)[]) {
    return <DuelPile owner={owner} zone={zone} label={label} values={values} prompt={prompt} disabled={disabled} activeLocation={activeLocation} card={card} chooseAction={chooseAction} />
  }
  function deck(owner: number) {
    const available = !disabled && prompt?.choices.some(choice => choice.location?.owner === owner && choice.location.zone === 1)
    const effectReady = available && prompt?.choices.some(choice => choice.location?.owner === owner && choice.location.zone === 1 && effectAvailableAt(prompt, choice.location))
    return <button className={'arena-pile arena-deck' + (available ? ' action-available' : '') + (effectReady ? ' effect-available' : '')} disabled={!available} onClick={()=>{ const choice=prompt?.choices.find(choice=>choice.location?.owner===owner && choice.location.zone===1); if(choice?.location) chooseLocation(choice.location) }} data-duel-owner={owner} data-duel-zone={1} aria-label="Deckaktionen">{sides[owner].deck > 0 && <img src={cardBack} alt="Deckrückseite" />}<span>Deck</span>{effectReady && <span className="arena-effect-label">✦ Effekt verfügbar</span>}<strong>{sides[owner].deck}</strong></button>
  }
  return <div className={'duel-arena ' + (turn === seat ? 'is-own-turn' : 'is-opponent-turn')} aria-label="Duellarena">
    {[1 - seat, seat].map(owner => <article className={'duel-player-field arena-player ' + (owner === seat ? 'arena-own' : 'arena-opponent')} key={owner}>
      <DuelPlayerHUD owner={owner} own={owner === seat} lp={sides[owner].lp} active={turn === owner} hand={sides[owner].hand.length} />
      <div className="duel-hand arena-hand" style={{'--hand-count':Math.max(1,sides[owner].hand.length)} as CSSProperties} data-duel-owner={owner} data-duel-zone={2}>{sides[owner].hand.map((value, index) => {
        const options = owner === seat && !disabled ? actions(index, drop?.index === index ? drop.target.zone : undefined) : []
        const handChoices = !disabled ? optionsAt(owner,2,index) : []
        return <div className={'arena-hand-card' + (drop?.index === index || activeAt(owner,2,index) ? ' placement-open' : '') + (handChoices.length ? ' action-available' : '') + (handChoices.some(choice => zoneSelection.includes(choice.index)) ? ' zone-selected' : '')} key={index} draggable={options.some(choice => choice.action !== 'activate')}
          onDragStart={event => { setDragging(index); setDrop(null); event.dataTransfer.setData('text/plain', String(index)); event.dataTransfer.effectAllowed = 'move' }} onDragEnd={() => setDragging(null)}>
          {card(value, `hand:${index}`, false, {owner,zone:2,sequence:index})}
          {activeAt(owner,2,index) && prompt?.select && handChoices.some(choice=>zoneSelection.includes(choice.index)) && <div className="arena-hand-actions" aria-label="Auswahl auf der Hand"><button disabled={disabled || !selectionValid} onClick={confirmSelection}>{selectionLabel}</button><button disabled={disabled} onClick={()=>chooseLocation({owner,zone:2,sequence:index})}>Abwählen</button></div>}
          {options.length > 0 && <div className="arena-hand-actions" aria-label="Kartenaktionen">{options.map(option => <button key={option.choiceIndex} className="duel-action-button" data-duel-action={option.action} disabled={disabled} onClick={() => { chooseAction(option.choiceIndex, drop?.index === index ? drop.target : undefined); setDrop(null) }}><DuelActionLabel action={option.action} label={option.action === 'set_spell' || option.action === 'set_monster' ? 'Setzen' : option.action === 'activate' ? 'Aktivieren' : option.action === 'special_summon' ? 'Spezialbeschwören' : 'Beschwören'} /></button>)}{drop?.index === index && <button onClick={() => setDrop(null)}>Abbrechen</button>}</div>}
        </div>
      })}</div>
      <div className="arena-layout">
        <div className="arena-flank">{slot(owner, 8, 5, 'Spielfeldzone')}{pile(owner, 64, 'Extra-Deck', sides[owner].extra || [])}</div>
        <div className="arena-main-zones">
          <div className="arena-monster-row">{Array.from({ length: 5 }, (_, index) => slot(owner, 4, owner === seat ? index : 4 - index, `Monsterzone ${(owner === seat ? index : 4 - index) + 1}`))}</div>
          <div className="arena-spell-row">{Array.from({ length: 5 }, (_, index) => slot(owner, 8, owner === seat ? index : 4 - index, `${index === 0 || index === 4 ? 'Zauber / Pendel' : 'Zauber / Falle'} ${(owner === seat ? index : 4 - index) + 1}`))}</div>
          {sides[owner].field.some(value => value.zone === 8 && value.sequence >= 6) && <div className="arena-legacy-pendulum">{slot(owner, 8, 6, 'Pendel links')}{slot(owner, 8, 7, 'Pendel rechts')}</div>}
        </div>
        <div className="arena-flank">{deck(owner)}{pile(owner, 16, 'Friedhof', sides[owner].grave)}{pile(owner, 32, 'Verbannt', sides[owner].removed || [])}</div>
      </div>
    </article>)}
    <div className="arena-extra-row" aria-label="Extra-Monsterzonen">{[0, 1].map(index => {
      // These two physical zones keep their identity when the controller changes.
      const ownSequence = 5 + index, otherSequence = 6 - index
      const ownAvailable = prompt?.choices.some(choice => choice.location?.owner === seat && choice.location.zone === 4 && choice.location.sequence === ownSequence)
      const ownOccupied = sides[seat].field.some(value => value.zone === 4 && value.sequence === ownSequence)
      const otherOccupied = sides[1 - seat].field.some(value => value.zone === 4 && value.sequence === otherSequence)
      const owner = ownOccupied ? seat : otherOccupied ? 1 - seat : ownAvailable ? seat : 1 - seat
      return slot(owner, 4, owner === seat ? ownSequence : otherSequence, `Extra-Monsterzone ${index + 1}`, `extra:${index}`)
    })}<DuelPhaseControl phase={phase} turnNumber={turnNumber} active={turn === seat} disabled={disabled} prompt={prompt} choose={chooseAction} /></div>
    {children}
  </div>
}
