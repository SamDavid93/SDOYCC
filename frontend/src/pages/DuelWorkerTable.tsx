import { useEffect, useRef, useState, type SyntheticEvent } from 'react'
import { API_BASE_URL, sessionToken } from '../api/transport'
import { ErrorBox } from '../components/Workflow'
import { DuelAnimations, type DuelEvent } from './DuelAnimations'
import { DuelDecisions, type WorkerPrompt, type DuelLocation } from './DuelDecisions'
import { DuelSideboard, type MatchProgress } from './DuelSideboard'
import { DuelArena } from './DuelArena'
import './duel-arena.css'
import cardBack from '../assets/card-back.jpg'

export type EngineCard = { code: number; name: string; description?: string; image_url?: string; fallback_image_url?: string; atk?: number; defense?: number }
function imageFailed(event: SyntheticEvent<HTMLImageElement>, card: EngineCard) {
  const image = event.currentTarget
  if (card.fallback_image_url && !image.dataset.fallbackAttempted) {
    image.dataset.fallbackAttempted = 'true'
    image.src = API_BASE_URL.replace(/\/api\/?$/, '') + card.fallback_image_url
  } else image.hidden = true
}
export type Side = { lp: number; deck: number; hand: (EngineCard | null)[]; field: { zone: number; sequence: number; position: number; card: EngineCard | null; materials?: EngineCard[]; counters?: number[]; disabled?: boolean; equip?: { owner: number; zone: number; sequence: number } | null; targets?: { owner: number; zone: number; sequence: number }[] }[]; grave: (EngineCard | null)[]; extra?: (EngineCard | null)[]; removed?: (EngineCard | null)[] }
type Board = { revision: number; seat: number; boards: Side[]; turn: number; turn_number: number; phase: number; ended: boolean; events: DuelEvent[]; prompt: WorkerPrompt | null }
export type WorkerResult = { id: string; state: string; seat: number; reason: string | null; winner_seat: number | null; board: Board | null; match?: MatchProgress | null; clock?: { remaining: number[]; active: number | null; side_remaining: number | null } }
const terminal = (value: WorkerResult) => ['finished', 'aborted', 'recovery_required'].includes(value.state)

