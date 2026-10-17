import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '../api/transport'
import type { EngineCard } from './DuelWorkerTable'
import { phaseAnnouncement } from './duelFeedback'
import { DuelSoundPlayer } from './duelSounds'
import { DuelEventMotion } from './DuelEventMotion'
import { bossSummon, DuelSummonCutin } from './DuelSummonCutin'
import { germanEffectText } from './duelGermanText'

type Location = { owner: number; zone: number; sequence: number; position?: number }
export type DuelEvent = { id: number; kind: string; winner?: number | null; added?: boolean; delta?: number; affected_cards?: { role: string; name: string }[]; direct?: boolean; card?: EngineCard; effect?: string | null; effect_language?: string | null; player?: number; count?: number; value?: number; phase?: number; number?: number; step?: number; code?: number; text?: string; method?: string; values?: number[]; cards?: { name: string }[]; before?: Location & { position?: number }; after?: Location & { position?: number }; source?: Location; target?: Location; attacker?: Location; defender?: Location; location?: Location }
type Mode = 'full' | 'fast' | 'reduced'
export type DuelPlayback = { through: number; idle: boolean; event: DuelEvent | null }
const captions: Record<string, string> = { draw: 'Karte gezogen', move: 'Karte bewegt', position: 'Position geändert',
  turn: 'Neuer Spielzug', turn_end: 'Zug beendet', phase_request: 'Beendet Zug', phase: 'Phasenwechsel', lp: 'Lebenspunkte geändert', summon: 'Beschwörung',
  chain: 'Effekt aktiviert', chain_step: 'Kette', attack: 'Angriff', win: 'Duell beendet',
  shuffle: 'Deck gemischt', destroy: 'Karte zerstört', banish: 'Karte verbannt', coin: 'Münzwurf', dice: 'Würfelwurf', negate: 'Effekt negiert',
  control: 'Kontrolle gewechselt', material: 'Material bewegt', token: 'Spielmarke erzeugt', counter: 'Zählmarken geändert',
  equip: 'Ausrüstung verbunden', unequip: 'Ausrüstung gelöst', target: 'Ziel markiert', untarget: 'Ziel gelöst', reveal: 'Karten aufgedeckt', zones: 'Zonensperre geändert', hint: 'Engine-Hinweis' }
const methods: Record<string, string> = { normal: 'Normal-/Tributbeschwörung', flip: 'Flippbeschwörung', special: 'Spezialbeschwörung', fusion: 'Fusion', synchro: 'Synchro', xyz: 'Xyz', link: 'Link', ritual: 'Ritual', pendulum: 'Pendel', covered: 'Verdeckte Beschwörung' }
const chainSteps: Record<number, string> = { 71: 'Kette fortgesetzt', 72: 'Effekt wird aufgelöst', 73: 'Effekt aufgelöst', 74: 'Kette beendet', 75: 'Aktivierung negiert', 76: 'Effekt negiert' }

