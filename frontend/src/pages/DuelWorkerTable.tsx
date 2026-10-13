import { useCallback, useEffect, useRef, useState, type SyntheticEvent } from 'react'
import { API_BASE_URL, sessionToken } from '../api/transport'
import { ErrorBox } from '../components/Workflow'
import { DuelAnimations, type DuelEvent } from './DuelAnimations'
import { DuelDecisions, type WorkerPrompt, type DuelLocation } from './DuelDecisions'
import { DuelSideboard, type MatchProgress } from './DuelSideboard'
import { DuelArena } from './DuelArena'
import { duelPhaseName } from './DuelPhaseControl'
import { effectAvailableAt } from './duelFeedback'
import { includeChoice, selectionComplete } from './duelSelection'
import './duel-arena.css'
import './duel-premium.css'
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
export type WorkerResult = { practice?: boolean; id: string; state: string; seat: number; reason: string | null; winner_seat: number | null; board: Board | null; match?: MatchProgress | null; clock?: { remaining: number[]; active: number | null; side_remaining: number | null; limit?: number; refill_ratio?: number; recovered?: number[] } }
const terminal = (value: WorkerResult) => ['finished', 'aborted', 'recovery_required'].includes(value.state)

export function DuelWorkerTable({ runId, onExit }: { runId: string; onExit: () => void }) {
  const [result, setResult] = useState<WorkerResult | null>(null), [error, setError] = useState('')
  const [preview, setPreview] = useState<EngineCard | null>(null)
  const [zoneSelection, setZoneSelection] = useState<number[]>([])
  const selectionClick = useRef<{ prompt: number; index: number; before: number[] } | null>(null)
  const [activeLocation, setActiveLocation] = useState<DuelLocation | null>(null)
  const [pendingAttack, setPendingAttack] = useState<number | null>(null)
  const [attackFlow, setAttackFlow] = useState(false)
  const attackStartedAfter = useRef(0)
  const [previewEffect, setPreviewEffect] = useState<string | null>(null)
  const showEffect = useCallback((card: EngineCard, effect?: string | null) => { setPreview(card); setPreviewEffect(effect || 'Effekt aktiviert') }, [])
  const placement = useRef<DuelLocation | null>(null)
  const finishSelectionAfter = useRef<number | null>(null)
  const socket = useRef<WebSocket | null>(null)
  const pendingCommand = useRef<{ revision: number; prompt?: number } | null>(null)
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
          accept(message.result); setConnected(true); setError(''); attempts = 0
          const pending = pendingCommand.current
          if (!pending || message.ack || terminal(message.result) || message.result.board?.revision > pending.revision || message.result.board?.prompt?.id !== pending.prompt) {
            pendingCommand.current = null; setBusy(false)
          }
          done = terminal(message.result)
        } else if (message.type === 'error') { placement.current = null; finishSelectionAfter.current = null; pendingCommand.current = null; setBusy(false); setError(message.message) }
      }
      ws.onclose = event => {
        clearInterval(heartbeat)
        if (disposed) return
        setConnected(false); setBusy(false)
        pendingCommand.current = null
        finishSelectionAfter.current = null
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
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === 'Escape') { setPreview(null); setActiveLocation(null); setPendingAttack(null) } }; window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close) }, [])
  function send(kind: string, body: Record<string, unknown>, finishSelection = false) {
    if (!connected || busy || pendingCommand.current || socket.current?.readyState !== WebSocket.OPEN) return
    pendingCommand.current = { revision: result?.board?.revision || 0, prompt: result?.board?.prompt?.id }
    setBusy(true); setError('')
    if (finishSelection && typeof body.prompt === 'number') finishSelectionAfter.current = body.prompt
    socket.current.send(JSON.stringify({ type: kind, ...body }))
  }
  const board = result?.board, prompt = board?.prompt
  useEffect(() => {
    if (finishSelectionAfter.current === null || !prompt || prompt.id <= finishSelectionAfter.current || busy || !connected) return
    finishSelectionAfter.current = null
    if (prompt.selection_progress?.can_finish && prompt.cancel) send('answer', { prompt: prompt.id, selected: [], cancel: true })
  }, [prompt?.id, busy, connected])
  useEffect(() => { if (board?.events.some(event => event.kind === 'attack' && event.id > attackStartedAfter.current)) setAttackFlow(false) }, [board?.revision])
  const chainReaction = prompt?.kind === 'chain' || prompt?.title === 'Auf die Kette reagieren'
  useEffect(() => { setZoneSelection(prompt?.counter ? prompt.choices.map(() => 0) : []); setActiveLocation(null); setPendingAttack(null); if (prompt?.title === 'Aktion wählen') setAttackFlow(false) }, [prompt?.id])
  const disabled = busy || !connected || Boolean(result && terminal(result))
  function choicesAt(location: DuelLocation) { return prompt?.choices.map((choice, index) => ({ choice, index })).filter(({choice}) => choice.location?.owner === location.owner && choice.location.zone === location.zone && choice.location.sequence === location.sequence) || [] }
  function chooseLocation(location: DuelLocation, complete = false) {
    if (disabled || !prompt) return
    const options = choicesAt(location)
    if (!options.length) return
    const side = board!.boards[location.owner]
    const shown = location.zone === 2 ? side.hand[location.sequence] : location.zone === 64 ? side.extra?.[location.sequence] : location.zone === 16 ? side.grave[location.sequence] : location.zone === 32 ? side.removed?.[location.sequence] : side.field.find(entry => entry.zone === location.zone && entry.sequence === location.sequence)?.card
    if (shown) { setPreview(shown); setPreviewEffect(null) }
    if (prompt.select && options.length === 1) {
      setActiveLocation(location)
      const index = options[0].index
      if (complete) {
        const before = selectionClick.current?.prompt === prompt.id && selectionClick.current.index === index ? selectionClick.current.before : zoneSelection
        const next = includeChoice(before, index, prompt.maximum || 0)
        setZoneSelection(next)
        if (next.includes(index) && selectionComplete(next, prompt.minimum || 0, prompt.maximum || 0)) send('answer', { prompt: prompt.id, selected: next })
      } else {
        selectionClick.current = { prompt: prompt.id, index, before: [...zoneSelection] }
        setZoneSelection(old => old.includes(index) ? old.filter(value => value !== index) : includeChoice(old,index,prompt.maximum || 0))
      }
    } else if (options.length === 1 && options[0].choice.action === 'attack') {
      setActiveLocation(null); setPendingAttack(options[0].index)
    } else setActiveLocation(location)
  }
  function chooseAction(index: number, target?: DuelLocation) {
    if (!prompt || disabled) return
    if (prompt.choices[index]?.action === 'attack') { setActiveLocation(null); setPendingAttack(index); return }
    placement.current = target || null
    send('answer', { prompt: prompt.id, selected: [index] })
  }
  const phaseLabels = ['Kampfphase','Hauptphase 2','Zug beenden']
  const freeChoices = prompt?.choices.map((choice,index)=>({choice,index})).filter(({choice})=>!choice.location && !phaseLabels.includes(choice.label)).map(({index})=>index) || []
  const pileChoices = activeLocation && ![2,4,8].includes(activeLocation.zone & 127) ? choicesAt(activeLocation).map(({index})=>index) : []
  const showDecision = !!prompt && (prompt.title !== 'Aktion wählen' || freeChoices.length > 0 || pileChoices.length > 0)
  const selectOnField = !!prompt?.select && prompt.choices.every(choice => choice.location && [2,4,8].includes(choice.location.zone)) && new Set(prompt.choices.map(choice=>`${choice.location?.owner}:${choice.location?.zone}:${choice.location?.sequence}`)).size === prompt.choices.length
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
  const card = (value: EngineCard | null, key: string, covered = false, location?: DuelLocation) => <button key={key} className={'duel-playing-card' + (!value || covered ? ' covered' : '') + (location && !disabled && effectAvailableAt(prompt,location) ? ' effect-available' : '')} disabled={!value && !(location && choicesAt(location).length && !disabled)} onClick={event => { if (event.detail > 1) return; if (value) { setPreview(value); setPreviewEffect(null) } if (location) chooseLocation(location) }} onDoubleClick={() => { if (location && prompt?.select) chooseLocation(location,true) }} aria-label={value ? value.name + ' ansehen' : 'Verdeckte Karte'}>{!value || covered ? <img src={cardBack} alt="Kartenrückseite" draggable={false} /> : <>{value.image_url && <img key={value.image_url} src={API_BASE_URL.replace(/\/api\/?$/, '') + value.image_url} alt="" loading="lazy" onError={event => imageFailed(event, value)} />}<strong>{value.name}</strong><small>{value.atk !== undefined ? `ATK ${value.atk} · DEF ${value.defense}` : 'Kartentext ansehen'}</small></>}</button>
  return <section className={'duel-worker-table' + (board && result && !terminal(result) && result.match?.phase !== 'sideboarding' ? ' is-playing' : '')}>
    <ErrorBox message={error} />
    <p className="duel-connection-status" role="status">{connected ? result?.practice ? 'Admin-Testduell · Test-KI · Keine Belohnungen' : 'Mit dem Duell verbunden' : result && terminal(result) ? 'Duell abgeschlossen' : 'Duellverbindung herstellen …'}</p>
    {error && !result && <button onClick={onExit}>Zur Lobby-Übersicht</button>}
    {!result && <p role="status">Privaten Spielstand laden …</p>}
    {result && terminal(result) && <div className="deck-panel duel-worker-result" role="status"><h2>{result.state === 'finished' ? result.winner_seat === null ? 'Unentschieden' : result.winner_seat === result.seat ? 'Du hast gewonnen' : 'Du hast verloren' : result.state === 'recovery_required' ? 'Betriebsprüfung erforderlich' : 'Testduell abgebrochen'}</h2><p>{result.state === 'recovery_required' ? 'Die Worker-Verbindung wurde nach einem Serverwechsel nicht übernommen. Karten bleiben bis zur sicheren Prozessprüfung reserviert.' : result.reason === 'surrender' ? 'Das Duell wurde durch Aufgabe beendet. Kartenreservierungen sind aufgehoben.' : result.state === 'aborted' ? 'Das Duell wird nicht gewertet. Der Worker wurde gestoppt und die Karten wurden freigegeben.' : 'Der Regelkern hat das Duell beendet. Deine Karten bleiben erhalten.'}</p><button onClick={onExit}>Zur Lobby-Übersicht</button></div>}
    {result?.match && <p className="duel-turn-line">Match bis zum zweiten Sieg · Spiel {result.match.game} · Du {result.match.score[result.seat]} : {result.match.score[1 - result.seat]} Gegner</p>}
    {result?.match?.phase === 'sideboarding' && result.clock?.side_remaining != null && <p role="timer">Sideboarding: noch {Math.ceil(result.clock.side_remaining)} s</p>}
    {result?.match?.phase === 'sideboarding' && <DuelSideboard match={result.match} seat={result.seat} disabled={busy || !connected} send={send} />}
    {board && result?.match?.phase !== 'sideboarding' && <>
      <div className="duel-arena-shell">
        <aside className="duel-card-inspector" aria-label="Kartenvorschau">
          {preview ? <><button className="outline-button" onClick={() => setPreview(null)}>Vorschau schließen</button><h2>{preview.name}</h2>
            {preview.image_url && <img key={preview.image_url} src={API_BASE_URL.replace(/\/api\/?$/, '') + preview.image_url} alt={preview.name} onError={event => imageFailed(event, preview)} />}
            {preview.atk !== undefined && <p>ATK {preview.atk} · DEF {preview.defense ?? '—'}</p>}
            {previewEffect && <p className="duel-inspector-effect" role="status">✦ {previewEffect}</p>}
            <small>Kartentext</small><p className="duel-card-description">{preview.description || 'Für diese Karte ist kein Text verfügbar.'}</p></>
            : <div className="duel-inspector-empty"><span>◇</span><h2>Kartenvorschau</h2><p>Klicke eine sichtbare Karte an, um Bild und Kartentext hier zu lesen.</p></div>}
        </aside>
        <DuelArena sides={board.boards} seat={board.seat} card={card} prompt={prompt} disabled={busy || !connected || Boolean(result && terminal(result))}
          activeLocation={activeLocation} chooseLocation={chooseLocation}
          selectionValid={zoneSelection.length >= (prompt?.minimum || 0) && zoneSelection.length <= (prompt?.maximum || 0)} selectionLabel={attackFlow ? 'Angriff bestätigen' : 'Auswahl bestätigen'} confirmSelection={()=>prompt && send('answer',{prompt:prompt.id,selected:zoneSelection})}
          phase={board.phase} turn={board.turn} turnNumber={board.turn_number}
          zoneSelection={zoneSelection} chooseZone={index => {
            if (!prompt) return
            if (prompt.select) setZoneSelection(old => old.includes(index) ? old.filter(value => value !== index) : [...old, index])
            else send('answer', { prompt: prompt.id, selected: [index] })
          }} chooseAction={chooseAction}>
          <div className="arena-hud" role="status"><span>Zug {board.turn_number} · {board.turn === board.seat ? 'Dein Zug' : 'Gegnerischer Zug'} · {duelPhaseName(board.phase)}</span>{result?.clock && <span role="timer" title="360 Sekunden Zeitkonto. 50 % der gegnerischen Entscheidungszeit werden gutgeschrieben, bis maximal 360 Sekunden.">Du {Math.ceil(result.clock.remaining[result.seat])} s · Gegner {Math.ceil(result.clock.remaining[1-result.seat])} s</span>}</div>
          <DuelAnimations events={board.events} runId={runId} onEffect={showEffect} seat={board.seat} phase={board.phase} turn={board.turn} turnNumber={board.turn_number} disabled={disabled} surrender={() => { if(window.confirm('Duell wirklich aufgeben?')) send('surrender',{}) }} />
          {pendingAttack !== null && prompt && <section className="arena-attack-confirm" role="dialog" aria-label="Angriff vorbereiten"><h2>⚔ Angriff starten?</h2><p>{prompt.choices[pendingAttack]?.card?.name || 'Dein Monster'} soll angreifen. Danach wählst du ein erlaubtes Ziel.</p><button disabled={disabled} onClick={()=>{ attackStartedAfter.current = Math.max(0,...board.events.map(event=>event.id)); setAttackFlow(true); send('answer',{prompt:prompt.id,selected:[pendingAttack]}); setPendingAttack(null) }}>Angriff starten</button><button onClick={()=>setPendingAttack(null)}>Abbrechen</button></section>}
          {!showDecision && pendingAttack === null && !disabled && <p className="arena-action-guide">{prompt ? 'Markierte Karte anklicken · Phasenwechsel über den Kreis' : 'Dein Gegner entscheidet …'}</p>}
          {showDecision && result && !terminal(result) && <div className={chainReaction ? 'duel-chain-overlay' : 'arena-decision-overlay' + (selectOnField || prompt?.kind === 'zones' ? ' arena-field-selection-guide' : '')} role={chainReaction ? 'region' : undefined} aria-label={chainReaction ? 'Kettenreaktion' : undefined}>
            {chainReaction && <div className="duel-chain-notice"><span aria-hidden="true">∞</span><strong>Deine Kettenreaktion</strong></div>}
            <DuelDecisions prompt={prompt} disabled={disabled} send={send} zoneSelection={zoneSelection} onZoneSelection={setZoneSelection} hideChoices={selectOnField || prompt?.kind === 'zones'} hideConfirmation={selectOnField && zoneSelection.length > 0} hideSurrender attackTarget={attackFlow && Boolean(prompt?.select)} choiceIndices={prompt?.title === 'Aktion wählen' ? pileChoices.length ? pileChoices : freeChoices : undefined} />
          </div>}
        </DuelArena>
      </div>
    </>}

  </section>
}
