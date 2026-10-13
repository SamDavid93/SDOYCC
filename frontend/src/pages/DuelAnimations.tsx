import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '../api/transport'
import type { EngineCard } from './DuelWorkerTable'
import { phaseAnnouncement } from './duelFeedback'
import { DuelSoundPlayer } from './duelSounds'

type Location = { owner: number; zone: number; sequence: number }
export type DuelEvent = { id: number; kind: string; added?: boolean; delta?: number; affected_cards?: { role: string; name: string }[]; direct?: boolean; card?: EngineCard; effect?: string | null; player?: number; count?: number; value?: number; phase?: number; number?: number; step?: number; code?: number; text?: string; method?: string; values?: number[]; cards?: { name: string }[]; before?: Location & { position?: number }; after?: Location & { position?: number }; source?: Location; target?: Location; attacker?: Location; defender?: Location; location?: Location }
type Mode = 'full' | 'fast' | 'reduced'
const captions: Record<string, string> = { draw: 'Karte gezogen', move: 'Karte bewegt', position: 'Position geändert',
  turn: 'Neuer Spielzug', turn_end: 'Zug beendet', phase_request: 'Beendet Zug', phase: 'Phasenwechsel', lp: 'Lebenspunkte geändert', summon: 'Beschwörung',
  chain: 'Effekt aktiviert', chain_step: 'Kette', attack: 'Angriff', win: 'Duell beendet',
  shuffle: 'Deck gemischt', destroy: 'Karte zerstört', banish: 'Karte verbannt', coin: 'Münzwurf', dice: 'Würfelwurf', negate: 'Effekt negiert',
  control: 'Kontrolle gewechselt', material: 'Material bewegt', token: 'Spielmarke erzeugt', counter: 'Zählmarken geändert',
  equip: 'Ausrüstung verbunden', unequip: 'Ausrüstung gelöst', target: 'Ziel markiert', untarget: 'Ziel gelöst', reveal: 'Karten aufgedeckt', zones: 'Zonensperre geändert', hint: 'Engine-Hinweis' }
const methods: Record<string, string> = { normal: 'Normal-/Tributbeschwörung', flip: 'Flippbeschwörung', special: 'Spezialbeschwörung', fusion: 'Fusion', synchro: 'Synchro', xyz: 'Xyz', link: 'Link', ritual: 'Ritual', pendulum: 'Pendel', covered: 'Verdeckte Beschwörung' }
const chainSteps: Record<number, string> = { 71: 'Kette fortgesetzt', 72: 'Effekt wird aufgelöst', 73: 'Effekt aufgelöst', 74: 'Kette beendet', 75: 'Aktivierung negiert', 76: 'Effekt negiert' }

function Motion({ event, mode }: { event: DuelEvent; mode: Mode }) {
  if (mode === 'reduced') return null
  const point = (location?: Location) => {
    if (!location) return null
    const base = `[data-duel-owner="${location.owner}"][data-duel-zone="${location.zone & 127}"]`
    const element = document.querySelector(`${base}[data-duel-sequence="${location.sequence}"]`) || document.querySelector(base)
    if (!element) return null
    const rect = element.getBoundingClientRect()
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
  }
  const from = point(event.before || event.attacker || event.source || (event.kind === 'draw' ? { owner: event.player!, zone: 1, sequence: 0 } : event.location))
  const to = point(event.after || event.defender || event.target || (event.kind === 'draw' ? { owner: event.player!, zone: 2, sequence: 0 } : event.location))
  if (!from || !to) return null
  const seconds = mode === 'full' ? '.65s' : '.18s'
  return <svg className="duel-motion-layer" aria-hidden="true"><defs><marker id="duel-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#f8cd76" /></marker></defs>
    {['attack', 'target', 'equip'].includes(event.kind) ? <path d={`M${from.x} ${from.y} L${to.x} ${to.y}`} stroke="#f8cd76" strokeWidth="5" markerEnd="url(#duel-arrow)" /> :
      <g><rect x="-20" y="-28" width="40" height="56" rx="4" fill="#44291e" stroke="#e4bc71" strokeWidth="3" /><text y="4" textAnchor="middle" fill="#f8cd76" fontSize="12">SDO</text><animateMotion dur={seconds} path={`M${from.x} ${from.y} L${to.x} ${to.y}`} fill="freeze" /></g>}
    <circle cx={to.x} cy={to.y} r="12" fill="none" stroke="#80e8ff" strokeWidth="3"><animate attributeName="r" from="12" to="60" dur={seconds} /><animate attributeName="opacity" from="1" to="0" dur={seconds} /></circle>
  </svg>
}

