import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { Archive, ArrowLeft, Check, Copy, Download, Layers3, Minus, Plus, ShieldCheck, Shuffle, Trash2, Upload } from 'lucide-react'
import { api, apiFetch, API_BASE_URL, jsonPost } from '../api/transport'
import { toCardRecord, type ApiCard } from '../api/client'
import { CardVisual } from '../components/CardVisual'
import { OpeningCardPreview } from '../components/OpeningCardPreview'
import { ErrorBox, useAction, useRead } from '../components/Workflow'
import { label } from '../i18n'
import './decks.css'
import { DeckSharing } from './DeckSharing'

type Section = 'main' | 'extra' | 'side'
type Entry = { card_id: number; section: Section; quantity: number }
type Profile = { id: string; name: string; list_name: string; engine_approved: boolean; region_approved: boolean }
type Rule = { status: string; message: string; passcode: number | null; identity: number | null; copy_limit: number | null; section: Section | null; type_bits: number; script_available: boolean }
type Stock = { owned: number; available: number; stock_verified: boolean }
type Validation = { counts: Record<Section, number>; rules_ok: boolean; stock_ok: boolean; engine_ok: boolean; ready: boolean; issues: { kind: string; code: string; message: string; card_id: number | null }[]; stock: Record<number, Stock>; rules: Record<number, Rule> }
type Draft = { name: string; notes: string; profile_id: string | null; entries: Entry[] }
type Summary = { id: string; name: string; notes: string; profile_id: string | null; version: number; archived: boolean; updated_at: string; counts: Record<Section, number> }
type Deck = Summary & { entries: Entry[]; cards: Record<number, ApiCard>; validation: Validation; profile: Profile | null }
type CatalogItem = Stock & { card: ApiCard; rule: Rule }
const sections: [Section, string, string][] = [['main', 'Hauptdeck', '40–60'], ['extra', 'Extra-Deck', '0–15'], ['side', 'Side-Deck', '0–15']]
const draftOf = (deck: Deck): Draft => ({ name: deck.name, notes: deck.notes, profile_id: deck.profile_id, entries: deck.entries })
type Recovery = { version: number; draft: Draft; cards: Record<number, ApiCard> }
const recoveryKey = (id: string) => 'sdoycc-deck-draft:' + id
function readRecovery(id: string): Recovery | null {
  try {
    const raw = sessionStorage.getItem(recoveryKey(id))
    if (!raw || raw.length > 2000000) return null
    const item = JSON.parse(raw) as Recovery, d = item.draft
    if (!Number.isInteger(item.version) || item.version < 1 || !d || typeof d.name !== 'string' || d.name.length > 80 || typeof d.notes !== 'string' || d.notes.length > 1000 || (d.profile_id !== null && !/^[a-f0-9]{64}$/.test(d.profile_id)) || !Array.isArray(d.entries) || d.entries.length > 200) return null
    if (d.entries.some(e => !Number.isInteger(e.card_id) || e.card_id < 1 || !Number.isInteger(e.quantity) || e.quantity < 1 || !['main','extra','side'].includes(e.section)) || d.entries.reduce((n, e) => n+e.quantity, 0) > 200) return null
    if (!item.cards || typeof item.cards !== 'object' || Object.values(item.cards).some(c => !c || typeof c.name !== 'string' || typeof c.type !== 'string' || typeof c.rarity !== 'string' || !Number.isInteger(c.id))) return null
    return item
  } catch { return null }
}

export function DeckBuilder({ deckId }: { deckId?: string }) {
  const profiles = useRead<Profile[]>('/decks/profiles')
  return deckId ? <DeckLoader key={deckId} id={deckId} profiles={profiles.data || []} /> : <DeckList profiles={profiles.data || []} profileError={profiles.error} profileLoading={!profiles.data && !profiles.error} />
}

