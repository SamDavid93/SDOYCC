import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api, jsonPost } from '../api/transport'
import { CardVisual } from './CardVisual'
import { toCardRecord, type ApiCard } from '../api/client'
import { label } from '../i18n'
import '../workflow.css'

export type Page<T> = { items: T[]; total: number; page_size: number }
export type Position = { kind: string; quantity: number; card_id?: number; booster_id?: number; rarity?: string; bound?: boolean; name?: string }
export type Packet = { variant_id: number; quantity: number; card: ApiCard }
export const stamp = (value: string) => new Date(value).toLocaleString('de-DE')
export const stateLabel: Record<string, string> = { draft: 'Entwurf', open: 'Offen', completed: 'Abgeschlossen', cancelled: 'Zurückgezogen', expired: 'Abgelaufen', moderated: 'Moderiert', pending: 'Offen', accepted: 'Angenommen', rejected: 'Abgelehnt', withdrawn: 'Zurückgezogen', invalidated: 'Aufgehoben', active: 'Aktiv', scheduled: 'Geplant', ended: 'Abholfrist läuft', archived: 'Archiviert', published: 'Veröffentlicht', done: 'Ausgeführt', ready: 'Bereit', resolved: 'Geprüft' }

export function useRead<T>(path: string | null, revision = 0) {
  const [data, setData] = useState<T>(); const [error, setError] = useState('')
  useEffect(() => { setData(undefined); setError(''); if (!path) return; const ctrl = new AbortController(); api<T>(path, { signal: ctrl.signal }).then(v => { if (!ctrl.signal.aborted) setData(v) }).catch(e => { if (!ctrl.signal.aborted) setError(e.message) }); return () => ctrl.abort() }, [path, revision])
  return { data, error }
}
export function useAction() {
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const keys = useRef(new Map<string, string>())
  async function run<T>(path: string, body: unknown = {}): Promise<T | undefined> {
    if (busy) return; setBusy(true); setError('')
    const fingerprint = path + JSON.stringify(body, (key, value) => key === 'password' ? undefined : value)
    if (!keys.current.has(fingerprint)) keys.current.set(fingerprint, crypto.randomUUID())
    try { const value = await api<T>(path, { ...jsonPost(body), headers: { 'Content-Type': 'application/json', 'Idempotency-Key': keys.current.get(fingerprint)! } }); keys.current.delete(fingerprint); window.dispatchEvent(new Event('hub-data-changed')); return value }
    catch (e) { setError(e instanceof Error ? e.message : 'Aktion fehlgeschlagen.'); return undefined } finally { setBusy(false) }
  }
  return { run, busy, error }
}
export function ErrorBox({ message }: { message?: string }) { return message ? <p className="api-notice" role="alert">{message}</p> : null }
export function Pager({ page, setPage, total, size = 20 }: { page: number; setPage: (n: number) => void; total: number; size?: number }) { return <div className="workflow-actions"><button className="outline-button" disabled={page === 1} onClick={() => setPage(page - 1)}>Zurück</button><span>Seite {page} · {total} Einträge</span><button className="outline-button" disabled={page * size >= total} onClick={() => setPage(page + 1)}>Weiter</button></div> }
export function PacketView({ items }: { items: Packet[] }) { return <div className="packet-grid">{items.map(i => <div key={i.variant_id}><CardVisual card={{ ...toCardRecord(i.card), quantity: i.quantity }} compact showQuantity /><small>{label(i.card.rarity)}</small></div>)}</div> }
function RewardRow({ item }: { item: Position }) {
  const [card, setCard] = useState<ApiCard>(); const [pack, setPack] = useState<{ name: string; image_url?: string }>()
  useEffect(() => { let active = true; if (item.card_id) api<ApiCard>(`/cards/${item.card_id}`).then(c => { if(active) setCard(c) }).catch(() => {}); if(item.kind === 'pack') api<{id:number;name:string;image_url?:string}[]>('/boosters').then(rows => { if(active) setPack(rows.find(p=>p.id===item.booster_id)) }).catch(()=>{}); return ()=>{active=false} }, [item.card_id,item.booster_id,item.kind])
  return <li>{item.quantity} × {item.kind === 'points' ? 'Sammelpunkte' : item.name || card?.name || pack?.name || 'Belohnung wird geladen …'}{item.rarity && ` · ${label(item.rarity)}`}{item.bound && ' · kontogebunden'}{card && <details><summary>Kartenvorschau</summary><div style={{maxWidth:130}}><CardVisual card={{...toCardRecord(card),rarity:item.rarity||card.rarity}} compact /></div></details>}{pack?.image_url && <details><summary>Booster-Vorschau</summary><img src={pack.image_url} alt={pack.name} width="100" loading="lazy" /></details>}</li>
}
export function RewardList({ items }: { items: Position[] }) { return <ul>{items.map((i,n)=><RewardRow key={n} item={i}/>)}</ul> }

export function Confirm({ title, children, admin = false, busy, error, close, confirm }: { title: string; children: ReactNode; admin?: boolean; busy: boolean; error?: string; close: () => void; confirm: (password: string, reason: string) => void }) {
  const ref = useRef<HTMLDialogElement>(null); const [password, setPassword] = useState(''); const [reason, setReason] = useState('')
  useEffect(() => { ref.current?.showModal(); ref.current?.querySelector<HTMLHeadingElement>('h2')?.focus(); if (ref.current) ref.current.scrollTop = 0; return () => ref.current?.close() }, [])
  return <dialog ref={ref} className="workflow-dialog" onCancel={e => { e.preventDefault(); if (!busy) close() }} aria-label={title}><form onSubmit={e => { e.preventDefault(); confirm(password, reason) }}><h2 tabIndex={-1}>{title}</h2>{children}{admin && <><label>Begründung<textarea required minLength={5} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label><label>Dein Administrator-Passwort<input type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={e => setPassword(e.target.value)} /></label></>}<ErrorBox message={error} /><div className="workflow-actions"><button type="button" className="outline-button" disabled={busy} onClick={close}>Abbrechen</button><button className="primary-button" disabled={busy}>{busy ? 'Wird verarbeitet …' : 'Verbindlich bestätigen'}</button></div></form></dialog>
}