export function DuelWorkerTable({ runId, onExit }: { runId: string; onExit: () => void }) {
  const [result, setResult] = useState<WorkerResult | null>(null), [error, setError] = useState('')
  const [preview, setPreview] = useState<EngineCard | null>(null)
  const [zoneSelection, setZoneSelection] = useState<number[]>([])
  const placement = useRef<DuelLocation | null>(null)
  const socket = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false), [busy, setBusy] = useState(false)
  function accept(next: WorkerResult) {
    setResult(old => old && ((terminal(old) && !terminal(next)) || (old.board && next.board && old.board.revision > next.board.revision)) ? old : next)
  }
  useEffect(() => {
    let disposed = false, done = false, attempts = 0
    let timer: ReturnType<typeof setTimeout>, heartbeat: ReturnType<typeof setInterval>
    function connect() {
      const token = sessionToken()
      if (!token) { setError('Bitte melde dich erneut an.'); return }
      const url = new URL(`${API_BASE_URL}/duel-zone/worker/runs/${runId}/socket`, window.location.href)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(url); socket.current = ws
      ws.onopen = () => {
        if (disposed) { ws.close(); return }
        ws.send(JSON.stringify({ type: 'authenticate', token }))
        heartbeat = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' })) }, 5000)
      }
      ws.onmessage = event => {
        if (disposed) return
        const message = JSON.parse(event.data)
        if (message.type === 'state') {
          accept(message.result); setConnected(true); setBusy(false); setError(''); attempts = 0
          done = terminal(message.result)
        } else if (message.type === 'error') { placement.current = null; setBusy(false); setError(message.message) }
      }
      ws.onclose = event => {
        clearInterval(heartbeat)
        if (disposed) return
        setConnected(false); setBusy(false)
        if (done) return
        if ([4401, 4403, 4404, 4400, 4429].includes(event.code)) {
          setError('Die Duellverbindung wurde abgewiesen. Prüfe deine ursprüngliche Anmeldung.'); return
        }
        setError(event.code === 4409 ? 'Dieser Spielplatz ist bereits verbunden. Verbindung wird erneut geprüft …' : 'Verbindung unterbrochen. Dein Spielstand wird wieder verbunden …')
        timer = setTimeout(connect, Math.min(5000, 500 * 2 ** attempts++))
      }
    }
    connect()
    return () => { disposed = true; clearTimeout(timer); clearInterval(heartbeat); socket.current?.close(); socket.current = null }
  }, [runId])
  useEffect(() => { if (result && terminal(result)) window.dispatchEvent(new Event('hub-data-changed')) }, [result?.state])
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setPreview(null) }; window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close) }, [])
  function send(kind: string, body: Record<string, unknown>) {
    if (!connected || busy || socket.current?.readyState !== WebSocket.OPEN) return
    setBusy(true); setError('')
    socket.current.send(JSON.stringify({ type: kind, ...body }))
  }
  const board = result?.board, prompt = board?.prompt
  const chainReaction = prompt?.kind === 'chain' || prompt?.title === 'Auf die Kette reagieren'
  useEffect(() => { setZoneSelection([]) }, [prompt?.id])
  useEffect(() => {
    if (!placement.current || busy || !connected) return
    if (result && terminal(result)) { placement.current = null; return }
    if (prompt?.choices.some(choice => choice.action)) { placement.current = null; return }
    if (prompt?.kind !== 'zones' || !prompt.placement || prompt.select) return
    const target = placement.current
    const index = prompt.choices.findIndex(choice => choice.location?.owner === target.owner && choice.location.zone === target.zone && choice.location.sequence === target.sequence)
    placement.current = null
    if (index >= 0) send('answer', { prompt: prompt.id, selected: [index] })
  }, [prompt?.id, connected, busy])
  const card = (value: EngineCard | null, key: string, covered = false) => <button key={key} className={'duel-playing-card' + (!value || covered ? ' covered' : '')} disabled={!value} onClick={() => value && setPreview(value)} aria-label={value ? value.name + ' ansehen' : 'Verdeckte Karte'}>{!value || covered ? <img src={cardBack} alt="Kartenrückseite" draggable={false} /> : <>{value.image_url && <img key={value.image_url} src={API_BASE_URL.replace(/\/api\/?$/, '') + value.image_url} alt="" loading="lazy" onError={event => imageFailed(event, value)} />}<strong>{value.name}</strong><small>{value.atk !== undefined ? `ATK ${value.atk} · DEF ${value.defense}` : 'Kartentext ansehen'}</small></>}</button>
  return <section className="duel-worker-table">
    <header className="duel-arena-toolbar"><div><p className="eyebrow accent">SDOYCC · DUELL</p><h1>Duellarena</h1></div><small>Verbindungsfrist: 60 Sekunden</small></header>
    <ErrorBox message={error} />
    <p className="duel-connection-status" role="status">{connected ? 'Mit dem Duell verbunden' : result && terminal(result) ? 'Duell abgeschlossen' : 'Duellverbindung herstellen …'}</p>
    {result?.clock && !terminal(result) && <div className="duel-turn-line" role="timer"><p>Bedenkzeit: Du {Math.ceil(result.clock.remaining[result.seat])} s · Gegner {Math.ceil(result.clock.remaining[1 - result.seat])} s</p><small>180 Sekunden je Spieler; beim eigenen neuen Zug aufgefüllt. Reaktionen verbrauchen das Restbudget. Verbindungswechsel setzen die Uhr nicht zurück.</small>{result.clock.side_remaining !== null && <p>Sideboarding: {Math.ceil(result.clock.side_remaining)} s. Wer allein nicht bereit ist, verliert das Match; fehlen beide Bestätigungen, erfolgt ein neutraler Abbruch.</p>}</div>}
    {error && !result && <button onClick={onExit}>Zur Lobby-Übersicht</button>}
    {!result && <p role="status">Privaten Spielstand laden …</p>}
    {result && terminal(result) && <div className="deck-panel duel-worker-result" role="status"><h2>{result.state === 'finished' ? result.winner_seat === null ? 'Unentschieden' : result.winner_seat === result.seat ? 'Du hast gewonnen' : 'Du hast verloren' : result.state === 'recovery_required' ? 'Betriebsprüfung erforderlich' : 'Testduell abgebrochen'}</h2><p>{result.state === 'recovery_required' ? 'Die Worker-Verbindung wurde nach einem Serverwechsel nicht übernommen. Karten bleiben bis zur sicheren Prozessprüfung reserviert.' : result.reason === 'surrender' ? 'Das Duell wurde durch Aufgabe beendet. Kartenreservierungen sind aufgehoben.' : result.state === 'aborted' ? 'Das Duell wird nicht gewertet. Der Worker wurde gestoppt und die Karten wurden freigegeben.' : 'Der Regelkern hat das Duell beendet. Deine Karten bleiben erhalten.'}</p><button onClick={onExit}>Zur Lobby-Übersicht</button></div>}
    {result?.match && <p className="duel-turn-line">Match bis zum zweiten Sieg · Spiel {result.match.game} · Du {result.match.score[result.seat]} : {result.match.score[1 - result.seat]} Gegner</p>}
    {result?.match?.phase === 'sideboarding' && <DuelSideboard match={result.match} seat={result.seat} disabled={busy || !connected} send={send} />}
    {board && result?.match?.phase !== 'sideboarding' && <>
      <DuelAnimations events={board.events} runId={runId} />
      <div className="duel-turn-line" role="status">Zug {board.turn_number} · {board.turn === board.seat ? 'Du bist am Zug' : 'Dein Gegner ist am Zug'} · {({ 1: 'Ziehphase', 2: 'Vorbereitungsphase', 4: 'Hauptphase 1', 8: 'Kampfphase', 16: 'Kampfphase', 32: 'Kampfphase', 64: 'Kampfphase', 256: 'Hauptphase 2', 512: 'Endphase' } as Record<number, string>)[board.phase] || 'Phasenwechsel'}</div>
      <div className="duel-arena-shell">
        <aside className="duel-card-inspector" aria-label="Kartenvorschau">
          {preview ? <><button className="outline-button" onClick={() => setPreview(null)}>Vorschau schließen</button><h2>{preview.name}</h2>
            {preview.image_url && <img key={preview.image_url} src={API_BASE_URL.replace(/\/api\/?$/, '') + preview.image_url} alt={preview.name} onError={event => imageFailed(event, preview)} />}
            {preview.atk !== undefined && <p>ATK {preview.atk} · DEF {preview.defense ?? '—'}</p>}
            <small>Kartentext</small><p className="duel-card-description">{preview.description || 'Für diese Karte ist kein Text verfügbar.'}</p></>
            : <div className="duel-inspector-empty"><span>◇</span><h2>Kartenvorschau</h2><p>Klicke eine sichtbare Karte an, um Bild und Kartentext hier zu lesen.</p></div>}
        </aside>
        <DuelArena sides={board.boards} seat={board.seat} card={card} prompt={prompt} disabled={busy || !connected || Boolean(result && terminal(result))}
          zoneSelection={zoneSelection} chooseZone={index => {
            if (!prompt) return
            if (prompt.select) setZoneSelection(old => old.includes(index) ? old.filter(value => value !== index) : [...old, index])
            else send('answer', { prompt: prompt.id, selected: [index] })
          }} chooseAction={(index, target) => {
            if (!prompt) return
            placement.current = target || null
            send('answer', { prompt: prompt.id, selected: [index] })
          }} />
      </div>
      {result && !terminal(result) && <div className={chainReaction ? 'duel-chain-overlay' : undefined} role={chainReaction ? 'region' : undefined} aria-label={chainReaction ? 'Kettenreaktion' : undefined}>
        {chainReaction && <div className="duel-chain-notice"><span aria-hidden="true">∞</span><strong>Deine Kettenreaktion</strong></div>}
        <DuelDecisions prompt={prompt} disabled={busy || !connected} send={send} zoneSelection={zoneSelection} onZoneSelection={setZoneSelection} />
      </div>}
    </>}

  </section>
}
