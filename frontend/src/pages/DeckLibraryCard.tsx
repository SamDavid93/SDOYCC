import type { CatalogItem } from './DeckBuilder'
import { CardVisual } from '../components/CardVisual'
import { toCardRecord } from '../api/client'

type Budget = { reason: string; remaining: number; count: number; destination: string }

export function DeckLibraryCard({ item, state, readonly, add, remove, preview, drag, endDrag }: {
  item: CatalogItem; state: Budget; readonly: boolean; add: () => void; remove: () => void; preview: () => void;
  drag: (event: React.DragEvent) => void; endDrag: () => void;
}) {
  const blocked = !!state.reason || readonly
  const forbidden = item.rule.status === 'mapped' && item.rule.copy_limit === 0
  const unverified = item.rule.status !== 'mapped' || !item.rule.script_available
  const title = forbidden ? 'Verboten' : unverified ? 'Nicht freigegeben' : state.remaining === 0 ? 'Ausgeschöpft' : 'Erlaubt'
  return <article className={'deck-library-card deck-budget-card ' + (blocked ? 'deck-card-blocked' : 'deck-card-allowed')} draggable={!blocked} onDragStart={drag} onDragEnd={endDrag}>
    <span className={'deck-legality-badge ' + (forbidden || unverified ? 'is-blocked' : state.remaining ? 'is-allowed' : 'is-full')}>{title}</span>
    <div className="deck-card-budget"><span>Besessen <b>{item.owned}</b></span><span>Frei <b>{item.available}</b></span><span>Im Deck <b>{state.count}</b></span><span>Noch möglich <b>{state.remaining}</b></span></div>
    <button className="deck-card-preview" aria-label={`${item.card.name} hinzufügen per Klick`} aria-disabled={blocked} disabled={readonly} onClick={add} onContextMenu={event => { event.preventDefault(); remove() }}><CardVisual card={toCardRecord(item.card)} compact /></button>
    <small className="deck-rule-label">{unverified ? 'Zuordnung noch offen' : forbidden ? '0 erlaubt' : `${item.rule.copy_limit === 1 ? 'Limitiert: 1' : item.rule.copy_limit === 2 ? 'Semi-limitiert: 2' : 'Bis zu 3'} · alle Deckbereiche zusammen`}</small>
    {state.reason && <p className={'deck-card-reason' + (!forbidden && !unverified ? ' is-exhausted' : '')}>{state.reason}</p>}
    <div className="deck-library-actions"><button className="deck-add" aria-disabled={blocked} disabled={readonly} onClick={add} aria-label={`${item.card.name} hinzufügen`}>{blocked ? 'Nicht verfügbar' : '+1 ' + (state.destination === 'extra' ? 'Extra-Deck' : state.destination === 'side' ? 'Side-Deck' : 'Hauptdeck')}</button><button className="deck-info-button" aria-label={`${item.card.name} ansehen`} onClick={preview}>Details</button></div>
  </article>
}