export function DuelAnimations({ events, runId, onEffect, seat, disabled, surrender, phase, turn, turnNumber }: { events: DuelEvent[]; runId: string; phase?: number; turn?: number; turnNumber?: number;
  onEffect?: (card: EngineCard, effect?: string | null) => void; seat?: number; disabled?: boolean; surrender?: () => void }) {
  const [mode, setMode] = useState<Mode>(() => {
    const stored = localStorage.getItem('duel-motion')
    return stored === 'full' || stored === 'fast' || stored === 'reduced' ? stored : matchMedia('(prefers-reduced-motion: reduce)').matches ? 'reduced' : 'full'
  })
  const [sound, setSound] = useState(() => localStorage.getItem('duel-sound') !== 'off'), [active, setActive] = useState<DuelEvent | null>(null)
  const [volume, setVolume] = useState(() => { const value=Number(localStorage.getItem('duel-volume') ?? '.3'); return Number.isFinite(value) ? Math.min(1,Math.max(0,value)) : .3 })
  const [queue, setQueue] = useState<DuelEvent[]>([])
  const watermark = useRef<number | null>(null), audio = useRef<DuelSoundPlayer | null>(null)
  const lastSound = useRef<number | null>(null), lastPhase = useRef<string | null>(null)
  useEffect(() => { watermark.current = null; lastSound.current=null; lastPhase.current=null; audio.current?.stop(); setQueue([]); setActive(null) }, [runId])
  useEffect(() => {
    audio.current ||= new DuelSoundPlayer()
    const player=audio.current
    return () => { player.close(); audio.current=null }
  }, [])
  useEffect(() => { audio.current?.setVolume(volume) }, [volume])
  useEffect(() => {
    if (!sound) { audio.current?.stop(); return }
    const unlock = () => { void audio.current?.unlock().catch(()=>{}) }
    document.addEventListener('pointerdown',unlock); document.addEventListener('keydown',unlock)
    return () => { document.removeEventListener('pointerdown',unlock); document.removeEventListener('keydown',unlock) }
  }, [sound])
  useEffect(() => {
    const newest = Math.max(0, ...events.map(event => event.id))
    if (watermark.current === null) {
      watermark.current = newest
      if (phase) setQueue([{id:-1,kind:'phase',phase,player:turn,number:turnNumber}])
      return
    }
    const unseen = events.filter(event => event.id > watermark.current!).sort((a, b) => a.id - b.id)
    watermark.current = Math.max(watermark.current, newest)
    if (document.hidden) return
    const shown = unseen.filter(event => {
      if (event.kind === 'information') return false
      if (event.kind !== 'phase') return true
      const phase = event.phase && event.phase >= 8 && event.phase <= 128 ? 8 : event.phase
      const key = `${event.player}:${event.number}:${phase}`
      if (lastPhase.current === key) return false
      lastPhase.current = key
      return true
    })
    if (shown.length) setQueue(old => [...old, ...shown].slice(-30))
  }, [events])
  useEffect(() => {
    if (active || !queue.length) return
    setActive(queue[0]); setQueue(old => old.slice(1))
  }, [active, queue])
  useEffect(() => {
    if (!active) return
    const timer = setTimeout(() => { if (active.kind === 'chain' && active.card) onEffect?.(active.card, active.effect); setActive(null) }, active.kind === 'chain' && active.card ? 2000 : phaseAnnouncement(active,seat) ? 1500 : mode === 'full' ? 650 : mode === 'fast' ? 180 : 80)
    return () => clearTimeout(timer)
  }, [active, mode, onEffect, seat])
  useEffect(() => {
    if (!active || lastSound.current===active.id) return
    lastSound.current=active.id
    if (sound) audio.current?.play(active)
  }, [active, sound])
  useEffect(() => {
    const catchUp = () => { if (document.hidden) { setQueue([]); setActive(null); audio.current?.stop() } }
    document.addEventListener('visibilitychange', catchUp)
    return () => document.removeEventListener('visibilitychange', catchUp)
  }, [])
  async function toggleSound() {
    localStorage.setItem('duel-sound',sound ? 'off' : 'on')
    if (!sound) { audio.current ||= new DuelSoundPlayer(); await audio.current.unlock().catch(()=>{}) }
    setSound(!sound)
  }
  const announcement = active && phaseAnnouncement(active,seat)
  return <aside className={`duel-animation-console motion-${mode}`} aria-label="Duellanimationen">
    <details className="arena-settings"><summary aria-label="Duellmenü">☰</summary><div className="arena-settings-content">
    <div className="duel-animation-controls"><label>Animationen<select value={mode} onChange={event => { const next = event.target.value as Mode; setMode(next); localStorage.setItem('duel-motion', next) }}><option value="full">Voll</option><option value="fast">Schnell</option><option value="reduced">Bewegungsarm</option></select></label>
      <button aria-pressed={sound} onClick={() => void toggleSound()}>Ton {sound ? 'an' : 'aus'}</button>
      <label>Lautstärke<input aria-label="Duell-Lautstärke" type="range" min="0" max="1" step="0.05" value={volume} onChange={event => { const next=Number(event.target.value); setVolume(next); localStorage.setItem('duel-volume',String(next)) }} /></label>
      <button disabled={!active && !queue.length} onClick={() => { setQueue([]); setActive(null); audio.current?.stop() }}>Animationen überspringen</button>
    </div>
    {surrender && <button className="duel-surrender" disabled={disabled} onClick={surrender}>Duell aufgeben</button>}
    <a href={`${import.meta.env.BASE_URL}duel-sounds/CREDITS.md`} target="_blank" rel="noreferrer">Soundquellen</a>
    <button onClick={event => { const field=event.currentTarget.closest('.duel-worker-table'); if (document.fullscreenElement) void document.exitFullscreen(); else if(field) void field.requestFullscreen().catch(()=>{}) }}>Spielfeld im Vollbild</button>
    <details><summary>Bestätigtes Duellprotokoll</summary><ol className="duel-event-log">{events.filter(event => event.kind !== 'information').map(event => <li key={event.id}>#{event.id} {event.kind === 'summon' ? methods[event.method || 'special'] : event.kind === 'chain_step' ? chainSteps[event.step || 0] || 'Kette' : captions[event.kind] || event.kind}{event.number ? ` · ${event.number}` : ''}{event.value !== undefined ? ` · ${event.value}` : ''}{event.values ? ` · ${event.values.join(', ')}` : ''}{event.text ? ` · ${event.text}` : ''}{event.card ? ` · ${event.card.name}` : ''}{event.affected_cards?.map((card,index) => <span key={index}> · {card.role}: {card.name}</span>)}{event.direct ? ' · Direkter Angriff' : ''}{event.cards ? ` · ${event.cards.map(card => card.name).join(', ')}` : ''}</li>)}</ol></details>
    </div></details>
    {active && <Motion key={`motion:${active.id}`} event={active} mode={mode} />}
    {announcement && <section className={'arena-phase-announcement ' + (announcement.own ? 'is-own-turn' : 'is-opponent-turn')} role="status" aria-label="Phasenwechsel" key={`phase:${active!.id}`}><small>{announcement.detail}</small><strong>{announcement.title}</strong></section>}
    {active?.kind === 'chain' && active.card && <section className="duel-effect-reveal" role="status" aria-label="Aktivierter Karteneffekt" key={`effect:${active.id}`}>
      <span>{active.source?.owner === seat ? 'Dein Effekt' : 'Gegner aktiviert'} · Kettenglied {active.number}</span>
      {active.card.image_url && <img src={API_BASE_URL.replace(/\/api\/?$/, '') + active.card.image_url} alt={active.card.name} onError={event => { const img=event.currentTarget; if(active.card?.fallback_image_url && !img.dataset.fallback){img.dataset.fallback='1';img.src=API_BASE_URL.replace(/\/api\/?$/, '')+active.card.fallback_image_url}else img.hidden=true }} />}
      <strong>{active.card.name}</strong>{active.effect && <small>{active.effect}</small>}
    </section>}
    {active && !announcement && !(active.kind === 'chain' && active.card) && <div className={`duel-event-stage event-${active?.kind || 'idle'} summon-${active?.method || 'none'}`} key={`event:${active?.id || 'idle'}`} aria-live="polite">
      <span className="duel-event-symbol" aria-hidden="true">{active?.kind === 'attack' ? '⚔' : active?.kind === 'summon' ? '✦' : active?.kind === 'chain' ? '∞' : active?.kind === 'lp' ? '♥' : '◇'}</span>
      <span>{active ? active.kind === 'summon' ? methods[active.method || 'special'] : captions[active.kind] || 'Spielereignis' : 'Bereit für dein Duell'}{active?.kind === 'lp' && ` · ${active.value?.toLocaleString('de-DE')} LP`}{active?.kind === 'chain_step' && ` · ${active.number ? 'Glied ' + active.number + ': ' : ''}${active.step === 72 ? 'wird aufgelöst' : active.step === 73 ? 'aufgelöst' : active.step === 74 ? 'beendet' : active.step === 75 || active.step === 76 ? 'negiert' : 'fortgesetzt'}`}{active?.values && ` · ${active.values.join(', ')}`}{active?.text && ` · ${active.text}`}{active?.cards && ` · ${active.cards.map(card => card.name).join(', ')}`}</span>
    </div>}
  </aside>
}
