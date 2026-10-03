import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { api } from '../api/transport'
import type { OwnedVariant } from '../data/cards'
import { label } from '../i18n'

export function VariantDetails({ variants }: { variants: OwnedVariant[] }) {
  return <details className="variant-details"><summary>Bestandsvarianten · {variants.length}</summary><ul>{variants.map((variant, index) => <li key={`${variant.id}:${variant.bound}:${index}`}><strong>{variant.quantity} × {variant.legacy ? 'Altbestand – Ausgabe nicht bestimmt' : label(variant.rarity)}</strong><span>{variant.source ? `Herkunft: ${variant.source}` : 'Herkunft nicht eindeutig belegt'}</span><small>{variant.bound ? 'Kontogebunden' : `${variant.available} frei verfügbar`}{variant.reserved > 0 ? ` · ${variant.reserved} reserviert` : ''}</small></li>)}</ul></details>
}

type Movement = { id: number; card_id: number; name: string; rarity: string | null; legacy: boolean; source: string | null; amount: number; balance_after: number; reason: string; created_at: string }
export function InventoryJournal({ userId }: { userId?: number }) {
  const [page, setPage] = useState(1)
  const [data, setData] = useState<{ items: Movement[]; total: number; page_size: number } | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setData(null); setError('')
    api<{ items: Movement[]; total: number; page_size: number }>(`${userId ? `/admin/users/${userId}/inventory-journal` : '/inventory/me/journal'}?page=${page}`, { signal: controller.signal }).then(result => { if (!controller.signal.aborted) setData(result) }).catch(cause => { if (!controller.signal.aborted) setError(cause.message) })
    return () => controller.abort()
  }, [page, userId])
  const reasons: Record<string, string> = { admin_correction: 'Admin-Korrektur', season_reward: 'Saisonbelohnung', trade_in: 'Tausch erhalten', trade_out: 'Tausch abgegeben', admin_grant: 'Admin-Vergabe', booster_opening: 'Pack geöffnet', legacy_migration: 'Altbestand übernommen', opening_reconstruction: 'Bestand aus Öffnungshistorie zugeordnet' }
  return <section className="content-panel inventory-journal"><h2>Kartenbewegungen</h2><p>Jede Bewegung führt eine konkrete Bestandsvariante. Übernahmen zeigen den Zeitpunkt der Umstellung und sind keine neuen Kartengewinne.</p>{error ? <p role="alert" className="api-notice">{error}</p> : !data ? <p role="status">Kartenbewegungen werden geladen …</p> : <>{data.items.map(item => <article className="inventory-movement" key={item.id}><div><NavLink to={`/cards/${item.card_id}`}>{item.name}</NavLink><small>{item.legacy ? 'Altbestand – Ausgabe nicht bestimmt' : label(item.rarity)}{item.source ? ` · ${item.source}` : ''}</small><small>{reasons[item.reason] || 'Kartenbewegung'} · {new Date(item.created_at).toLocaleString('de-DE')}</small></div><div><strong>{item.amount > 0 ? '+' : ''}{item.amount}</strong><small>Variante danach: {item.balance_after}</small></div></article>)}{!data.items.length && <p>Noch keine Kartenbewegungen.</p>}<div className="pagination"><button className="outline-button" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>Zurück</button><span>Seite {page} / {Math.max(1, Math.ceil(data.total / data.page_size))}</span><button className="outline-button" disabled={page * data.page_size >= data.total} onClick={() => setPage(value => value + 1)}>Weiter</button></div></>}</section>
}
