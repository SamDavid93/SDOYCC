import { useEffect, useRef, useState } from 'react'
import { api, jsonPost } from '../api/transport'
import { useSession } from '../Session'
import { label } from '../i18n'
import { getCardDetail } from '../api/client'
import { CardVisual } from './CardVisual'
import type { CardRecord } from '../data/cards'

type Kind = 'points' | 'card' | 'pack'
type Position = { kind: Kind; quantity: number; card_id?: number; booster_id?: number; rarity?: string; bound?: boolean }
type Row = Position & { name: string; source?: string; before: number; after: number }
type Preview = { username: string; user_id: number; reason: string; items: Row[]; preview_hash: string; points_after: number }
type Receipt = Preview & { grant_id: number; audit_id: number }
type Option = { booster_id: number; name: string; rarity: string }
const names: Record<Kind, string> = { points: 'Sammelpunkte', card: 'Karten', pack: 'Packs' }

function CardPreview({ cardId, rarity }: { cardId: number; rarity?: string }) {
  const [card, setCard] = useState<CardRecord | null>(null)
  useEffect(() => {
    let active = true
    setCard(null)
    getCardDetail(cardId).then(value => { if (active) setCard(value) }).catch(() => {})
    return () => { active = false }
  }, [cardId])
  return card ? <div className="grant-card-preview"><CardVisual card={{ ...card, rarity: rarity || 'unknown' }} compact /></div> : null
}

export function GrantReceipt({ grantId }: { grantId: number }) {
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [error, setError] = useState('')
  return <details className="grant-saved-receipt" onToggle={event => {
    if (event.currentTarget.open && !receipt) api<Receipt>(`/admin/grants/${grantId}`).then(setReceipt).catch(cause => setError(cause.message))
  }}><summary>Vergabebeleg #{grantId} anzeigen</summary>{error && <p role="alert">{error}</p>}{receipt ? <ul className="grant-preview">{receipt.items.map((row, index) => <li key={index}><strong>+{row.quantity} {row.name}</strong>{row.rarity && <span>{label(row.rarity)} · {row.source}{row.bound ? ' · kontogebunden' : ''}</span>}<span>Bestand bei Vergabe: {row.before} → {row.after}</span></li>)}</ul> : !error && <p>Beleg wird geladen …</p>}</details>
}

export function GrantPanel({ account, onDone }: { account: { id: number; username: string; role: string; is_active: boolean; twitch_id: string | null }; onDone: (message: string) => void }) {
  const { user } = useSession()
  const [open, setOpen] = useState(false)
  if (!user || !['admin', 'super_admin'].includes(user.role) || !account.is_active || !account.twitch_id || (user.role !== 'super_admin' && account.role !== 'user')) return null
  return <section className="content-panel grant-entry"><h2>Belohnungen vergeben</h2><p>Stelle Punkte, Kartenvarianten und Packs für dieses Konto zusammen. Vor der Vergabe prüfst du alle Positionen gemeinsam.</p><button className="primary-button" onClick={() => setOpen(true)}>Vergabe vorbereiten</button>{open && <GrantDialog account={account} close={() => setOpen(false)} done={onDone} />}</section>
}

