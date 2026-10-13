import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Copy, DoorOpen, ShieldCheck, Swords, UserRound } from 'lucide-react'
import { api } from '../api/transport'
import { useSession } from '../Session'
import { ErrorBox, useAction, useRead } from '../components/Workflow'
import './decks.css'
import { DuelWorkerTable, type WorkerResult } from './DuelWorkerTable'
import { DuelHistory } from './DuelHistory'

type DeckChoice = { id: string; name: string; profile_id: string | null; version: number; counts: { main: number; extra: number; side: number } }
type Room = { mode: 'single' | 'match'; id: string; code: string; host_id: number; state: string; version: number; expires_at: string; profile: { id: string; name: string; engine_approved: boolean; region_approved: boolean }; own_deck: DeckChoice | null; own_deck_changed: boolean; can_confirm_deck: boolean; both_decks_confirmed: boolean; can_start: boolean; start_blocker: string; worker_run_id: string | null; worker_test_available: boolean; worker_alpha?: boolean; worker_both_consented: boolean; members: { user_id: number; name: string; seat: number; accepted: boolean; deck_selected: boolean; deck_confirmed: boolean; worker_consented: boolean; deck_ready: boolean }[] }

export function DuelZone() {
  const { user } = useSession(), action = useAction()
  const [room, setRoom] = useState<Room | null>(), [error, setError] = useState(''), [tick, setTick] = useState(0)
  const [mode, setMode] = useState<'single' | 'match'>('single')
  const [deckId, setDeckId] = useState(''), [code, setCode] = useState(''), [feedback, setFeedback] = useState('')
  const runKey = 'sdoycc-test-duel:' + user?.id
  const [runId, setRunId] = useState<string | null>(() => sessionStorage.getItem(runKey))
  const decks = useRead<DeckChoice[]>('/decks', tick)
  useEffect(() => {
    const ctrl = new AbortController()
    let pending = false
    async function refresh() {
      if (pending) return
      pending = true
      try { const result = await api<Room | null>('/duel-zone/me', { signal: ctrl.signal }); if (!ctrl.signal.aborted) { setRoom(old => old?.id === result?.id && old && result && old.version > result.version ? old : result); setError('') } }
      catch (cause) { if (!ctrl.signal.aborted) setError((cause as Error).message) }
      finally { pending = false }
    }
    void refresh(); const timer = setInterval(() => void refresh(), 4000)
    return () => { ctrl.abort(); clearInterval(timer) }
  }, [tick])
  useEffect(() => { if (room?.worker_run_id) { setRunId(room.worker_run_id); sessionStorage.setItem(runKey, room.worker_run_id) } }, [room?.worker_run_id, runKey])
  async function command(path: string, body: unknown) {
    const result = await action.run<Room | { left: boolean }>(path, body)
    if (result) { setRoom(old => 'left' in result ? null : old?.id === result.id && old.version > result.version ? old : result); setFeedback(''); setTick(n => n+1) }
  }
  const ownSeat = room?.members.find(member => member.user_id === user?.id)
  const guest = room?.members.find(member => member.seat === 1)
  const host = room?.host_id === user?.id
  const choices = decks.data?.filter(deck => deck.profile_id && (!room || deck.profile_id === room.profile.id)) || []
  const selected = choices.find(deck => deck.id === deckId)
  const deckSelect = <label>Dein Deck<select aria-label="Dein Deck" value={room ? ownSeat?.deck_ready ? room.own_deck?.id || '' : '' : selected?.id || ''} onChange={e => {
    const value = e.target.value
    if (room) void command(`/duel-zone/lobbies/${room.id}/deck`, { version: room.version, deck_id: value || null, ready: Boolean(value) })
    else setDeckId(value)
  }} disabled={action.busy || Boolean(room && (!ownSeat?.accepted || room.state === 'expired'))}><option value="">Deck auswählen</option>{choices.map(deck => <option key={deck.id} value={deck.id}>{deck.name} · {deck.counts.main}/{deck.counts.extra}/{deck.counts.side}</option>)}</select></label>
  if (runId) return <div className="page-wrap decks-page"><DuelWorkerTable key={runId} runId={runId} onExit={() => { sessionStorage.removeItem(runKey); setRunId(null); setRoom(null); setTick(n => n+1) }} /></div>
  return <div className="page-wrap decks-page duel-zone-page">
    <section className="deck-hero"><div><p className="eyebrow accent">EIN RAUM. ZWEI STRATEGIEN.</p><h1>DuelZone</h1><p>Eröffne eine private Lobby und lade deinen Gegner mit einem Raumcode ein. Deine Deckliste bleibt dabei privat.</p></div><Swords className="deck-hero-symbol" size={90} /></section>
    <p className="deck-phase-note">Deck auswählen, Gast annehmen und <strong>Match starten</strong>. Eure Karten werden erst beim Start reserviert.</p>
    <ErrorBox message={error || action.error || decks.error} /><DuelHistory />
    {!user?.twitch_id && <p className="deck-warning">Lobbys benötigen ein registriertes Twitch-Konto. Die lokale Demo kann weiterhin Deckentwürfe erstellen.</p>}
    {room === undefined ? <p role="status">Deine Lobby wird geladen …</p> : !room ? <div className="duel-entry-grid">
      <form className="deck-panel" onSubmit={e => { e.preventDefault(); if (selected) void command('/duel-zone/lobbies', { deck_id: selected.id, mode, ready: true }) }}><Swords size={26} /><h2>Deine Lobby eröffnen</h2><p>Wähle dein Deck. Der Regelstand gilt für beide Spieler.</p>{deckSelect}<label>Spielmodus<select value={mode} onChange={event => setMode(event.target.value as 'single' | 'match')}><option value="single">Einzelduell</option><option value="match">Match bis zum zweiten Sieg</option></select></label><button className="primary-button" disabled={action.busy || !selected || !user?.twitch_id}>Private Lobby erstellen</button>{choices.length === 0 && <p>Du benötigst zunächst ein aktives Deck mit Regelstand.</p>}<NavLink to="/decks">Meine Decks bearbeiten →</NavLink></form>
      <form className="deck-panel" onSubmit={e => { e.preventDefault(); void command('/duel-zone/join', { code: code.trim().toUpperCase() }) }}><DoorOpen size={26} /><h2>Einer Lobby beitreten</h2><p>Dein Gegner teilt den Raumcode mit dir und bestätigt anschließend deinen Platz.</p><label>Lobby-Code<input value={code} onChange={e => setCode(e.target.value.toUpperCase())} maxLength={13} minLength={8} placeholder="SDO-7K4P-9M2R" required autoComplete="off" /></label><button className="primary-button" disabled={action.busy || !user?.twitch_id}>Beitreten</button></form>
    </div> : <section className="duel-room">
      <header className="duel-room-heading"><div><p className="eyebrow accent">DEINE PRIVATE LOBBY</p><h2>{room.code}</h2><p>{room.profile.name} · {room.mode === 'match' ? 'Match bis zum zweiten Sieg' : 'Einzelduell'}</p></div><div className="deck-actions"><button onClick={() => { void navigator.clipboard.writeText(room.code).then(() => setFeedback('Lobby-Code kopiert.')).catch(() => setFeedback('Bitte den angezeigten Code markieren und kopieren.')) }}><Copy size={16} />Code kopieren</button><button disabled={action.busy} onClick={() => { if (!host || window.confirm('Lobby schließen? Dein Gegner verlässt dadurch ebenfalls den Raum.')) void command(`/duel-zone/lobbies/${room.id}/leave`, { version: room.version }) }}>{host ? 'Lobby schließen' : 'Lobby verlassen'}</button></div></header>
      {feedback && <p role="status">{feedback}</p>}
      {room.state === 'expired' && <p className="api-notice" role="alert">Die Lobby ist abgelaufen oder eine Anmeldung wurde beendet. Verlasse sie, um neu zu beginnen.</p>}
      <div className="duel-seats">{[0, 1].map(position => { const member = room.members.find(item => item.seat === position); return <article className="deck-panel duel-seat" key={position}><div className="duel-avatar"><UserRound size={36} /></div><p className="eyebrow">{position === 0 ? 'GASTGEBER' : 'HERAUSFORDERER'}</p><h3>{member?.name || 'Platz frei'}</h3><p>{!member ? 'Teile deinen Lobby-Code.' : member.accepted ? 'Teilnahme angenommen' : 'Wartet auf Gastgeber'}</p>{member && <span><ShieldCheck size={15} />{member.deck_ready ? 'Bereit · Deck ausgewählt' : 'Deckauswahl offen'}</span>}{position === 1 && host && guest && <div className="deck-actions">{!guest.accepted && <button disabled={action.busy || room.state === 'expired'} onClick={() => void command(`/duel-zone/lobbies/${room.id}/guest`, { version: room.version, accept: true })}>Gast bestätigen</button>}<button disabled={action.busy || room.state === 'expired'} onClick={() => void command(`/duel-zone/lobbies/${room.id}/guest`, { version: room.version, accept: false })}>Gast entfernen</button></div>}</article> })}</div>
      <div className="deck-panel duel-own-deck"><h2>Dein Deck</h2><p>{room.own_deck ? room.own_deck.name : 'Noch kein Deck ausgewählt.'}</p>{room.own_deck_changed && <p className="deck-warning">Dein Deck wurde verändert oder archiviert. Wähle einen aktuellen, passenden Entwurf.</p>}{!ownSeat?.accepted && <p>Warte darauf, dass der Gastgeber dich annimmt.</p>}{deckSelect}{room.own_deck && <NavLink to={'/decks/' + room.own_deck.id}>Deck ansehen →</NavLink>}<p className="duel-privacy-note">Die Auswahl wird sofort gespeichert. Zum Zurücknehmen wähle den leeren Eintrag. Dein Gegner sieht nur, ob dein Deck ausgewählt ist.</p></div>
      <div className="duel-start-note"><Swords size={24} /><div><h3>{room.can_start ? 'Bereit für den Matchstart' : 'Noch nicht startbereit'}</h3><p>{room.start_blocker || (host ? 'Beide Spieler sind bereit. Du kannst das Match starten.' : 'Beide Spieler sind bereit. Warte auf den Start durch den Gastgeber.')}</p><small>Lobby gültig bis {new Date(room.expires_at).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}. Die Deckregeln und der Kartenbestand werden beim Start erneut geprüft.</small>{host && <button className="primary-button" disabled={action.busy || !room.can_start} onClick={() => {
        void action.run<WorkerResult>('/duel-zone/worker/start', { lobby_id: room.id, version: room.version }).then(value => { if (value) { setRunId(value.id); sessionStorage.setItem(runKey, value.id) } })
      }}>Match starten</button>}</div></div>
    </section>}
  </div>
}
