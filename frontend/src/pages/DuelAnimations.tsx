import { useEffect, useRef, useState } from 'react'

type Location = { owner: number; zone: number; sequence: number }
export type DuelEvent = { id: number; kind: string; player?: number; count?: number; value?: number; phase?: number; number?: number; step?: number; code?: number; text?: string; method?: string; values?: number[]; cards?: { name: string }[]; before?: Location; after?: Location; source?: Location; target?: Location; attacker?: Location; defender?: Location; location?: Location }
type Mode = 'full' | 'fast' | 'reduced'
const captions: Record<string, string> = { draw: 'Karte gezogen', move: 'Karte bewegt', position: 'Position geändert',
  turn: 'Neuer Spielzug', phase: 'Phasenwechsel', lp: 'Lebenspunkte geändert', summon: 'Beschwörung',
  chain: 'Effekt aktiviert', chain_step: 'Kette', attack: 'Angriff', win: 'Duell beendet',
  shuffle: 'Deck gemischt', destroy: 'Karte zerstört', banish: 'Karte verbannt', coin: 'Münzwurf', dice: 'Würfelwurf', negate: 'Effekt negiert',
  control: 'Kontrolle gewechselt', material: 'Material bewegt', token: 'Spielmarke erzeugt', counter: 'Zählmarken geändert',
  equip: 'Ausrüstung verbunden', unequip: 'Ausrüstung gelöst', target: 'Ziel markiert', untarget: 'Ziel gelöst', reveal: 'Karten aufgedeckt', zones: 'Zonensperre geändert', hint: 'Engine-Hinweis' }
const methods: Record<string, string> = { normal: 'Normal-/Tributbeschwörung', flip: 'Flippbeschwörung', special: 'Spezialbeschwörung', fusion: 'Fusion', synchro: 'Synchro', xyz: 'Xyz', link: 'Link', ritual: 'Ritual', pendulum: 'Pendel', covered: 'Verdeckte Beschwörung' }

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

export function DuelAnimations({ events, runId }: { events: DuelEvent[]; runId: string }) {
  const [mode, setMode] = useState<Mode>(() => {
    const stored = localStorage.getItem('duel-motion')
    return stored === 'full' || stored === 'fast' || stored === 'reduced' ? stored : matchMedia('(prefers-reduced-motion: reduce)').matches ? 'reduced' : 'full'
  })
  const [sound, setSound] = useState(false), [active, setActive] = useState<DuelEvent | null>(null)
  const [queue, setQueue] = useState<DuelEvent[]>([])
  const watermark = useRef<number | null>(null), audio = useRef<AudioContext | null>(null)
  useEffect(() => { watermark.current = null; setQueue([]); setActive(null) }, [runId])
  useEffect(() => {
    const newest = Math.max(0, ...events.map(event => event.id))
    if (watermark.current === null) { watermark.current = newest; return }
    const unseen = events.filter(event => event.id > watermark.current!).sort((a, b) => a.id - b.id)
    watermark.current = Math.max(watermark.current, newest)
    if (document.hidden) return
    if (unseen.length) setQueue(old => [...old, ...unseen].slice(-30))
  }, [events])
  useEffect(() => {
    if (active || !queue.length) return
    setActive(queue[0]); setQueue(old => old.slice(1))
  }, [active, queue])
  useEffect(() => {
    if (!active) return
    if (sound && audio.current?.state === 'running') {
      const context = audio.current, oscillator = context.createOscillator(), gain = context.createGain()
      oscillator.type = 'sine'; oscillator.frequency.value = active.kind === 'attack' ? 170 : active.kind === 'summon' ? 600 : 340
      gain.gain.setValueAtTime(0.035, context.currentTime); gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.08)
      oscillator.connect(gain); gain.connect(context.destination); oscillator.start(); oscillator.stop(context.currentTime + 0.09)
    }
    const timer = setTimeout(() => setActive(null), mode === 'full' ? 650 : mode === 'fast' ? 180 : 80)
    return () => clearTimeout(timer)
  }, [active, mode, sound])
  useEffect(() => () => { void audio.current?.close() }, [])
  useEffect(() => {
    const catchUp = () => { if (document.hidden) { setQueue([]); setActive(null) } }
    document.addEventListener('visibilitychange', catchUp)
    return () => document.removeEventListener('visibilitychange', catchUp)
  }, [])
  async function toggleSound() {
    if (!sound) { audio.current ||= new AudioContext(); await audio.current.resume() }
    setSound(!sound)
  }
  return <aside className={`duel-animation-console motion-${mode}`} aria-label="Duellanimationen">
    <div className="duel-animation-controls"><label>Animationen<select value={mode} onChange={event => { const next = event.target.value as Mode; setMode(next); localStorage.setItem('duel-motion', next) }}><option value="full">Voll</option><option value="fast">Schnell</option><option value="reduced">Bewegungsarm</option></select></label>
      <button aria-pressed={sound} onClick={() => void toggleSound()}>Ton {sound ? 'an' : 'aus'}</button>
      <button disabled={!active && !queue.length} onClick={() => { setQueue([]); setActive(null) }}>Animationen überspringen</button>
    </div>
    {active && <Motion key={`motion:${active.id}`} event={active} mode={mode} />}
    <div className={`duel-event-stage event-${active?.kind || 'idle'} summon-${active?.method || 'none'}`} key={`event:${active?.id || 'idle'}`} aria-live="polite">
      <span className="duel-event-symbol" aria-hidden="true">{active?.kind === 'attack' ? '⚔' : active?.kind === 'summon' ? '✦' : active?.kind === 'chain' ? '∞' : active?.kind === 'lp' ? '♥' : '◇'}</span>
      <span>{active ? active.kind === 'summon' ? methods[active.method || 'special'] : captions[active.kind] || 'Spielereignis' : 'Bereit für dein Duell'}{active?.kind === 'lp' && ` · ${active.value?.toLocaleString('de-DE')} LP`}{active?.kind === 'chain_step' && ` · ${active.number ? 'Glied ' + active.number + ': ' : ''}${active.step === 72 ? 'wird aufgelöst' : active.step === 73 ? 'aufgelöst' : active.step === 74 ? 'beendet' : active.step === 75 || active.step === 76 ? 'negiert' : 'fortgesetzt'}`}{active?.values && ` · ${active.values.join(', ')}`}{active?.text && ` · ${active.text}`}{active?.cards && ` · ${active.cards.map(card => card.name).join(', ')}`}</span>
    </div>
    <details><summary>Bestätigtes Duellprotokoll</summary><ol className="duel-event-log">{events.filter(event => event.kind !== 'information').map(event => <li key={event.id}>#{event.id} {event.kind === 'summon' ? methods[event.method || 'special'] : captions[event.kind] || event.kind}{event.number ? ` · ${event.number}` : ''}{event.value !== undefined ? ` · ${event.value}` : ''}{event.values ? ` · ${event.values.join(', ')}` : ''}{event.text ? ` · ${event.text}` : ''}{event.cards ? ` · ${event.cards.map(card => card.name).join(', ')}` : ''}</li>)}</ol></details>
  </aside>
}
