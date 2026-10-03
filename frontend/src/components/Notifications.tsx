import { useEffect, useState } from 'react'
import { Bell } from 'lucide-react'
import { api } from '../api/transport'
import { useSession } from '../Session'
import { label } from '../i18n'

type Notice = { id: number; grant_id: number | null; title?: string; link?: string; read: boolean; reason: string; created_at: string; items: { kind: string; name: string; quantity: number; rarity?: string; bound?: boolean }[] }
export function Notifications() {
  const { user, revision } = useSession()
  const [open, setOpen] = useState(false)
  const [page, setPage] = useState(1)
  const [tick, setTick] = useState(0)
  const [data, setData] = useState<{ items: Notice[]; total: number; unread: number; page_size: number } | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { const timer = setInterval(() => { if (document.visibilityState === 'visible') setTick(value => value + 1) }, 30000); return () => clearInterval(timer) }, [])
  useEffect(() => {
    setData(null); setOpen(false); setPage(1)
  }, [user?.id])
  useEffect(() => {
    const controller = new AbortController()
    if (user) api<NonNullable<typeof data>>(`/notifications?page=${page}`, { signal: controller.signal }).then(result => { if (!controller.signal.aborted) { setData(result); setError('') } }).catch(cause => { if (!controller.signal.aborted) setError(cause.message) })
    return () => controller.abort()
  }, [user?.id, revision, tick, page])
  async function mark(id: number) {
    try { await api(`/notifications/${id}/read`, { method: 'POST' }); setTick(value => value + 1) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Mitteilung konnte nicht aktualisiert werden.') }
  }
  return <div className="notifications"><button className="icon-button" aria-label={`Mitteilungen${data?.unread ? `, ${data.unread} ungelesen` : ''}`} aria-expanded={open} onClick={() => setOpen(value => !value)}><Bell size={18} />{!!data?.unread && <b>{data.unread}</b>}</button>{open && <section className="notification-panel" aria-label="Mitteilungen"><div className="section-heading"><h3>Mitteilungen</h3><button className="outline-button" onClick={() => setOpen(false)}>Schließen</button></div>{error && <p role="alert">{error}</p>}{data?.items.map(item => <article key={item.id}><strong>{item.title || `Belohnung erhalten · #${item.grant_id}`}</strong><small>{new Date(item.created_at).toLocaleString('de-DE')}</small><ul>{item.items.map((row, index) => <li key={index}>+{row.quantity} {row.kind === 'points' ? 'Sammelpunkte' : `× ${row.name}`}{row.rarity ? ` · ${label(row.rarity)}` : ''}{row.bound ? ' · kontogebunden' : ''}</li>)}</ul><p>{item.reason}</p>{item.link && <a href={`#${item.link}`} onClick={() => setOpen(false)}>Vorgang ansehen</a>}{!item.read && <button className="outline-button" onClick={() => void mark(item.id)}>Als gelesen markieren</button>}</article>)}{data && !data.items.length && <p>Noch keine Mitteilungen.</p>}<div className="grant-pages"><button className="outline-button" disabled={page === 1} onClick={() => setPage(page - 1)}>Zurück</button><span>Seite {page}</span><button className="outline-button" disabled={!data || page * data.page_size >= data.total} onClick={() => setPage(page + 1)}>Weiter</button></div></section>}</div>
}
