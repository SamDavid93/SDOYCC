import { useEffect, useState, type ReactNode } from 'react'
import type { EngineCard, Side } from './DuelWorkerTable'
import type { DuelLocation, WorkerPrompt } from './DuelDecisions'
import cardBack from '../assets/card-back.jpg'

type Props = { sides: Side[]; seat: number; card: (value: EngineCard | null, key: string, covered?: boolean) => ReactNode;
  prompt?: WorkerPrompt | null; disabled: boolean; zoneSelection: number[]; chooseZone: (index: number) => void;
  chooseAction: (index: number, target?: DuelLocation) => void }
export function DuelArena({ sides, seat, card, prompt, disabled, zoneSelection, chooseZone, chooseAction }: Props) {
  const [dragging, setDragging] = useState<number | null>(null)
  const [drop, setDrop] = useState<{ index: number; target: DuelLocation } | null>(null)
  useEffect(() => { setDrop(null); setDragging(null) }, [prompt?.id])
  const actions = (index: number, zone?: number) => prompt?.choices.map((choice, choiceIndex) => ({ ...choice, choiceIndex })).filter(choice =>
    choice.location?.owner === seat && choice.location.zone === 2 && choice.location.sequence === index &&
    (zone === 8 ? choice.action === 'set_spell' : zone === 4 ? ['summon', 'special_summon', 'set_monster'].includes(choice.action || '') : ['summon', 'special_summon', 'set_monster', 'set_spell'].includes(choice.action || ''))) || []
  function slot(owner: number, zone: number, sequence: number, label: string) {
    const entry = sides[owner].field.find(value => value.zone === zone && value.sequence === sequence)
    const zoneChoice = prompt?.kind === 'zones' ? prompt.choices.findIndex(choice => choice.location?.owner === owner && choice.location.zone === zone && choice.location.sequence === sequence) ?? -1 : -1
    const canDrop = !disabled && owner === seat && !entry && (zone === 4 || zone === 8) && dragging !== null && actions(dragging, zone).length > 0
    return <div key={`${zone}:${sequence}`} className={'arena-slot' + (zone === 4 && entry && (entry.position & 12) ? ' defense-position' : '') + (entry?.disabled ? ' zone-disabled' : '') + (zoneChoice >= 0 && !disabled ? ' zone-selectable' : '') + (zoneSelection.includes(zoneChoice) ? ' zone-selected' : '') + (canDrop ? ' zone-droppable' : '')}
      onDragOver={event => { if (canDrop) { event.preventDefault(); event.dataTransfer.dropEffect = 'move' } }}
      onDrop={event => { event.preventDefault(); if (canDrop && dragging !== null) setDrop({ index: dragging, target: { owner, zone, sequence } }); setDragging(null) }}
      data-duel-owner={owner} data-duel-zone={zone} data-duel-sequence={sequence} aria-label={`${owner === seat ? 'Deine' : 'Gegnerische'} ${label}`}>
      {zoneChoice >= 0 && <button className="arena-zone-choice" aria-label={`${label} auswählen`} disabled={disabled} aria-pressed={zoneSelection.includes(zoneChoice)} onClick={() => chooseZone(zoneChoice)} />}
      <span className="arena-zone-label">{label}</span>
      {entry ? card(entry.card, `${owner}:${zone}:${sequence}`, Boolean(entry.position & 10)) : <span className="arena-empty-mark">◇</span>}
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
    return <details className="arena-pile" data-duel-owner={owner} data-duel-zone={zone}><summary>{label}<strong>{values.length}</strong></summary>
      <div className="arena-pile-content">{values.map((value, index) => card(value, `${zone}:${index}`))}{!values.length && <small>Leer</small>}</div></details>
  }
  return <div className="duel-arena" aria-label="Duellarena">
    {[1 - seat, seat].map(owner => <article className={'duel-player-field arena-player ' + (owner === seat ? 'arena-own' : 'arena-opponent')} key={owner}>
      <header><h2>{owner === seat ? 'Dein Spielfeld' : 'Gegnerisches Spielfeld'}</h2><strong className="duel-life" key={sides[owner].lp}>{sides[owner].lp.toLocaleString('de-DE')} LP</strong></header>
      <div className="duel-hand arena-hand" data-duel-owner={owner} data-duel-zone={2}>{sides[owner].hand.map((value, index) => {
        const options = owner === seat && !disabled ? actions(index, drop?.index === index ? drop.target.zone : undefined) : []
        return <div className={'arena-hand-card' + (drop?.index === index ? ' placement-open' : '')} key={index} draggable={options.length > 0}
          onDragStart={event => { setDragging(index); setDrop(null); event.dataTransfer.setData('text/plain', String(index)); event.dataTransfer.effectAllowed = 'move' }} onDragEnd={() => setDragging(null)}>
          {card(value, `hand:${index}`)}
          {options.length > 0 && <div className="arena-hand-actions" aria-label="Kartenaktionen">{options.map(option => <button key={option.choiceIndex} disabled={disabled} onClick={() => { chooseAction(option.choiceIndex, drop?.index === index ? drop.target : undefined); setDrop(null) }}>{option.action === 'set_spell' || option.action === 'set_monster' ? 'Setzen' : option.action === 'special_summon' ? 'Spezialbeschwören' : 'Beschwören'}</button>)}{drop?.index === index && <button onClick={() => setDrop(null)}>Abbrechen</button>}</div>}
        </div>
      })}</div>
      <div className="arena-layout">
        <div className="arena-flank">{slot(owner, 8, 5, 'Spielfeldzone')}{pile(owner, 64, 'Extra-Deck', sides[owner].extra || [])}</div>
        <div className="arena-main-zones">
          <div className="arena-monster-row">{Array.from({ length: 5 }, (_, index) => slot(owner, 4, owner === seat ? index : 4 - index, `Monsterzone ${(owner === seat ? index : 4 - index) + 1}`))}</div>
          <div className="arena-spell-row">{Array.from({ length: 5 }, (_, index) => slot(owner, 8, owner === seat ? index : 4 - index, `${index === 0 || index === 4 ? 'Zauber / Pendel' : 'Zauber / Falle'} ${(owner === seat ? index : 4 - index) + 1}`))}</div>
          {sides[owner].field.some(value => value.zone === 8 && value.sequence >= 6) && <div className="arena-legacy-pendulum">{slot(owner, 8, 6, 'Pendel links')}{slot(owner, 8, 7, 'Pendel rechts')}</div>}
        </div>
        <div className="arena-flank"><div className="arena-pile arena-deck" data-duel-owner={owner} data-duel-zone={1}>{sides[owner].deck > 0 && <img src={cardBack} alt="Deckrückseite" />}<span>Deck</span><strong>{sides[owner].deck}</strong></div>{pile(owner, 16, 'Friedhof', sides[owner].grave)}{pile(owner, 32, 'Verbannt', sides[owner].removed || [])}</div>
      </div>
    </article>)}
    <div className="arena-extra-row" aria-label="Extra-Monsterzonen">{[0, 1].map(index => {
      const ownSequence = 5 + index, otherSequence = 6 - index
      const ownAvailable = prompt?.choices.some(choice => choice.location?.owner === seat && choice.location.zone === 4 && choice.location.sequence === ownSequence)
      const owner = ownAvailable || sides[seat].field.some(value => value.zone === 4 && value.sequence === ownSequence) ? seat : 1 - seat
      return slot(owner, 4, owner === seat ? ownSequence : otherSequence, `Extra-Monsterzone ${index + 1}`)
    })}</div>
  </div>
}