function DeckList({ profiles, profileError, profileLoading }: { profiles: Profile[]; profileError: string; profileLoading: boolean }) {
  const [archived, setArchived] = useState(false), [name, setName] = useState(''), [revision, setRevision] = useState(0)
  const list = useRead<Summary[]>(`/decks?archived=${archived}`, revision)
  const action = useAction(), navigate = useNavigate()
  async function create() {
    const deck = await action.run<Deck>('/decks', { name: name.trim(), profile_id: profiles[0]?.id || null, entries: [] })
    if (deck) navigate('/decks/' + deck.id)
  }
  async function manage(deck: Summary, kind: 'archive' | 'delete' | 'duplicate') {
    if (kind === 'delete' && !window.confirm(`„${deck.name}“ endgültig löschen? Deine Karten bleiben erhalten.`)) return
    const result = await action.run<Summary>(`/decks/${deck.id}/${kind}`, { version: deck.version, ...(kind === 'archive' ? { archived: !deck.archived } : {}) })
    if (result) { if (kind === 'duplicate') navigate('/decks/' + result.id); else setRevision(v => v+1) }
  }
  return <div className="page-wrap decks-page">
    <section className="deck-hero"><div><p className="eyebrow accent">DEINE KARTEN. DEINE STRATEGIE.</p><h1>Meine Decks</h1><p>Forme deine Sammlung zu einem Deck. Plane neue Kombinationen und sieh sofort, welche Karten dir noch fehlen.</p></div><div className="deck-hero-symbol" aria-hidden="true"><Layers3 size={72} /></div></section>
    <div className="deck-guide"><span><b>01</b> Deck zusammenstellen</span><span><b>02</b> Regeln & Besitz prüfen</span><span><b>03</b> Für die DuelZone vorbereiten</span></div>
    <p className="deck-phase-note">Baue private Decks aus deiner Sammlung. Karten bleiben in deinem Besitz und werden erst beim Duellstart reserviert.</p>
    <ErrorBox message={list.error || action.error || profileError} />
    <form className="deck-create" onSubmit={e => { e.preventDefault(); if (!profileLoading) void create() }}><label>Neues Deck<input value={name} onChange={e => setName(e.target.value)} maxLength={80} required placeholder="Zum Beispiel: Meine Drachenstrategie" /></label><button className="primary-button" disabled={profileLoading || action.busy || !name.trim()}><Plus size={18} />Deck erstellen</button></form>
    <div className="deck-list-heading"><h2>{archived ? 'Dein Deckarchiv' : 'Deine Strategien'}</h2><div className="deck-toggle"><button aria-pressed={!archived} onClick={() => setArchived(false)}>Aktiv</button><button aria-pressed={archived} onClick={() => setArchived(true)}>Archiv</button></div></div>
    {!list.data ? <p role="status">Decks werden geladen …</p> : list.data.length === 0 ? <div className="deck-empty"><Layers3 size={40} /><h3>{archived ? 'Dein Archiv ist leer.' : 'Dein erstes Deck wartet auf dich.'}</h3><p>Gib deinem Deck einen Namen und füge Karten aus deiner Sammlung hinzu.</p></div> : <div className="deck-list">{list.data.map(deck => <article className="deck-tile" key={deck.id}>
      <div className="deck-tile-art" aria-hidden="true"><i /><i /><i /><Layers3 size={38} /></div><div className="deck-tile-copy"><p className="eyebrow">{deck.archived ? 'ARCHIVIERT' : 'PRIVATER DECKENTWURF'}</p><h3><NavLink to={'/decks/' + deck.id}>{deck.name}</NavLink></h3><p>{deck.counts.main} Haupt · {deck.counts.extra} Extra · {deck.counts.side} Side</p><small>Geändert am {new Date(deck.updated_at).toLocaleDateString('de-DE')}</small></div>
      <div className="deck-tile-actions"><NavLink className="primary-button" to={'/decks/' + deck.id}>{deck.archived ? 'Ansehen' : 'Deck bearbeiten'}</NavLink><button title="Duplizieren" aria-label={`${deck.name} duplizieren`} disabled={action.busy} onClick={() => void manage(deck, 'duplicate')}><Copy size={16} /></button><button title={deck.archived ? 'Wiederherstellen' : 'Archivieren'} aria-label={`${deck.name} ${deck.archived ? 'wiederherstellen' : 'archivieren'}`} disabled={action.busy} onClick={() => void manage(deck, 'archive')}><Archive size={16} /></button><button title="Löschen" aria-label={`${deck.name} löschen`} disabled={action.busy} onClick={() => void manage(deck, 'delete')}><Trash2 size={16} /></button></div>
    </article>)}</div>}
  </div>
}

function DeckLoader({ id, profiles }: { id: string; profiles: Profile[] }) {
  const result = useRead<Deck>('/decks/' + id)
  if (!result.data) return <div className="page-wrap"><NavLink to="/decks" className="back-link">← Meine Decks</NavLink><ErrorBox message={result.error} />{!result.error && <p role="status">Deck wird geladen …</p>}</div>
  return <DeckEditor initial={result.data} profiles={profiles} />
}