export function DuelAnimations({ events, runId, onEffect, onPlayback, seat, disabled, surrender, phase, turn, turnNumber, decisionPending=false, timerWarning }: { events: DuelEvent[]; runId: string; phase?: number; turn?: number; turnNumber?: number; decisionPending?:boolean; timerWarning?: {seconds:number;serial:number} | null; onPlayback?: (playback: DuelPlayback) => void;
  onEffect?: (card: EngineCard, effect?: string | null) => void; seat?: number; disabled?: boolean; surrender?: () => void }) {
  const [mode, setMode] = useState<Mode>(() => {
    const stored = localStorage.getItem('duel-motion')
    return stored === 'full' || stored === 'fast' || stored === 'reduced' ? stored : matchMedia('(prefers-reduced-motion: reduce)').matches ? 'reduced' : 'full'
  })
  const [sound, setSound] = useState(() => localStorage.getItem('duel-sound') !== 'off'), [active, setActive] = useState<DuelEvent | null>(null)
  const [volume, setVolume] = useState(() => { const value=Number(localStorage.getItem('duel-volume') ?? '.3'); return Number.isFinite(value) ? Math.min(1,Math.max(0,value)) : .3 })
  const [queue, setQueue] = useState<DuelEvent[]>([])
  const [cutins,setCutins]=useState(()=>localStorage.getItem('duel-cutins')!=='off')
  const watermark = useRef<number | null>(null), audio = useRef<DuelSoundPlayer | null>(null)
  const completed = useRef(0)
  const queuedThrough = useRef(0)
  const resultSeen = useRef(false)
  const lastSound = useRef<number | null>(null), lastPhase = useRef<string | null>(null)
  useEffect(() => { watermark.current = null; resultSeen.current=false; lastSound.current=null; lastPhase.current=null; audio.current?.stop(); setQueue([]); setActive(null) }, [runId])
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
      completed.current = newest
      queuedThrough.current = newest
      resultSeen.current = events.some(event => event.kind === 'win')
      if (phase && !resultSeen.current) setQueue([{id:-1,kind:'phase',phase,player:turn,number:turnNumber}])
      return
    }
    const unseen = events.filter(event => event.id > watermark.current!).sort((a, b) => a.id - b.id)
    watermark.current = Math.max(watermark.current, newest)
    if (document.hidden) { resultSeen.current ||= unseen.some(event => event.kind === 'win'); completed.current = newest; queuedThrough.current = newest; return }
    // The viewer follows confirmed effects immediately, independently of animation playback.
    const effects = unseen.filter(event => event.kind === 'chain' && event.card)
    const latestEffect = effects.at(-1)
    if (latestEffect?.card && latestEffect.source?.owner === seat) onEffect?.(latestEffect.card, latestEffect.effect_language === 'de' ? latestEffect.effect : undefined)
    if (sound) effects.filter(event => event.source?.owner === seat).forEach(event => audio.current?.play(event))
    const shown = unseen.filter(event => {
      if (event.kind === 'information') return false
      if (event.kind === 'win') {
        if (resultSeen.current) return false
        resultSeen.current = true
        return true
      }
      if (event.kind === 'chain' && event.source?.owner === seat) return false
      if (event.kind !== 'phase') return true
      const phase = event.phase && event.phase >= 8 && event.phase <= 128 ? 8 : event.phase
      const key = `${event.player}:${event.number}:${phase}`
      if (lastPhase.current === key) return false
      lastPhase.current = key
      return true
    })
    // Preserve attacks, damage and the final result in engine order.
    if (shown.length) { queuedThrough.current = shown.at(-1)!.id; setQueue(old => [...old, ...shown]) }
  }, [events, onEffect, seat, sound])
  useEffect(() => {
    if (active || !queue.length) return
    setActive(queue[0]); setQueue(old => old.slice(1))
  }, [active, queue])
  useEffect(() => {
    if (!active) return
    const routine = ['move','position','shuffle','counter','material','equip','unequip','target','untarget','hint','zones'].includes(active.kind)
    const duration = cutins && bossSummon(active,seat) ? mode==='full'?1450:mode==='fast'?650:350 : active.kind === 'win' ? 1800 : active.kind === 'chain' && active.card ? (mode === 'fast' ? 450 : 900) : phaseAnnouncement(active,seat) ? 850 : active.kind === 'chain_step' ? 180 : routine ? 90 : mode === 'full' ? 650 : mode === 'fast' ? 220 : 180
    const timer = setTimeout(() => { completed.current = Math.max(completed.current, active.id); setActive(null) }, duration)
    return () => clearTimeout(timer)
  }, [active, mode, onEffect, seat, cutins])
  useEffect(() => {
    // Defer until newly received events have entered the queue. Reporting idle
    // in the ingestion render would reveal a terminal snapshot too early.
    const timer = setTimeout(() => {
      const idle = !active && !queue.length && completed.current >= queuedThrough.current
      onPlayback?.({ through: idle ? watermark.current || 0 : completed.current, idle, event: active })
    }, 0)
    return () => clearTimeout(timer)
  }, [active, queue, events, onPlayback])
  useEffect(() => {
    if (!active || lastSound.current===active.id) return
    lastSound.current=active.id
    if (sound) {
      if(cutins && bossSummon(active,seat))audio.current?.playBossSummon(active,mode==='full'?1.65:mode==='fast'?.8:.4)
      else audio.current?.play(active)
    }
  }, [active, sound, seat, cutins, mode])
  useEffect(() => {
    const catchUp = () => { if (document.hidden) { completed.current = watermark.current || 0; setQueue([]); setActive(null); audio.current?.stop() } }
    document.addEventListener('visibilitychange', catchUp)
    return () => document.removeEventListener('visibilitychange', catchUp)
  }, [])
  async function toggleSound() {
    localStorage.setItem('duel-sound',sound ? 'off' : 'on')
    if (!sound) { audio.current ||= new DuelSoundPlayer(); await audio.current.unlock().catch(()=>{}) }
    setSound(!sound)
  }
  useEffect(() => { if (sound && timerWarning) audio.current?.playTimerWarning(timerWarning.seconds) }, [timerWarning])
  const announcement = active && phaseAnnouncement(active,seat)
  const cutin=active && cutins && bossSummon(active,seat)
  return <aside className={`duel-animation-console motion-${mode}`} aria-label="Duellanimationen">
    <details className="arena-settings"><summary aria-label="Duellmenü">☰</summary><div className="arena-settings-content">
    <div className="duel-animation-controls"><label>Animationen<select aria-label="Animationen" value={mode} onChange={event => { const next = event.target.value as Mode; setMode(next); localStorage.setItem('duel-motion', next) }}><option value="full">Voll</option><option value="fast">Schnell</option><option value="reduced">Bewegungsarm</option></select></label>
      <label><input aria-label="Boss-Cut-ins" type="checkbox" checked={cutins} onChange={event=>{setCutins(event.target.checked);localStorage.setItem('duel-cutins',event.target.checked?'on':'off')}} />Boss-Cut-ins</label>
      <button aria-pressed={sound} onClick={() => void toggleSound()}>Ton {sound ? 'an' : 'aus'}</button>
      <label>Lautstärke<input aria-label="Duell-Lautstärke" type="range" min="0" max="1" step="0.05" value={volume} onChange={event => { const next=Number(event.target.value); setVolume(next); localStorage.setItem('duel-volume',String(next)) }} /></label>
      <button disabled={!active && !queue.length} onClick={() => { completed.current = watermark.current || 0; setQueue([]); setActive(null); audio.current?.stop() }}>Animationen überspringen</button>
    </div>
    {surrender && <button className="duel-surrender" disabled={disabled} onClick={surrender}>Duell aufgeben</button>}
    <a href={`${import.meta.env.BASE_URL}duel-sounds/CREDITS.md`} target="_blank" rel="noreferrer">Soundquellen</a>
    <button onClick={event => { const field=event.currentTarget.closest('.duel-worker-table'); if (document.fullscreenElement) void document.exitFullscreen(); else if(field) void field.requestFullscreen().catch(()=>{}) }}>Spielfeld im Vollbild</button>
    <details><summary>Bestätigtes Duellprotokoll</summary><ol className="duel-event-log">{events.filter(event => event.kind !== 'information').map(event => <li key={event.id}>#{event.id} {event.kind === 'summon' ? methods[event.method || 'special'] : event.kind === 'chain_step' ? chainSteps[event.step || 0] || 'Kette' : captions[event.kind] || event.kind}{event.number ? ` · ${event.number}` : ''}{event.value !== undefined ? ` · ${event.value}` : ''}{event.values ? ` · ${event.values.join(', ')}` : ''}{event.text && (event.kind !== 'hint' || event.effect_language === 'de') ? ` · ${event.text}` : ''}{event.card ? ` · ${event.card.name}` : ''}{event.affected_cards?.map((card,index) => <span key={index}> · {card.role}: {card.name}</span>)}{event.direct ? ' · Direkter Angriff' : ''}{event.cards ? ` · ${event.cards.map(card => card.name).join(', ')}` : ''}</li>)}</ol></details>
    </div></details>
    {active && <DuelEventMotion key={`motion:${active.id}`} event={active} mode={mode} seat={seat} />}
    {cutin && active && <DuelSummonCutin key={`cutin:${active.id}`} event={active} compact={decisionPending} mode={mode} />}
    {announcement && <section className={'arena-phase-announcement ' + (announcement.own ? 'is-own-turn' : 'is-opponent-turn')} role="status" aria-label="Phasenwechsel" key={`phase:${active!.id}`}><small>{announcement.detail}</small><strong>{announcement.title}</strong></section>}
    {active?.kind === 'win' && <section className={'duel-result-announcement ' + (active.winner === seat ? 'is-victory' : active.winner == null ? 'is-draw' : 'is-defeat')} role="status" aria-label="Duellergebnis" key={`result:${active.id}`}><small>Duell abgeschlossen</small><strong>{active.winner === undefined ? 'Duell beendet' : active.winner === null ? 'Unentschieden' : active.winner === seat ? 'Sieg' : 'Niederlage'}</strong><span>Das Ergebnis wurde bestätigt.</span></section>}
    {(active?.kind === 'negate' || active?.kind === 'chain_step' && [75,76].includes(active.step || 0)) && <section className="duel-negate-announcement" role="status" aria-label="Negierter Effekt"><span aria-hidden="true">×</span><strong>{active.step === 75 ? 'Aktivierung negiert' : 'Effekt negiert'}</strong></section>}
    {active?.kind === 'chain' && active.card && active.source?.owner !== seat && <section className="duel-effect-reveal" role="status" aria-label="Aktivierter Karteneffekt" data-effect-owner="opponent" key={`effect:${active.id}`}>
      <div className="duel-effect-orbit" aria-hidden="true" /><b className="duel-chain-number" aria-hidden="true">{active.number || 1}</b>
      <span>{active.source?.owner === seat ? 'Dein Effekt' : 'Gegner aktiviert'} · Kettenglied {active.number}</span>
      {active.card.image_url && <img src={API_BASE_URL.replace(/\/api\/?$/, '') + active.card.image_url} alt={active.card.name} onError={event => { const img=event.currentTarget; if(active.card?.fallback_image_url && !img.dataset.fallback){img.dataset.fallback='1';img.src=API_BASE_URL.replace(/\/api\/?$/, '')+active.card.fallback_image_url}else img.hidden=true }} />}
      <strong>{active.card.name}</strong><small>{germanEffectText(active.effect, active.effect_language, active.card)}</small>
    </section>}
    {active && active.kind !== 'win' && !cutin && !announcement && !(active.kind === 'chain' && active.card) && <div className={`duel-event-stage event-${active?.kind || 'idle'} summon-${active?.method || 'none'}`} key={`event:${active?.id || 'idle'}`} aria-live="polite">
      <span className="duel-event-symbol" aria-hidden="true">{active?.kind === 'attack' ? '⚔' : active?.kind === 'summon' ? '✦' : active?.kind === 'chain' ? '∞' : active?.kind === 'lp' ? '♥' : '◇'}</span>
      <span>{active ? active.kind === 'summon' ? methods[active.method || 'special'] : captions[active.kind] || 'Spielereignis' : 'Bereit für dein Duell'}{active?.kind === 'lp' && ` · ${active.value?.toLocaleString('de-DE')} LP`}{active?.kind === 'chain_step' && ` · ${active.number ? 'Glied ' + active.number + ': ' : ''}${active.step === 72 ? 'wird aufgelöst' : active.step === 73 ? 'aufgelöst' : active.step === 74 ? 'beendet' : active.step === 75 || active.step === 76 ? 'negiert' : 'fortgesetzt'}`}{active?.values && ` · ${active.values.join(', ')}`}{active?.text && (active.kind !== 'hint' || active.effect_language === 'de') && ` · ${active.text}`}{active?.cards && ` · ${active.cards.map(card => card.name).join(', ')}`}</span>
      {active.affected_cards?.length ? <small className="duel-event-cardnames">{[...new Set(active.affected_cards.map(card => card.name))].join(' / ')}</small> : null}
    </div>}
  </aside>
}
