import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight, Search, ShieldCheck } from 'lucide-react'
import { api, jsonPost } from '../api/transport'
import { useSession } from '../Session'
import './admin.css'
import { InventoryJournal, VariantDetails } from '../components/InventoryDetails'
import { GrantPanel, GrantReceipt } from '../components/GrantPanel'
import type { OwnedVariant } from '../data/cards'

const roles: Record<string, string> = { user: 'Sammler', support_admin: 'Support', admin: 'Administrator', super_admin: 'Hauptadministrator' }
export const canReadAdmin = (role: string) => ['support_admin', 'admin', 'super_admin'].includes(role)
type Account = { id: number; username: string; display_name: string; twitch_id: string | null; role: string; is_active: boolean; registered: boolean; points: number; created_at: string; cards: number; unique_cards: number; packs: number }
type Page<T> = { items: T[]; total: number; page: number; page_size: number }
type Overview = { users: number; registered: number; pending: number; inactive: number; points: number; cards: number; packs: number }
type Entry = { id: number; name?: string; quantity?: number; amount?: number; balance_after?: number; reason?: string; created_at?: string; variants?: OwnedVariant[] }
const number = (value: number) => value.toLocaleString('de-DE')
const date = (value: string) => new Date(value).toLocaleString('de-DE')
const status = (account: Account) => !account.is_active ? 'Gesperrt' : account.registered ? 'Registriert' : account.twitch_id ? 'Registrierung offen' : 'Demo-Konto'

function useRead<T>(path: string, revision = 0) {
  const key = `${path}:${revision}`
  const [result, setResult] = useState<{ key: string; data?: T; error?: string }>()
  useEffect(() => {
    const controller = new AbortController()
    api<T>(path, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setResult({ key, data })
    }).catch(error => { if (!controller.signal.aborted) setResult({ key, error: error.message }) })
    return () => controller.abort()
  }, [path, key])
  return result?.key === key ? result : undefined
}

function Pagination({ page, total, size, setPage }: { page: number; total: number; size: number; setPage: (page: number) => void }) {
  return <div className="admin-pagination"><span>{number(total)} Einträge · Seite {page} von {Math.max(1, Math.ceil(total / size))}</span><div><button className="outline-button" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Vorherige Seite"><ChevronLeft size={18} /></button><button className="outline-button" disabled={page * size >= total} onClick={() => setPage(page + 1)} aria-label="Nächste Seite"><ChevronRight size={18} /></button></div></div>
}

export function AdminPage({ userId }: { userId?: number }) {
  const { user } = useSession()
  if (!user || !canReadAdmin(user.role)) return <div className="page-wrap"><h1>Kein Zugriff</h1><p>Für diesen Bereich fehlen dir die Verwaltungsrechte.</p><NavLink to="/">Zur Übersicht</NavLink></div>
  return <div className="page-wrap admin-page"><section className="page-heading"><p className="eyebrow accent"><ShieldCheck size={15} /> VERWALTUNG</p><h1>{userId ? 'Kontodetails' : 'Deine Community im Blick'}</h1><p>Konten finden, Bestände prüfen und Änderungen nachvollziehen.</p></section><div className="admin-access"><span>{roles[user.role]}</span><p>{user.role === 'support_admin' ? 'Lesender Support-Zugriff' : 'Kontoaktionen mit Passwortbestätigung und Änderungsprotokoll'}</p></div>{userId ? <AccountDetail key={userId} userId={userId} /> : <><NavLink className="primary-button" to="/admin/advanced">Sonderkarten, Sammelvergaben, Handel & Saisons</NavLink><Directory />{user.role !== 'support_admin' && <AuditPanel />}</>}</div>
}