function DeckEditor({ initial, profiles }: { initial: Deck; profiles: Profile[] }) {
  const [draft, setDraft] = useState<Draft>(draftOf(initial)), [cards, setCards] = useState(initial.cards)
  const [validation, setValidation] = useState<Validation>(initial.validation), [validating, setValidating] = useState(false)
  const [version, setVersion] = useState(initial.version), [saved, setSaved] = useState(JSON.stringify(draftOf(initial)))
  const [saveState, setSaveState] = useState('Gespeichert'), [saveError, setSaveError] = useState(''), [error, setError] = useState('')
  const [readonly, setReadonly] = useState(initial.archived)
  const [recovery, setRecovery] = useState<Recovery | null>(() => readRecovery(initial.id))
  const recoverAction = useAction(), navigate = useNavigate()
  const [pulse, setPulse] = useState(0), [section, setSection] = useState<Section>('main'), [pane, setPane] = useState('deck')
  const [preview, setPreview] = useState<ApiCard>(), [testHand, setTestHand] = useState<ApiCard[]>()
  const [search, setSearch] = useState(''), [query, setQuery] = useState(''), [scope, setScope] = useState('owned'), [group, setGroup] = useState('all'), [page, setPage] = useState(1)
  const [drag, setDrag] = useState<{ cardId: number; from?: Section; ruleSection?: Section | null } | null>(null)
  const [filters, setFilters] = useState<Record<string, string>>({}), [refreshStock, setRefreshStock] = useState(0)
  const live = useRef(draft), currentVersion = useRef(version), saving = useRef(false), mounted = useRef(true)
  const file = useRef<HTMLInputElement>(null)
  live.current = draft
  const serialized = JSON.stringify(draft), dirty = serialized !== saved
  useEffect(() => {
    if (recovery) return
    try {
      if (!dirty) sessionStorage.removeItem(recoveryKey(initial.id))
      else sessionStorage.setItem(recoveryKey(initial.id), JSON.stringify({ version: currentVersion.current, draft,
        cards: Object.fromEntries(draft.entries.filter(e => cards[e.card_id]).map(e => [e.card_id, cards[e.card_id]])) }))
    } catch { /* Autosave and the leave warning remain available if tab storage is full. */ }
  }, [serialized, dirty, saved, recovery, initial.id, cards])
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => { const timer = window.setTimeout(() => { setQuery(search); setPage(1) }, 250); return () => clearTimeout(timer) }, [search])
  const params = new URLSearchParams({ scope, group, search: query, page: String(page), page_size: '18', ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')) })
  if (draft.profile_id) params.set('profile_id', draft.profile_id)
  const catalog = useRead<{ items: CatalogItem[]; total: number }>(`/decks/catalog?${params}`, refreshStock)
  useEffect(() => {
    if (catalog.data) setCards(previous => ({ ...previous, ...Object.fromEntries(catalog.data!.items.map(i => [i.card.id, i.card])) }))
  }, [catalog.data])
  const save = useCallback(async () => {
    if (saving.current || readonly) return
    const sent = JSON.stringify(live.current)
    saving.current = true; setSaveState('Wird gespeichert …'); setSaveError('')
    try {
      const result = await api<Deck>('/decks/' + initial.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...live.current, version: currentVersion.current }) })
      currentVersion.current = result.version
      if (mounted.current) { setVersion(result.version); setSaved(sent); setSaveState('Gespeichert'); setPulse(v => v+1) }
    } catch (cause) { if (mounted.current) { setSaveError((cause as Error).message); setSaveState('Nicht gespeichert') } }
    finally { saving.current = false }
  }, [initial.id, readonly])
  useEffect(() => {
    if (!dirty || readonly || saveError || !draft.name.trim()) return
    const timer = window.setTimeout(() => void save(), 900)
    return () => clearTimeout(timer)
  }, [serialized, saved, pulse, saveError, dirty, readonly, save])
  useEffect(() => {
    const ctrl = new AbortController(); setValidating(true)
    const timer = window.setTimeout(() => {
      api<Validation>('/decks/validate', { ...jsonPost({ ...draft, name: draft.name.trim() || 'Entwurf' }), signal: ctrl.signal }).then(value => {
        if (!ctrl.signal.aborted) { setValidation(value); setValidating(false); setError('') }
      }).catch(cause => { if (!ctrl.signal.aborted) { setError(cause.message); setValidating(false) } })
    }, 350)
    return () => { clearTimeout(timer); ctrl.abort() }
  }, [serialized, refreshStock])
  useEffect(() => {
    if (!dirty) return
    const leave = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    const navigate = (event: MouseEvent) => {
      const anchor = (event.target as Element).closest?.('a[href]') as HTMLAnchorElement | null
      if (anchor && anchor.hash !== window.location.hash && !window.confirm('Es gibt ungespeicherte Änderungen. Seite trotzdem verlassen?')) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener('beforeunload', leave); document.addEventListener('click', navigate, true)
    return () => { window.removeEventListener('beforeunload', leave); document.removeEventListener('click', navigate, true) }
  }, [dirty])
  useEffect(() => {
    const refresh = () => setRefreshStock(v => v+1)
    window.addEventListener('focus', refresh); window.addEventListener('hub-data-changed', refresh)
    return () => { window.removeEventListener('focus', refresh); window.removeEventListener('hub-data-changed', refresh) }
  }, [])
  function change(cardId: number, target: Section, delta: number) {
    if (readonly) return
    setDraft(d => {
      if (delta > 0 && d.entries.reduce((n, e) => n+e.quantity, 0) >= 200) { setError('Höchstens 200 Karten pro Entwurf.'); return d }
      const entries = d.entries.map(e => ({ ...e })), entry = entries.find(e => e.card_id === cardId && e.section === target)
      if (entry) entry.quantity += delta
      else if (delta > 0) entries.push({ card_id: cardId, section: target, quantity: delta })
      return { ...d, entries: entries.filter(e => e.quantity > 0) }
    })
    setTestHand(undefined)
  }
  function add(item: CatalogItem) {
    const target = section === 'side' ? 'side' : item.rule.section || section
    change(item.card.id, target, 1)
  }
  function dropCard(target: Section) {
    if (readonly || !drag) return
    if (target !== 'side' && drag.ruleSection && target !== drag.ruleSection) {
      setError(`Diese Karte gehört ins ${drag.ruleSection === 'extra' ? 'Extra-Deck' : 'Hauptdeck'} oder Side-Deck.`); setDrag(null); return
    }
    if (drag.from === target) { setDrag(null); return }
    if (drag.from) {
      setDraft(old => {
        const source = old.entries.find(entry => entry.card_id === drag.cardId && entry.section === drag.from)
        if (!source || source.quantity < 1) return old
        const entries = old.entries.map(entry => ({ ...entry }))
        entries.find(entry => entry.card_id === drag.cardId && entry.section === drag.from)!.quantity -= 1
        const destination = entries.find(entry => entry.card_id === drag.cardId && entry.section === target)
        if (destination) destination.quantity += 1; else entries.push({ card_id: drag.cardId, section: target, quantity: 1 })
        return { ...old, entries: entries.filter(entry => entry.quantity > 0) }
      })
      setTestHand(undefined)
    } else change(drag.cardId, target, 1)
    setError(''); setDrag(null)
  }
  async function reload() {
    if (dirty && !window.confirm('Aktuellen Serverstand laden und deinen ungespeicherten Entwurf verwerfen?')) return
    try {
      const next = await api<Deck>('/decks/' + initial.id, { signal: new AbortController().signal })
      setDraft(draftOf(next)); live.current = draftOf(next); currentVersion.current = next.version; setVersion(next.version)
      setSaved(JSON.stringify(draftOf(next))); setSaveError(''); setSaveState('Gespeichert'); setCards(next.cards); setValidation(next.validation); setReadonly(next.archived)
    } catch (cause) { setSaveError((cause as Error).message) }
  }
  async function recover(asCopy: boolean) {
    if (!recovery) return
    if (asCopy) {
      const copy = await recoverAction.run<Deck>('/decks', { ...recovery.draft, name: (recovery.draft.name.trim() || 'Deck').slice(0, 70) + ' (Rettung)' })
      if (!copy) return
      sessionStorage.removeItem(recoveryKey(initial.id)); navigate('/decks/' + copy.id)
    } else {
      if (recovery.version !== currentVersion.current || readonly) return
      setDraft(recovery.draft); setCards(old => ({ ...old, ...recovery.cards })); setRecovery(null)
    }
  }
  async function importFile(selectedFile?: File) {
    if (!selectedFile || readonly) return
    if (selectedFile.size > 100000) { setError('YDK-Datei ist größer als 100 KB.'); return }
    if (!draft.profile_id) { setError('Wähle zuerst einen Regelstand für die Passcode-Zuordnung.'); return }
    if (draft.entries.length && !window.confirm('Deckliste durch die YDK-Datei ersetzen? Deine Kartenbestände bleiben unverändert.')) return
    const selectedProfile = draft.profile_id
    const initialDraft = JSON.stringify(live.current)
    try {
      const result = await api<{ entries: Entry[]; cards: Record<number, ApiCard> }>('/decks/ydk/parse', jsonPost({ text: await selectedFile.text(), profile_id: selectedProfile }))
      if (JSON.stringify(live.current) !== initialDraft) { setError('Dein Entwurf wurde während des Imports geändert. Bitte die Datei erneut auswählen.'); return }
      setCards(old => ({ ...old, ...result.cards })); setDraft(old => ({ ...old, entries: result.entries })); setError(''); setTestHand(undefined)
    } catch (cause) { setError((cause as Error).message) }
  }
  async function exportFile() {
    try {
      const response = await apiFetch(`${API_BASE_URL}/decks/${initial.id}/ydk`, { signal: new AbortController().signal })
      if (!response.ok) throw new Error((await response.json()).detail || 'Export fehlgeschlagen.')
      const href = URL.createObjectURL(await response.blob()), anchor = document.createElement('a')
      anchor.href = href; anchor.download = 'sdoycc-deck.ydk'; anchor.click(); setTimeout(() => URL.revokeObjectURL(href), 1000)
    } catch (cause) { setError((cause as Error).message) }
  }
  function drawHand() {
    const pool = draft.entries.filter(e => e.section === 'main').flatMap(e => Array<ApiCard>(e.quantity).fill(cards[e.card_id])).filter(Boolean)
    if (pool.length < 5) return
    for (let i = pool.length-1; i > 0; i--) {
      const bound = Math.floor(0x100000000 / (i+1)) * (i+1); let value: number
      do { value = crypto.getRandomValues(new Uint32Array(1))[0] } while (value >= bound)
      const j = value % (i+1); [pool[i], pool[j]] = [pool[j], pool[i]]
    }
    setTestHand(pool.slice(0, 5))
  }
  const totals = Object.fromEntries(sections.map(([s]) => [s, draft.entries.filter(e => e.section === s).reduce((n, e) => n+e.quantity, 0)])) as Record<Section, number>
  const inDeck = (id: number) => draft.entries.filter(e => e.card_id === id).reduce((n, e) => n+e.quantity, 0)
  const statuses = [['Deckregeln', validation.rules_ok], ['Karten verfügbar', validation.stock_ok], ['Duellfreigabe', validation.engine_ok]] as const
  const distribution = [['Monster', 1], ['Zauber', 2], ['Fallen', 4]].map(([title, bit]) => ({ title: String(title), count: draft.entries.filter(e => e.section === 'main' && (validation.rules[e.card_id]?.type_bits & Number(bit)) !== 0).reduce((n, e) => n+e.quantity, 0) }))
  return <div className="page-wrap decks-page deck-editor" data-pane={pane}>
    <NavLink to="/decks" className="back-link"><ArrowLeft size={15} /> Meine Decks</NavLink>
    <header className="deck-editor-heading"><div><p className="eyebrow accent">DEINE STRATEGIEWERKSTATT</p><h1>{draft.name || 'Unbenanntes Deck'}</h1></div><div className="deck-save-indicator" role="status"><Check size={16} />{readonly ? 'Archivierte Ansicht' : dirty && saveState === 'Gespeichert' ? 'Änderungen werden gespeichert …' : saveState}<small>Version {version}</small></div></header>
    {recovery && <section className="deck-recovery" aria-label="Ungespeicherten Entwurf wiederherstellen"><h2>Ein ungespeicherter Entwurf wartet auf dich.</h2><p>In diesem Browser-Tab wurde „{recovery.draft.name}“ gesichert. {recovery.version !== version || readonly ? 'Der Serverstand hat sich verändert oder liegt im Archiv. Rette deine Änderungen als neues Deck.' : 'Du kannst deine Änderungen wiederherstellen oder als neues Deck retten.'}</p><ErrorBox message={recoverAction.error} /><div className="deck-actions">{recovery.version === version && !readonly && <button disabled={recoverAction.busy} onClick={() => void recover(false)}>Entwurf wiederherstellen</button>}<button disabled={recoverAction.busy} onClick={() => void recover(true)}>Als neues Deck retten</button><button disabled={recoverAction.busy} onClick={() => { sessionStorage.removeItem(recoveryKey(initial.id)); setRecovery(null) }}>Lokalen Entwurf verwerfen</button></div></section>}
    <ErrorBox message={saveError || error || (!draft.name.trim() ? 'Bitte gib einen Decknamen ein, damit dein Entwurf gespeichert werden kann.' : '')} />{saveError && <div className="deck-actions"><button onClick={() => void save()} disabled={saving.current}>Erneut speichern</button><button onClick={() => void reload()} disabled={saving.current}>Serverstand laden</button></div>}
    {readonly && <p className="deck-phase-note">Dieses Deck liegt im Archiv. Stelle es in der Deckübersicht wieder her, um es zu bearbeiten.</p>}
    <div className="deck-status-strip">{statuses.map(([title, ok]) => <span key={title} className={ok && !validating ? 'is-good' : ''}><ShieldCheck size={17} />{title}<b>{validating ? 'Prüft …' : ok ? 'Erfüllt' : title === 'Duellfreigabe' ? 'Noch ausstehend' : 'Prüfen'}</b></span>)}</div>
    <div className="deck-mobile-tabs">{[['catalog', 'Karten suchen'], ['deck', 'Mein Deck'], ['review', 'Prüfung']].map(([value, title]) => <button key={value} aria-pressed={pane === value} onClick={() => setPane(value)}>{title}</button>)}</div>
    <div className="deck-workbench">
      <section className={'deck-library deck-panel' + (drag?.from ? ' deck-drop-active' : '')} onDragOver={event => { if (drag?.from && !readonly) event.preventDefault() }} onDrop={event => { event.preventDefault(); if (drag?.from && !readonly) change(drag.cardId, drag.from, -1); setDrag(null) }}><h2>Karten hinzufügen</h2><div className="deck-return-zone" onDragOver={event => { if (drag?.from && !readonly) { event.preventDefault(); event.dataTransfer.dropEffect = 'move' } }} onDrop={event => { event.preventDefault(); event.stopPropagation(); if (drag?.from && !readonly) change(drag.cardId, drag.from, -1); setDrag(null) }}>Deckkarte hier ablegen, um ein Exemplar zu entfernen</div><label>Karten suchen<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Name, Effekt oder Passcode" maxLength={150} /></label>
        <div className="deck-library-selects"><label>Kartenauswahl<select value={scope} onChange={e => { setScope(e.target.value); setPage(1) }}><option value="available">Meine verfügbaren Karten</option><option value="owned">Alle meine Karten</option><option value="all">Gesamter Katalog · Wunschdeck</option></select></label><label>Kartengruppe<select value={group} onChange={e => { setGroup(e.target.value); setPage(1) }}><option value="all">Alle Karten</option><option value="monster">Monster</option><option value="spell">Zauber</option><option value="trap">Fallen</option><option value="extra">Extra-Deck</option><option value="unknown">Zuordnung offen</option></select></label></div>
        <details className="deck-filter-details"><summary>Weitere Filter</summary><div className="deck-filter-grid">{[['attribute', 'Attribut'], ['race', 'Unterart (Original)'], ['archetype', 'Archetyp'], ['level', 'Stufe / Rang'], ['atk', 'Angriff'], ['defense', 'Verteidigung'], ['scale', 'Pendelskala'], ['link_value', 'Linkwert'], ['copy_limit', 'Kopienlimit']].map(([key, title], i) => <label key={key}>{title}{key === 'attribute' ? <select value={filters[key] || ''} onChange={e => { setFilters(f => ({ ...f, [key]: e.target.value })); setPage(1) }}><option value="">Alle</option>{['LIGHT','DARK','EARTH','WATER','FIRE','WIND','DIVINE','SPELL','TRAP'].map(v => <option key={v} value={v}>{label(v)}</option>)}</select> : <input type={i < 3 ? 'text' : 'number'} value={filters[key] || ''} onChange={e => { setFilters(f => ({ ...f, [key]: e.target.value })); setPage(1) }} />}</label>)}</div><button type="button" onClick={() => { setFilters({}); setGroup('all'); setPage(1) }}>Filter zurücksetzen</button></details>
        <ErrorBox message={catalog.error} />
        {!catalog.data ? <p role="status">Karten werden geladen …</p> : <><p className="deck-result-count">{catalog.data.total} Karten · Linksklick hinzufügen · Rechtsklick entfernen · Ziehen ins Deck</p><div className="deck-library-grid">{catalog.data.items.map(item => <article key={item.card.id} className="deck-library-card" draggable={!readonly} onDragStart={event => { setDrag({ cardId: item.card.id, ruleSection: item.rule.section }); event.dataTransfer.setData('text/plain', String(item.card.id)); event.dataTransfer.effectAllowed = 'copy' }} onDragEnd={() => setDrag(null)}><button className="deck-card-preview" aria-label={`${item.card.name} hinzufügen per Klick`} disabled={readonly} onClick={() => add(item)} onContextMenu={event => { event.preventDefault(); change(item.card.id, section === 'side' ? 'side' : item.rule.section || section, -1) }}><CardVisual card={toCardRecord(item.card)} compact /></button><small>{inDeck(item.card.id)} im Deck · {item.available} frei / {item.owned} besessen</small><small className={item.rule.status !== 'mapped' ? 'deck-warning' : ''}>{item.rule.copy_limit == null ? 'Zuordnung offen' : `Limit ${item.rule.copy_limit} · ${item.rule.section === 'extra' ? 'Extra' : 'Haupt'}`}</small><div className="deck-library-actions"><button className="deck-add" disabled={readonly} onClick={() => add(item)} aria-label={`${item.card.name} hinzufügen`}><Plus size={14} />{section === 'side' ? 'Ins Side-Deck' : item.rule.section === 'extra' ? 'Ins Extra-Deck' : 'Hinzufügen'}</button><button className="deck-info-button" aria-label={`${item.card.name} ansehen`} onClick={() => setPreview(item.card)}>Details</button></div></article>)}</div>{catalog.data.items.length === 0 && <p>Keine Karten gefunden. Für einen Wunschentwurf kannst du zum gesamten Katalog wechseln.</p>}<div className="deck-pagination"><button disabled={page === 1} onClick={() => setPage(p => p-1)}>Zurück</button><span>Seite {page}</span><button disabled={page*18 >= catalog.data.total} onClick={() => setPage(p => p+1)}>Weiter</button></div></>}
      </section>
      <section className="deck-composition deck-panel"><div className="deck-fields"><label>Deckname<input value={draft.name} maxLength={80} disabled={readonly} onChange={e => setDraft(d => ({ ...d, name: e.target.value }))} /></label><label>Regelstand<select value={draft.profile_id || ''} disabled={readonly} onChange={e => { setDraft(d => ({ ...d, profile_id: e.target.value || null })); setPage(1) }}><option value="">Noch kein Regelstand</option>{profiles.map(p => <option key={p.id} value={p.id}>{p.name} · {p.id.slice(0, 8)}</option>)}</select></label></div>
        <div className="deck-section-tabs">{sections.map(([s, title, range]) => <button key={s} className={drag ? 'deck-drop-tab' : ''} aria-pressed={section === s} onClick={() => setSection(s)} onDragOver={event => { if (drag && !readonly) event.preventDefault() }} onDrop={event => { event.preventDefault(); dropCard(s); setSection(s) }}><strong>{title}</strong><b>{totals[s]}</b><small>{range} Karten</small></button>)}</div>
        <p className="deck-section-help">{section === 'side' ? 'Neue Karten werden dem Side-Deck hinzugefügt.' : 'Geprüfte Kartentypen werden automatisch Haupt- oder Extra-Deck zugeordnet.'}</p>
        <div className={'deck-entries' + (drag ? ' deck-drop-active' : '')} onDragOver={event => { if (drag && !readonly) event.preventDefault() }} onDrop={event => { event.preventDefault(); dropCard(section) }}>{draft.entries.filter(e => e.section === section).map(entry => {
          const card = cards[entry.card_id], stock = validation.stock[entry.card_id], missing = stock ? Math.max(0, inDeck(entry.card_id)-stock.available) : inDeck(entry.card_id)
          return <article key={entry.card_id} className={`deck-entry ${missing ? 'is-missing' : ''}`} draggable={!readonly} onDragStart={event => { setDrag({ cardId: entry.card_id, from: section, ruleSection: validation.rules[entry.card_id]?.section }); event.dataTransfer.setData('text/plain', String(entry.card_id)); event.dataTransfer.effectAllowed = 'move' }} onDragEnd={() => setDrag(null)}><button className="deck-card-preview" disabled={readonly} onClick={() => change(entry.card_id, section, 1)} onContextMenu={event => { event.preventDefault(); change(entry.card_id, section, -1) }} aria-label={`${card?.name || 'Karte'} ein Exemplar hinzufügen`}>{card ? <CardVisual card={{ ...toCardRecord(card), quantity: entry.quantity }} compact showQuantity /> : <span>Karte wird geladen …</span>}</button><button className="deck-info-button" onClick={() => card && setPreview(card)} aria-label={`${card?.name || 'Karte'} ansehen`}>Details</button><div className="deck-entry-stepper"><button disabled={readonly} aria-label={`${card?.name} entfernen`} onClick={() => change(entry.card_id, section, -1)}><Minus size={14} /></button><b>{entry.quantity}</b><button disabled={readonly} aria-label={`${card?.name} ein weiteres Exemplar`} onClick={() => change(entry.card_id, section, 1)}><Plus size={14} /></button></div><small>{validating ? 'Bestand wird geprüft …' : missing ? `${missing} Ex. im Deck nicht verfügbar` : 'Bestand vorhanden'}</small><label className="deck-move">Verschieben<select aria-label={`${card?.name} verschieben`} disabled={readonly} value="" onChange={e => { if (!e.target.value) return; change(entry.card_id, section, -1); change(entry.card_id, e.target.value as Section, 1) }}><option value="">1 Exemplar …</option>{sections.filter(([s]) => s !== section && (s === 'side' || !validation.rules[entry.card_id]?.section || s === validation.rules[entry.card_id].section)).map(([s, title]) => <option key={s} value={s}>{title}</option>)}</select></label></article>
        })}</div>
        {!draft.entries.some(e => e.section === section) && <div className="deck-empty"><Layers3 size={34} /><h3>Hier beginnt deine Strategie.</h3><p>Füge Karten aus der Suche hinzu. Fehlende Exemplare bleiben als Wunschkarten sichtbar.</p><button className="outline-button deck-mobile-search" onClick={() => setPane('catalog')}>Karten suchen</button></div>}
        <details className="deck-notes"><summary>Strategienotizen</summary><label>Deine privaten Notizen<textarea aria-label="Deine privaten Notizen" maxLength={1000} value={draft.notes} disabled={readonly} onChange={e => setDraft(d => ({ ...d, notes: e.target.value }))} /></label></details>
        <div className="deck-actions"><button disabled={readonly || !draft.profile_id} onClick={() => file.current?.click()}><Upload size={15} />YDK importieren</button><button disabled={dirty || saving.current} onClick={() => void exportFile()}><Download size={15} />YDK exportieren</button><button disabled={totals.main < 5} onClick={drawHand}><Shuffle size={15} />Testhand ziehen</button></div><input ref={file} type="file" accept=".ydk,text/plain" className="deck-file-input" aria-label="YDK-Datei auswählen" onChange={e => { void importFile(e.target.files?.[0]); e.target.value = '' }} />
        <DeckSharing deckId={initial.id} version={version} disabled={dirty || saving.current || readonly} />
        {testHand && <section className="deck-test-hand"><h3>Deine Testhand</h3><p>Fünf zufällige Karten aus deinem Entwurf. Keine Kartenvergabe oder Effektsimulation.</p><div>{testHand.map((card, index) => <button key={index} className="deck-card-preview" onClick={() => setPreview(card)}><CardVisual card={toCardRecord(card)} compact /></button>)}</div></section>}
      </section>
      <aside className="deck-review deck-panel"><p className="eyebrow accent">DEIN STRATEGIE-CHECK</p><h2>Deckprüfung</h2><p>Alle drei Deckbereiche zählen gemeinsam für Kartenbesitz und Kopienlimits.</p><button className="outline-button" onClick={() => setRefreshStock(v => v+1)} disabled={validating}>Bestand erneut prüfen</button>
        <dl className="deck-counts">{sections.map(([s, title, range]) => <div key={s}><dt>{title}</dt><dd>{totals[s]} <small>/ {range}</small></dd></div>)}</dl>
        <h3>Dein Hauptdeck</h3><div className="deck-distribution">{distribution.map(item => <span key={item.title}><b>{validating ? '…' : item.count}</b>{item.title}</span>)}</div><small className="deck-result-count">Nur Karten mit bekannten Engine-Typdaten werden einsortiert.</small>
        {!profiles.length && <p className="deck-warning">Es wurde noch kein versioniertes Regelpaket vorbereitet. Entwürfe sind möglich; Kartenfreigaben bleiben offen.</p>}
        <p className="deck-phase-note">Geprüft werden dein aktueller Besitz und der ausgewählte Regelstand. Ein Deckentwurf verändert weder Guthaben noch Kartenbestand; zum Duellstart müssen auch die Regelfreigaben vorliegen.</p>
        <div className="deck-issues" aria-busy={validating}>{validating ? <p role="status">Regeln und Bestand werden geprüft …</p> : validation.issues.map((issue, i) => <article key={i} className={`deck-issue ${issue.kind}`}><b>{issue.kind === 'rules' ? 'Deckregeln' : issue.kind === 'stock' ? 'Kartenbestand' : 'Duellfreigabe'}</b><p>{issue.message}</p>{issue.card_id && <div><NavLink to={`/cards/${issue.card_id}`}>Karte & passende Booster →</NavLink><NavLink to="/trade">Im Handel suchen →</NavLink></div>}</article>)}</div>
      </aside>
    </div>
    {preview && <OpeningCardPreview card={toCardRecord(preview)} packName={draft.name || 'Dein Deck'} contextLabel="Deck" backLabel="Zurück zum Deck" close={() => setPreview(undefined)} />}
  </div>
}