function GrantDialog({ account, close, done }: { account: { id: number; username: string }; close: () => void; done: (message: string) => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const requestKey = useRef(crypto.randomUUID())
  const { refresh } = useSession()
  const [items, setItems] = useState<(Position & { title: string })[]>([])
  const [kind, setKind] = useState<Kind>('points')
  const [quantity, setQuantity] = useState(100)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [catalog, setCatalog] = useState<{ items: { id: number; name: string }[]; total: number; page_size: number } | null>(null)
  const [selected, setSelected] = useState<{ id: number; name: string } | null>(null)
  const [options, setOptions] = useState<Option[]>([])
  const [option, setOption] = useState('')
  const [bound, setBound] = useState(false)
  const [reason, setReason] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [password, setPassword] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [limits, setLimits] = useState<Record<Kind, number> | null>(null)
  const draft = () => ({ user_id: account.id, reason: reason.trim(), items: items.map(({ title: _title, ...item }) => item) })
  useEffect(() => {
    const element = dialog.current!
    const previous = document.activeElement as HTMLElement | null
    element.showModal()
    api<Record<Kind, number>>('/admin/grants/limits').then(setLimits).catch(cause => setError(cause.message))
    return () => { element.close(); previous?.focus() }
  }, [])
  useEffect(() => {
    if (kind === 'points') return
    const controller = new AbortController()
    setCatalog(null)
    const timer = setTimeout(() => {
      api<NonNullable<typeof catalog>>(`/admin/grants/catalog?${new URLSearchParams({ kind, search, page: String(page) })}`, { signal: controller.signal }).then(result => { if (!controller.signal.aborted) setCatalog(result) }).catch(cause => { if (!controller.signal.aborted) setError(cause.message) })
    }, 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [kind, search, page])
  useEffect(() => {
    setOptions([]); setOption('')
    if (kind !== 'card' || !selected) return
    const controller = new AbortController()
    api<Option[]>(`/admin/grants/card-options/${selected.id}`, { signal: controller.signal }).then(result => { if (!controller.signal.aborted) setOptions(result) }).catch(cause => { if (!controller.signal.aborted) setError(cause.message) })
    return () => controller.abort()
  }, [kind, selected])
  function add() {
    if (!Number.isInteger(quantity) || quantity < 1) { setError('Bitte eine positive ganze Menge eingeben.'); return }
    let item: Position & { title: string } = { kind, quantity, title: names[kind] }
    if (kind !== 'points') {
      if (!selected) return
      item.title = selected.name
      if (kind === 'pack') item.booster_id = selected.id
      else {
        const source = options[Number(option)]
        if (option === '' || !source) return
        item = { ...item, card_id: selected.id, booster_id: source.booster_id, rarity: source.rarity, bound,
          title: `${selected.name} · ${label(source.rarity)} · ${source.name}${bound ? ' · kontogebunden' : ''}` }
      }
    }
    const same = items.findIndex(row => row.kind === item.kind && row.card_id === item.card_id && row.booster_id === item.booster_id && row.rarity === item.rarity && !!row.bound === !!item.bound)
    setItems(previous => same < 0 ? [...previous, item] : previous.map((row, index) => index === same ? { ...row, quantity: row.quantity + quantity } : row))
    setError('')
  }
  async function loadPreview() {
    setBusy(true); setError('')
    try { setPreview(await api<Preview>('/admin/grants/preview', jsonPost(draft()))); requestKey.current = crypto.randomUUID() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Vorschau fehlgeschlagen.') }
    finally { setBusy(false) }
  }
  async function execute() {
    if (busy || !preview) return
    setBusy(true); setError('')
    try {
      const result = await api<Receipt>('/admin/grants', { ...jsonPost({ ...draft(), password, confirmation, preview_hash: preview.preview_hash }), headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestKey.current } })
      setReceipt(result); setPassword(''); void refresh()
      window.dispatchEvent(new Event('hub-data-changed'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Vergabe fehlgeschlagen.'); setPassword('') }
    finally { setBusy(false) }
  }
  function finish() { if (receipt) done(`Vergabe #${receipt.grant_id} an @${account.username} erfolgreich · Protokoll #${receipt.audit_id}.`); close() }
  return <dialog ref={dialog} className="admin-dialog grant-dialog" aria-labelledby="grant-title" onCancel={event => { event.preventDefault(); if (!busy) finish() }}><h2 id="grant-title">{receipt ? 'Vergabe erfolgreich' : preview ? 'Vergabe prüfen' : 'Vergabe vorbereiten'}</h2><p><strong>Empfänger: @{account.username}</strong></p>
    {!preview && !receipt && <><div className="admin-tabs" role="group" aria-label="Belohnungsart">{Object.entries(names).map(([value, name]) => <button className={kind === value ? 'primary-button' : 'outline-button'} key={value} disabled={busy} onClick={() => { setKind(value as Kind); setQuantity(value === 'points' ? 100 : 1); setSelected(null); setSearch(''); setPage(1) }}>{name}</button>)}</div>
      {limits && <p>Limit je Vorgang: {limits.points.toLocaleString('de-DE')} Punkte · {limits.card} Karten · {limits.pack} Packs.</p>}
      {kind !== 'points' && <div className="grant-catalog"><label>{kind === 'card' ? 'Karte suchen' : 'Pack suchen'}<input value={search} onChange={event => { setSearch(event.target.value); setPage(1) }} maxLength={100} /></label>{!catalog ? <p role="status">Auswahl wird geladen …</p> : <><div className="grant-choices">{catalog.items.map(row => <button className={selected?.id === row.id ? 'selected' : ''} key={row.id} onClick={() => setSelected(row)}>{row.name}</button>)}</div>{catalog.total === 0 && <p>Keine passenden Einträge.</p>}<div className="grant-pages"><button className="outline-button" disabled={page === 1} onClick={() => setPage(page - 1)}>Zurück</button><span>Seite {page}</span><button className="outline-button" disabled={page * catalog.page_size >= catalog.total} onClick={() => setPage(page + 1)}>Weiter</button></div></>}{selected && <p>Gewählt: <strong>{selected.name}</strong></p>}
        {kind === 'card' && selected && <><CardPreview cardId={selected.id} rarity={option === '' ? undefined : options[Number(option)]?.rarity} /><label>Herkunft und Seltenheit<select value={option} onChange={event => setOption(event.target.value)}><option value="">Bitte auswählen</option>{options.map((row, index) => <option key={`${row.booster_id}:${row.rarity}`} value={index}>{row.name} · {label(row.rarity)}</option>)}</select></label>{!options.length && <p>Keine freigegebene Variante geladen. Wähle eine Karte aus einem gültigen Produkt.</p>}<label className="grant-bound"><input type="checkbox" checked={bound} onChange={event => setBound(event.target.checked)} />Kontogebunden (für späteren Handel gesperrt)</label></>}
      </div>}
      <div className="grant-quantity"><label>Menge<input type="number" min={1} max={limits?.[kind] || 1000000} step={1} value={quantity} onChange={event => setQuantity(Number(event.target.value))} /></label><button className="outline-button" onClick={add} disabled={busy || items.length >= 20 || (kind !== 'points' && !selected) || (kind === 'card' && option === '')}>Position hinzufügen</button></div>
      <ul className="grant-basket">{items.map((item, index) => <li key={index}><span>{item.quantity} × {item.title}</span><button className="outline-button" aria-label={`Position ${index + 1} entfernen`} onClick={() => setItems(rows => rows.filter((_, i) => i !== index))}>Entfernen</button></li>)}</ul>
      <label>Begründung (für den Empfänger sichtbar)<textarea value={reason} minLength={5} maxLength={500} onChange={event => setReason(event.target.value)} /></label><p>Structure-Deck-Vergaben zählen zum Limit von drei Bezügen je Konto. Packs bleiben ungeöffnet.</p><button className="primary-button" disabled={busy || !items.length || reason.trim().length < 5} onClick={() => void loadPreview()}>Vorschau laden</button>
    </>}
    {(receipt || preview) && <><ul className="grant-preview">{(receipt || preview)!.items.map((item, index) => <li key={index}><strong>+{item.quantity} {item.kind === 'points' ? 'Sammelpunkte' : `× ${item.name}`}</strong>{item.rarity && <span>{label(item.rarity)} · {item.source}{item.bound ? ' · kontogebunden' : ''}</span>}<span>Bestand: {item.before} → {item.after}</span></li>)}</ul><p>Grund: {(receipt || preview)!.reason}</p>{receipt ? <div className="success-notice" role="status">Vergabe #{receipt.grant_id} gebucht. Der Empfänger erhält eine Mitteilung im Hub.</div> : <form className="auth-form" onSubmit={event => { event.preventDefault(); void execute() }}><label>Empfänger zur Bestätigung<input value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="off" disabled={busy} /></label><label>Dein Administrator-Passwort<input type="password" autoComplete="current-password" value={password} maxLength={128} required onChange={event => setPassword(event.target.value)} disabled={busy} /></label><button className="primary-button" disabled={busy || confirmation !== account.username || !password}>{busy ? 'Wird vergeben …' : 'Verbindlich vergeben'}</button><button type="button" className="outline-button" disabled={busy} onClick={() => { setPreview(null); setPassword(''); setError('') }}>Zusammenstellung bearbeiten</button></form>}</>}
    {error && <p className="api-notice" role="alert">{error}</p>}<button className="outline-button" disabled={busy} onClick={finish}>{receipt ? 'Fertig' : 'Schließen'}</button>
  </dialog>
}