function Directory() {
  const [revision, setRevision] = useState(0)
  const summary = useRead<Overview>('/admin/overview', revision)
  const [input, setInput] = useState('')
  const [query, setQuery] = useState({ search: '', state: 'all', role: 'all', page: 1 })
  const result = useRead<Page<Account>>(`/admin/users?${new URLSearchParams({ ...query, page: String(query.page) })}`, revision)
  return <>
    <div className="section-heading"><h2>Konten & Bestände</h2><button className="outline-button" onClick={() => setRevision(value => value + 1)}>Aktualisieren</button></div>
    {summary?.error && <p className="api-notice" role="alert">{summary.error}</p>}
    <section className="stats-grid" aria-label="Community-Statistik">{([['Konten', 'users'], ['Registriert', 'registered'], ['Registrierung offen', 'pending'], ['Gesperrt', 'inactive'], ['Sammelpunkte', 'points'], ['Kartenexemplare', 'cards'], ['Ungeöffnete Packs', 'packs']] as const).map(([label, field]) => <div className="stat-card" key={field}><span className="stat-label">{label}</span><strong className="stat-value">{summary?.data ? number(summary.data[field]) : '…'}</strong></div>)}</section>
    <section className="content-panel"><form className="admin-filters" onSubmit={event => { event.preventDefault(); setQuery(value => ({ ...value, search: input.trim(), page: 1 })) }}><label className="admin-search">Name oder Twitch-ID<input maxLength={100} value={input} onChange={event => setInput(event.target.value)} placeholder="Konto suchen …" /></label><label>Status<select value={query.state} onChange={event => setQuery(value => ({ ...value, state: event.target.value, page: 1 }))}><option value="all">Alle Konten</option><option value="registered">Registriert</option><option value="pending">Registrierung offen</option><option value="inactive">Gesperrt</option></select></label><label>Rolle<select value={query.role} onChange={event => setQuery(value => ({ ...value, role: event.target.value, page: 1 }))}><option value="all">Alle Rollen</option>{Object.entries(roles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button className="primary-button" type="submit"><Search size={17} />Suchen</button></form>
      {result?.error ? <p role="alert" className="api-notice">{result.error}</p> : !result?.data ? <p role="status">Konten werden geladen …</p> : <><div className="admin-account-list">{result.data.items.map(account => <NavLink className="admin-account-row" key={account.id} to={`/admin/users/${account.id}`}><div className="admin-avatar">{account.display_name.slice(0, 2).toUpperCase()}</div><div><strong>{account.display_name}</strong><small>@{account.username} · {roles[account.role] || 'Unbekannte Rolle'}</small></div><span className={`admin-status ${!account.is_active ? 'is-blocked' : ''}`}>{status(account)}</span><strong className="admin-balance">{number(account.points)}<small>Sammelpunkte</small></strong><ChevronRight size={18} /></NavLink>)}</div>{result.data.total === 0 && <p>Keine passenden Konten gefunden.</p>}<Pagination page={query.page} total={result.data.total} size={result.data.page_size} setPage={page => setQuery(value => ({ ...value, page }))} /></>}
    </section>
  </>
}

function AccountDetail({ userId }: { userId: number }) {
  const { user } = useSession()
  const [receipt, setReceipt] = useState('')
  const [revision, setRevision] = useState(0)
  const result = useRead<Account>(`/admin/users/${userId}`, revision)
  const [tab, setTab] = useState('wallet')
  const account = result?.data
  return <>{receipt && <div className="success-notice" role="status">{receipt}</div>}<div className="section-heading"><NavLink className="back-link" to="/admin"><ArrowLeft size={16} />Alle Konten</NavLink><button className="outline-button" onClick={() => setRevision(value => value + 1)}>Aktualisieren</button></div>{result?.error ? <p className="api-notice" role="alert">{result.error}</p> : !account ? <p role="status">Konto wird geladen …</p> : <><section className="content-panel admin-profile"><div><h2>{account.display_name}</h2><p>@{account.username}</p><span className="admin-status">{status(account)}</span></div><dl><div><dt>Kontonummer</dt><dd>{account.id}</dd></div><div><dt>Twitch-ID</dt><dd>{account.twitch_id || 'Nicht verknüpft'}</dd></div><div><dt>Rolle</dt><dd>{roles[account.role] || 'Unbekannte Rolle'}</dd></div><div><dt>Angelegt</dt><dd>{date(account.created_at)}</dd></div></dl></section><section className="stats-grid">{[['Sammelpunkte', account.points], ['Kartenexemplare', account.cards], ['Verschiedene Karten', account.unique_cards], ['Ungeöffnete Packs', account.packs]].map(([label, value]) => <div className="stat-card" key={label}><span className="stat-label">{label}</span><strong className="stat-value">{number(Number(value))}</strong></div>)}</section><GrantPanel account={account} onDone={message => { setReceipt(message); setRevision(value => value + 1) }} /><AccountActions account={account} onDone={message => { setReceipt(message); setRevision(value => value + 1) }} /><div className="admin-tabs" role="group" aria-label="Kontobereich">{[['wallet', 'Buchungen'], ['inventory', 'Kartensammlung'], ['packs', 'Pack-Bestand'], ['journal', 'Kartenbewegungen']].map(([value, label]) => <button className={tab === value ? 'primary-button' : 'outline-button'} aria-pressed={tab === value} key={value} onClick={() => setTab(value)}>{label}</button>)}</div><>{tab === 'journal' ? <InventoryJournal key={`${userId}:${revision}`} userId={userId} /> : <AccountEntries key={`${userId}:${tab}`} userId={userId} tab={tab} revision={revision} />}</>{user?.role !== 'support_admin' && <AuditPanel userId={userId} revision={revision} />}</>}</>
}

function AccountEntries({ userId, tab, revision }: { userId: number; tab: string; revision: number }) {
  const [page, setPage] = useState(1)
  const result = useRead<Page<Entry>>(`/admin/users/${userId}/${tab}?page=${page}`, revision)
  const reasons: Record<string, string> = { admin_correction: 'Admin-Korrektur', season_reward: 'Saisonbelohnung', admin_grant: 'Admin-Gutschrift', opening_balance: 'Übernommenes Guthaben', twitch_redemption: 'Twitch-Kanalpunkte', booster_purchase: 'Booster-Kauf' }
  return <section className="content-panel">{tab === 'inventory' && <p className="admin-note">Gesamtmenge je Karte. Die Bestandsvarianten zeigen belegte Seltenheiten und ungeklärten Altbestand getrennt.</p>}{result?.error ? <p className="api-notice" role="alert">{result.error}</p> : !result?.data ? <p role="status">Einträge werden geladen …</p> : <>{result.data.items.map(entry => <div className="admin-entry" key={entry.id}>{tab === 'wallet' ? <><div><strong>{reasons[entry.reason || ''] || 'Sonstige Buchung'}</strong><small>{date(entry.created_at!)}</small></div><div><strong>{entry.amount! > 0 ? '+' : ''}{number(entry.amount!)} Punkte</strong><small>Stand: {number(entry.balance_after!)}</small></div></> : <><NavLink to={`/${tab === 'inventory' ? 'cards' : 'boosters'}/${entry.id}`}>{entry.name}</NavLink><div><strong>{number(entry.quantity!)} ×</strong>{entry.variants && <VariantDetails variants={entry.variants} />}</div></>}</div>)}{result.data.items.length === 0 && <p>Keine Einträge vorhanden.</p>}<Pagination page={page} total={result.data.total} size={result.data.page_size} setPage={setPage} /></>}</section>
}

const actionLabels: Record<string, string> = { grant: 'Belohnung vergeben', reset_login: 'Anmeldung zurücksetzen', revoke_sessions: 'Alle Sitzungen beenden', block: 'Konto sperren', unblock: 'Konto entsperren', change_role: 'Rolle ändern', owner_bootstrap: 'Hauptadministrator eingerichtet' }
const consequences: Record<string, string> = {
  reset_login: 'Das Passwort wird gelöscht. Alle Sitzungen und bisherigen Bestätigungscodes werden ungültig. Der Nutzer fordert mit !register einen Link an und bestätigt einen neuen Code über sein Twitch-Konto. Erst danach kann er ein neues Passwort festlegen. Punkte, Karten, Packs, Kaufgrenzen und Historie bleiben erhalten.',
  revoke_sessions: 'Alle laufenden Anmeldungen dieses Kontos werden beendet. Eine neue Anmeldung mit dem bestehenden Passwort bleibt möglich.',
  block: 'Das Konto kann sich nicht mehr anmelden oder Aktionen ausführen. Alle Sitzungen und Bestätigungscodes werden ungültig. Die Sperre gilt bis zur manuellen Entsperrung. Der Spielstand bleibt erhalten.',
  unblock: 'Das Konto darf sich wieder anmelden. Zuvor beendete Sitzungen bleiben ungültig.',
  change_role: 'Die ausgewählte Rolle bestimmt den Verwaltungszugriff. Alle bestehenden Sitzungen werden beendet; der Nutzer muss sich neu anmelden. Nur ein Hauptadministrator kann Rollen vergeben.',
}

function AccountActions({ account, onDone }: { account: Account; onDone: (message: string) => void }) {
  const { user } = useSession()
  const [action, setAction] = useState('')
  if (!user || !['admin', 'super_admin'].includes(user.role)) return null
  const mayManage = account.twitch_id && account.username !== 'jaden-demo' && (user.role === 'super_admin' || account.role === 'user')
  if (!mayManage) return <p className="admin-note">Für dieses Konto stehen dir keine Verwaltungsaktionen zur Verfügung.</p>
  const self = user.id === account.id
  const actions = self ? ['revoke_sessions'] : ['reset_login', 'revoke_sessions', account.is_active ? 'block' : 'unblock', ...(user.role === 'super_admin' ? ['change_role'] : [])]
  return <section className="content-panel admin-actions"><h2>Konto verwalten</h2><p>Jede Aktion wird mit Begründung protokolliert. Die Anmeldung lässt sich unabhängig vom Spielstand zurücksetzen.</p><div>{actions.map(value => <button key={value} className="outline-button" onClick={() => setAction(value)}>{actionLabels[value]}</button>)}</div>{self && <p className="admin-note">Das eigene Verwaltungskonto kann hier nur abgemeldet werden.</p>}{action && <ActionDialog account={account} action={action} close={() => setAction('')} done={onDone} />}</section>
}

function ActionDialog({ account, action, close, done }: { account: Account; action: string; close: () => void; done: (message: string) => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const request = useRef<{ signature: string; key: string } | null>(null)
  const { refresh } = useSession()
  const [reason, setReason] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState(account.role)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const element = dialog.current!
    const previous = document.activeElement as HTMLElement | null
    element.showModal()
    return () => { element.close(); previous?.focus() }
  }, [])
  async function submit() {
    if (busy) return
    setBusy(true); setError('')
    const fields = { action, reason: reason.trim(), confirmation: confirmation.trim(), ...(action === 'change_role' ? { role } : {}) }
    const signature = JSON.stringify(fields)
    if (request.current?.signature !== signature) request.current = { signature, key: crypto.randomUUID() }
    try {
      const result = await api<{ audit_id: number; sessions_revoked: number }>(`/admin/users/${account.id}/actions`, {
        ...jsonPost({ ...fields, password }), headers: { 'Content-Type': 'application/json', 'Idempotency-Key': request.current.key },
      })
      setPassword('')
      done(`${actionLabels[action]}: @${account.username}. Erfolgreich ausgeführt · Vorgang #${result.audit_id}.`)
      void refresh()
      close()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Aktion fehlgeschlagen.'); setPassword('') }
    finally { setBusy(false) }
  }
  return <dialog ref={dialog} className="admin-dialog" aria-labelledby="admin-action-title" onCancel={event => { event.preventDefault(); if (!busy) close() }}><h2 id="admin-action-title">{actionLabels[action]}</h2><p><strong>Zielkonto: @{account.username}</strong> · Kontonummer {account.id}</p><p className="admin-consequence">{consequences[action]}</p><form className="auth-form" onSubmit={event => { event.preventDefault(); void submit() }}>
    {action === 'change_role' && <label>Neue Rolle<select value={role} onChange={event => setRole(event.target.value)} disabled={busy}>{Object.entries(roles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
    <label>Begründung<textarea required minLength={5} maxLength={500} value={reason} onChange={event => setReason(event.target.value)} disabled={busy} placeholder="Warum ist diese Aktion erforderlich?" /></label>
    <label>Benutzername zur Bestätigung<input required autoComplete="off" value={confirmation} onChange={event => setConfirmation(event.target.value)} disabled={busy} placeholder={account.username} /></label>
    <label>Dein Administrator-Passwort<input type="password" required maxLength={128} autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} disabled={busy} /></label>
    {error && <p role="alert" className="api-notice">{error}</p>}<div className="admin-dialog-buttons"><button type="button" className="outline-button" disabled={busy} onClick={close}>Abbrechen</button><button type="submit" className="primary-button" disabled={busy || confirmation.trim() !== account.username || reason.trim().length < 5}>{busy ? 'Wird ausgeführt …' : 'Verbindlich ausführen'}</button></div>
  </form></dialog>
}

type AuditEntry = { id: number; action: string; actor: string | null; target: string; target_id: number; created_at: string; details: { reason?: string; grant_id?: number; previous_role?: string; role?: string; before?: { role: string; is_active: boolean; registered: boolean; active_sessions: number }; after?: { role: string; is_active: boolean; registered: boolean; active_sessions: number } } }
function AuditPanel({ userId, revision = 0 }: { userId?: number; revision?: number }) {
  const [page, setPage] = useState(1)
  const [action, setAction] = useState('')
  const [refresh, setRefresh] = useState(0)
  const params = new URLSearchParams({ page: String(page), action, ...(userId ? { user_id: String(userId) } : {}) })
  const result = useRead<Page<AuditEntry>>(`/admin/audit?${params}`, revision + refresh)
  const describe = (state: NonNullable<AuditEntry['details']['before']>) => `${roles[state.role] || 'Unbekannte Rolle'} · ${state.is_active ? 'Aktiv' : 'Gesperrt'} · ${state.registered ? 'Passwort eingerichtet' : 'Neue Twitch-Bestätigung nötig'} · ${state.active_sessions} Sitzungen`
  return <section className="content-panel admin-audit"><div className="section-heading"><h2>Änderungsprotokoll</h2><button className="outline-button" onClick={() => setRefresh(value => value + 1)}>Protokoll aktualisieren</button></div><label>Aktion filtern<select value={action} onChange={event => { setAction(event.target.value); setPage(1) }}><option value="">Alle Aktionen</option>{Object.entries(actionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>{result?.error ? <p role="alert" className="api-notice">{result.error}</p> : !result?.data ? <p role="status">Protokoll wird geladen …</p> : <>{result.data.items.map(entry => <article className="admin-audit-entry" key={entry.id}><strong>#{entry.id} · {actionLabels[entry.action] || 'Kontoaktion'}</strong><p><NavLink to={`/admin/users/${entry.target_id}`}>@{entry.target}</NavLink> · {entry.actor ? `Durch @${entry.actor}` : 'Lokale Einrichtung'} · {date(entry.created_at)}</p>{entry.details.reason && <p>{entry.details.reason}</p>}{entry.details.grant_id && <GrantReceipt grantId={entry.details.grant_id} />}{entry.details.before && entry.details.after && <details><summary>Vorher und nachher</summary><p>Vorher: {describe(entry.details.before)}</p><p>Nachher: {describe(entry.details.after)}</p></details>}</article>)}{!result.data.items.length && <p>Noch keine passenden Vorgänge.</p>}<Pagination page={page} total={result.data.total} size={result.data.page_size} setPage={setPage} /></>}</section>
}