type Choice = { id: number; name: string; username?: string; display_name?: string }
export function SearchPick({ path, title, choose }: { path: string; title: string; choose: (item: Choice) => void }) {
  const [search, setSearch] = useState(''); const [query, setQuery] = useState(''); const [page, setPage] = useState(1)
  useEffect(() => { const timer = setTimeout(() => { setQuery(search); setPage(1) }, 250); return () => clearTimeout(timer) }, [search])
  const r = useRead<Page<Choice>>(`${path}${path.includes('?') ? '&' : '?'}search=${encodeURIComponent(query)}&page=${page}&page_size=10`)
  return <section className="workflow-picker"><label>{title}<input value={search} maxLength={100} onChange={e => setSearch(e.target.value)} placeholder="Suchen …" /></label><ErrorBox message={r.error} />{!r.data ? <p>Lädt …</p> : <><div className="workflow-choices">{r.data.items.map(c => <button type="button" className="outline-button" key={c.id} onClick={() => choose(c)}>{c.name || c.display_name || c.username}</button>)}</div>{!r.data.items.length && <p>Keine Treffer.</p>}<Pager page={page} setPage={setPage} total={r.data.total} size={10} /></>}</section>
}

export function RewardEditor({ items, setItems }: { items: Position[]; setItems: (items: Position[]) => void }) {
  const [kind, setKind] = useState('points'); const [quantity, setQuantity] = useState(100); const [choice, setChoice] = useState<Choice>(); const [source, setSource] = useState(''); const [bound, setBound] = useState(false)
  const options = useRead<{ booster_id: number; name: string; rarity: string }[]>(kind === 'card' && choice ? `/admin/grants/card-options/${choice.id}` : null)
  const specials = useRead<Page<Choice & { card_id: number; state: string; tradable: boolean }>>(kind === 'special' ? '/admin/advanced/special-cards?page_size=100' : null)
  function add() {
    const base = { kind, quantity, ...(kind === 'points' ? {} : { name: choice?.name }) }; let item: Position
    if (kind === 'points') item = base
    else if (kind === 'pack' && choice) item = { ...base, booster_id: choice.id }
    else if (kind === 'special' && choice) item = { ...base, card_id: choice.id, bound }
    else if (kind === 'card' && choice && source) { const selected = options.data?.[Number(source)-1]; if (!selected) return; item = { ...base, card_id: choice.id, booster_id: selected.booster_id, rarity: selected.rarity, bound } }
    else return
    const identity = (p: Position) => [p.kind, p.card_id, p.booster_id, p.rarity, !!p.bound].join(':')
    const existing = items.find(i => identity(i) === identity(item)); setItems(existing ? items.map(i => i === existing ? { ...i, quantity: i.quantity+quantity } : i) : [...items, item])
  }
  return <div className="reward-editor"><div className="workflow-fields"><label>Belohnung<select value={kind} onChange={e => { setKind(e.target.value); setChoice(undefined); setSource(''); setQuantity(e.target.value === 'points' ? 100 : 1) }}><option value="points">Sammelpunkte</option><option value="pack">Booster</option><option value="card">Kartenvariante</option><option value="special">Community-Sonderkarte</option></select></label><label>Menge<input type="number" min="1" max="1000000" value={quantity} onChange={e => setQuantity(Number(e.target.value))} /></label></div>{['card','pack'].includes(kind) && <SearchPick path={`/admin/grants/catalog?kind=${kind}`} title={kind === 'card' ? 'Karte suchen' : 'Booster suchen'} choose={c => { setChoice(c); setSource('') }} />}{kind === 'special' && <label>Sonderkarte<select value={choice?.id || ''} onChange={e => { const s = specials.data?.items.find(s => s.card_id === Number(e.target.value)); setChoice(s ? { id: s.card_id, name: s.name } : undefined); setBound(s ? !s.tradable : false) }}><option value="">Bitte wählen</option>{specials.data?.items.filter(s => s.state === 'active').map(s => <option value={s.card_id} key={s.id}>{s.name}</option>)}</select></label>}{choice && <p>Ausgewählt: <strong>{choice.name}</strong></p>}{kind === 'card' && choice && <label>Ausgabe / Seltenheit<select value={source} onChange={e => setSource(e.target.value)}><option value="">Bitte wählen</option>{options.data?.map((o,i) => <option value={i+1} key={i}>{o.name} · {label(o.rarity)}</option>)}</select></label>}{['card','special'].includes(kind) && <label className="workflow-check"><input type="checkbox" checked={bound} onChange={e => setBound(e.target.checked)} />Kontogebunden (nicht handelbar)</label>}<button type="button" className="outline-button" disabled={!Number.isInteger(quantity) || quantity < 1 || (kind !== 'points' && !choice) || (kind === 'card' && !source) || items.length >= 20} onClick={add}>Position hinzufügen</button><RewardList items={items} />{items.map((i,n) => <button type="button" className="text-button" key={n} onClick={() => setItems(items.filter((_,k) => k !== n))}>Position {n+1} entfernen</button>)}</div>
}
export const cleanPositions = (items: Position[]) => items.map(({ name: _name, ...i }) => i)
