import { createContext, useContext, useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { NavLink } from 'react-router-dom'
import { ArrowRight, Check, SkipForward, Sparkles, Volume2, VolumeX, X } from 'lucide-react'
import { openBooster, type BoosterOpening, type BoosterSummary } from '../api/client'
import { BoosterCover } from './BoosterDisplay'
import { label } from '../i18n'
import { CardVisual } from './CardVisual'

type Opening = { booster: BoosterSummary; result: BoosterOpening | null; error: string }
type OpeningContextValue = { openPack: (booster: BoosterSummary) => Promise<BoosterOpening | null> }
const OpeningContext = createContext<OpeningContextValue | null>(null)
export function usePackOpening() { return useContext(OpeningContext)! }

export function PackOpeningProvider({ children }: { children: ReactNode }) {
  const [opening, setOpening] = useState<Opening | null>(null)
  const locked = useRef(false)
  const openPack = async (booster: BoosterSummary) => {
    if (locked.current) return null
    locked.current = true
    setOpening({ booster, result: null, error: '' })
    try {
      const result = await openBooster(booster.id)
      setOpening({ booster, result, error: '' })
      return result
    } catch (cause) {
      setOpening({ booster, result: null, error: cause instanceof Error ? cause.message : 'Das Pack konnte nicht geöffnet werden.' })
      return null
    }
  }
  const close = () => {
    if (!opening?.result && !opening?.error) return
    setOpening(null)
    locked.current = false
  }
  return <OpeningContext.Provider value={{ openPack }}>{children}{opening && <OpeningShow opening={opening} close={close} />}</OpeningContext.Provider>
}

function rarityStyle(rarity: string) {
  const value = rarity.toLowerCase().replaceAll(' ', '_')
  if (/secret|ultimate|ghost|collector|starlight|quarter/.test(value)) return 'prismatic'
  if (/ultra|gold/.test(value)) return 'gold'
  if (/super/.test(value)) return 'violet'
  return 'cyan'
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return reduced
}

// Original synthesized cues: no downloaded music or game sound assets.
function useOpeningSound() {
  const audio = useRef<AudioContext | null>(null)
  const [enabled, setEnabled] = useState(false)
  useEffect(() => () => { void audio.current?.close(); audio.current = null }, [])
  const play = (kind: 'charge' | 'burst' | 'reveal') => {
    if (!enabled || !audio.current || audio.current.state !== 'running') return
    const context = audio.current
    const now = context.currentTime
    const duration = kind === 'charge' ? 1.2 : .65
    for (let index = 0; index < 3; index++) {
      const oscillator = context.createOscillator()
      const gain = context.createGain()
      oscillator.type = kind === 'charge' ? 'sine' : 'triangle'
      oscillator.frequency.setValueAtTime((kind === 'charge' ? 90 : kind === 'burst' ? 180 : 440) * (index + 1), now)
      oscillator.frequency.exponentialRampToValueAtTime((kind === 'charge' ? 360 : kind === 'burst' ? 90 : 660) * (index + 1), now + duration)
      gain.gain.setValueAtTime(0, now)
      gain.gain.linearRampToValueAtTime(.025 / (index + 1), now + .03)
      gain.gain.exponentialRampToValueAtTime(.0001, now + duration)
      oscillator.connect(gain); gain.connect(context.destination)
      oscillator.start(now); oscillator.stop(now + duration)
    }
  }
  const toggle = () => {
    if (enabled) { setEnabled(false); return }
    try {
      audio.current ||= new AudioContext()
      void audio.current.resume().then(() => setEnabled(true)).catch(() => setEnabled(false))
    } catch { setEnabled(false) }
  }
  return { enabled, toggle, play }
}

function OpeningShow({ opening, close }: { opening: Opening; close: () => void }) {
  const { booster, result, error } = opening
  const dialog = useRef<HTMLDialogElement>(null)
  const [phase, setPhase] = useState<'loading' | 'charge' | 'burst' | 'reveal' | 'summary'>('loading')
  const [revealed, setRevealed] = useState<number[]>([])
  const [latest, setLatest] = useState<number | null>(null)
  const [spotlight, setSpotlight] = useState<number | null>(null)
  const reduced = useReducedMotion()
  const sound = useOpeningSound()
  const soundRef = useRef(sound.play)
  soundRef.current = sound.play
  useEffect(() => {
    const element = dialog.current!
    const previousFocus = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    element.showModal()
    return () => { element.close(); document.body.style.overflow = overflow; previousFocus?.focus({ preventScroll: true }) }
  }, [])
  useEffect(() => { if (result) setPhase(reduced ? 'reveal' : 'charge') }, [result])
  useEffect(() => { dialog.current?.scrollTo({ top: 0, behavior: 'instant' }) }, [phase])
  useEffect(() => {
    if (reduced && (phase === 'charge' || phase === 'burst')) { setPhase('reveal'); return }
    if (phase !== 'charge' && phase !== 'burst') return
    soundRef.current(phase)
    const timer = window.setTimeout(() => setPhase(phase === 'charge' ? 'burst' : 'reveal'), phase === 'charge' ? 1800 : 1000)
    return () => window.clearTimeout(timer)
  }, [phase, reduced])
  useEffect(() => {
    if (spotlight === null) return
    const timer = window.setTimeout(() => setSpotlight(null), 1900)
    return () => window.clearTimeout(timer)
  }, [spotlight])
  const reveal = (index: number) => {
    if (revealed.includes(index)) return
    setRevealed(current => [...current, index]); setLatest(index); sound.play('reveal')
    if (!reduced && result && rarityStyle(result.cards[index].rarity) !== 'cyan') setSpotlight(index)
  }
  const skip = () => { if (result) { setRevealed(result.cards.map((_, index) => index)); setPhase('summary') } }
  const allRevealed = !!result && revealed.length === result.cards.length
  const aura = latest === null || !result ? 'cyan' : rarityStyle(result.cards[latest].rarity)
  return createPortal(<dialog ref={dialog} className={`opening-show phase-${phase} aura-${aura}`} aria-labelledby="opening-title" onCancel={event => { event.preventDefault(); close() }}>
    <div className="opening-atmosphere" aria-hidden="true"><div className="opening-grid-floor" /><div className="opening-nebula" /><div className="opening-orbit orbit-a" /><div className="opening-orbit orbit-b" />{Array.from({ length: 32 }, (_, index) => <i className="opening-particle" key={index} style={{ '--x': `${(index * 37 + 11) % 100}%`, '--y': `${(index * 23 + 7) % 100}%`, '--delay': `${-(index % 7)}s`, '--travel': `${(index % 2 ? 1 : -1) * (80 + index * 8)}px` } as CSSProperties} />)}</div>
    <header className="opening-top"><span className="opening-brand"><Sparkles size={18} /> SDOYCC <small>{booster.product_type === 'structure_deck' ? 'DECK-ÖFFNUNG' : 'BOOSTER-ÖFFNUNG'}</small></span><div className="opening-controls"><button onClick={sound.toggle} aria-label={sound.enabled ? 'Ton ausschalten' : 'Ton einschalten'} aria-pressed={sound.enabled}>{sound.enabled ? <Volume2 size={18} /> : <VolumeX size={18} />}</button><button disabled={!result} onClick={skip}><SkipForward size={16} />Animation überspringen</button><button aria-label="Öffnung schließen" disabled={!result && !error} onClick={close}><X size={20} /></button></div></header>
    {error ? <section className="opening-error"><h1 id="opening-title">Öffnung unterbrochen</h1><p role="alert">{error}</p><p>Bei einem Verbindungsabbruch prüfe deine Öffnungshistorie. Bereits gezogene Karten bleiben in deiner Sammlung.</p><NavLink to="/boosters/history" onClick={close} className="opening-primary">Historie ansehen</NavLink><button onClick={close} className="opening-secondary">Zurück zum Hub</button></section> : <>
      <div className="opening-heading"><p className="eyebrow">{phase === 'summary' ? 'DEINE SAMMLUNG WÄCHST' : phase === 'reveal' ? 'DER MOMENT GEHÖRT DIR' : 'ENERGIE WIRD FREIGESETZT'}</p><h1 id="opening-title">{phase === 'summary' ? 'Deine neuen Karten.' : phase === 'reveal' ? 'Dein Pack. Deine Entdeckung.' : booster.name}</h1><p aria-live="polite">{phase === 'loading' ? 'Dein Pack wird geöffnet …' : phase === 'charge' ? 'Ein Pack. Unzählige Möglichkeiten.' : phase === 'burst' ? 'Das Siegel bricht.' : phase === 'reveal' ? `${revealed.length} / ${result?.cards.length} Karten aufgedeckt · Tippe auf eine Karte` : `${result?.cards.length} Karten sind jetzt in deiner Sammlung.`}</p></div>
      {phase === 'reveal' && spotlight !== null && result && <div key={spotlight} className={`rarity-spotlight rarity-${rarityStyle(result.cards[spotlight].rarity)}`} aria-hidden="true"><div className="spotlight-rays" /><div className="spotlight-orbit" /><div className="spotlight-card"><CardVisual card={result.cards[spotlight]} /></div><div className="spotlight-copy"><span>{label(result.cards[spotlight].rarity)}</span><strong>{result.cards[spotlight].name}</strong></div></div>}
      {(phase === 'loading' || phase === 'charge' || phase === 'burst') && <div className="opening-pack-stage" aria-hidden="true"><div className="pack-energy-ring" /><div className="pack-light-column" /><div className="opening-pack"><div className="pack-half pack-top"><BoosterCover name={booster.name} imageUrl={booster.image_url} /></div><div className="pack-half pack-bottom"><BoosterCover name={booster.name} imageUrl={booster.image_url} /></div><div className="pack-seam" /></div><div className="pack-shockwave" /><span className="pack-stage-caption">{phase === 'loading' ? 'VERBINDUNG ZUM HUB' : 'DAS NÄCHSTE KAPITEL DEINER SAMMLUNG'}</span></div>}
      {phase === 'reveal' && result && <><div className="opening-reveal-grid">{result.cards.map((card, index) => <div className={`reveal-slot rarity-${rarityStyle(card.rarity)} ${revealed.includes(index) ? 'is-revealed' : ''}`} key={index} style={{ '--card-index': index } as CSSProperties}><button className="reveal-card" disabled={revealed.includes(index)} aria-label={revealed.includes(index) ? card.name : `Karte ${index + 1} aufdecken`} onClick={() => reveal(index)}><span className="reveal-card-inner"><span className="reveal-back" aria-hidden="true"><span className="back-corner top">SDOYCC / {String(index + 1).padStart(2, '0')}</span><span className="back-sigil"><Sparkles size={42} /></span><span className="back-caption">SDOYCC<br /><small>ZUM AUFDECKEN ANTIPPEN</small></span></span><span className="reveal-front" aria-hidden={!revealed.includes(index)}><CardVisual card={card} /></span></span></button><div className="reveal-caption" aria-live="polite">{revealed.includes(index) ? <><span>{label(card.rarity)}</span><strong>{card.name}</strong></> : <span>KARTE {String(index + 1).padStart(2, '0')}</span>}</div></div>)}</div><div className="opening-bottom"><p><Check size={15} />Deine Karten sind bereits sicher in deiner Sammlung.</p><button className="opening-primary" onClick={skip}>{allRevealed ? 'Ergebnis ansehen' : 'Alle aufdecken'}<ArrowRight size={17} /></button></div></>}
      {phase === 'summary' && result && <><div className="opening-summary-grid">{result.cards.map((card, index) => <div className={`summary-card rarity-${rarityStyle(card.rarity)}`} key={index}><CardVisual card={card} /><span className="summary-rarity">{label(card.rarity)}</span></div>)}</div><div className="opening-summary-footer"><span><Check size={17} />In deiner Sammlung gespeichert · {result.remaining} Packs dieser Edition übrig</span><div><button className="opening-secondary" onClick={close}>Zurück zum Hub</button><NavLink className="opening-secondary" to="/my-packs" onClick={close}>Meine Packs</NavLink><NavLink className="opening-primary" to="/inventory" onClick={close}>Zur Sammlung <ArrowRight size={17} /></NavLink></div></div></>}
    </>}
  </dialog>, document.body)
}
