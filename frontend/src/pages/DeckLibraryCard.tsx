import type { CatalogItem } from './DeckBuilder'
import { CardVisual } from '../components/CardVisual'
import { toCardRecord } from '../api/client'

type Budget = { reason: string; remaining: number; count: number; destination: string }
export function DeckLibraryCard({ item, state, readonly, add, remove, preview, drag, endDrag }: {
  item: CatalogItem; state: Budget; readonly: boolean; add: () => void; remove: () => void; preview: (explicit?: boolean) => void;
  drag: (event: React.DragEvent) => void; endDrag: () => void;
}) {
  const blocked = !!state.reason || readonly
  const forbidden = item.rule.status === 'mapped' && item.rule.copy_limit === 0
  const unverified = item.rule.status !== 'mapped' || !item.rule.script_available
  const title = forbidden ? 'Verboten' : unverified ? 'Nicht freigegeben' : state.remaining === 0 ? 'Ausgeschöpft' : 'Erlaubt'
  return <article className={'deck-library-card deck-budget-card ' + (blocked ? 'deck-card-blocked' : 'deck-card-allowed')} data-status={forbidden || unverified ? 'blocked' : state.remaining ? 'allowed' : 'full'} title={`${item.card.name} · ${title} · Im Deck: ${state.count} · Noch möglich: ${state.remaining}${state.reason ? ' · ' + state.reason : ''}`} draggable={!blocked} onDragStart={drag} onDragEnd={endDrag} onMouseEnter={() => preview()} onFocus={() => preview()}>
    <button className="deck-card-preview" aria-label={`${item.card.name} hinzufügen per Klick`} aria-disabled={blocked} disabled={readonly} onClick={() => { preview(); add() }} onContextMenu={event => { event.preventDefault(); preview(); remove() }}><CardVisual card={toCardRecord(item.card)} compact /></button>
    <span className="deck-tile-status" aria-label={title}>{forbidden ? '×' : unverified ? '?' : state.remaining ? '+' : '−'}</span>
    <span className="deck-tile-quantity" aria-label={`Im Deck ${state.count}, noch möglich ${state.remaining}`}>{state.count}<span> / {state.count + state.remaining}</span></span>
    <button className="deck-info-button" aria-label={`${item.card.name} ansehen`} onClick={() => preview(true)}>i</button>
  </article>
}
