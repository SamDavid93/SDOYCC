import { useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import cardBack from '../assets/card-back.jpg'
import type { DuelEvent } from './DuelAnimations'

type Point = { x: number; y: number }
type Location = { owner: number; zone: number; sequence: number }

/** Coordinates come from this arena; card travel uses the back to preserve private identities. */
export function DuelEventMotion({ event, mode, seat }: { event: DuelEvent; mode: 'full' | 'fast' | 'reduced'; seat?: number }) {
  const root = useRef<SVGSVGElement>(null)
  const [points, setPoints] = useState<{ from: Point | null; to: Point | null }>({ from: null, to: null })
  useLayoutEffect(() => {
    const arena = root.current?.closest('.duel-arena')
    if (!arena) return
    const point = (location?: Location): Point | null => {
      if (!location) return null
      const selector = `[data-duel-owner="${location.owner}"][data-duel-zone="${location.zone & 127}"]`
      const element = arena.querySelector(`${selector}[data-duel-sequence="${location.sequence}"]`) || arena.querySelector(selector)
      const rect = element?.getBoundingClientRect()
      return rect ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 } : null
    }
    const hud = (owner?: number): Point | null => {
      const rect = arena.querySelector(`[data-duel-hud="${owner}"] .duel-life`)?.getBoundingClientRect()
      return rect ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 } : null
    }
    const measure = () => {
      const from = point(event.before || event.attacker || event.source || event.location || (event.kind === 'draw' ? { owner: event.player!, zone: 1, sequence: 0 } : undefined))
      const to = event.kind === 'lp' ? hud(event.player) : point(event.after || event.defender || event.target || event.location || (event.kind === 'draw' ? { owner: event.player!, zone: 2, sequence: 0 } : undefined)) || (event.kind === 'attack' && event.direct && event.attacker ? hud(1 - event.attacker.owner) : null) || from
      setPoints({ from, to })
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(arena)
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => { observer.disconnect(); window.removeEventListener('resize', measure); window.removeEventListener('scroll', measure, true) }
  }, [event])
  const { from, to } = points
  const own = (event.player ?? event.attacker?.owner ?? event.source?.owner ?? event.after?.owner) === seat
  const color = event.kind === 'summon' ? ({ fusion: '#ca8cff', synchro: '#e2fff9', xyz: '#eccc74', link: '#54dfff', ritual: '#709bff', pendulum: '#74eec0', covered: '#d2ad77' } as Record<string, string>)[event.method || ''] || '#8ebfff' : own ? '#66bcff' : '#ff7492'
  const travel = ['draw', 'move', 'destroy', 'banish', 'control', 'material'].includes(event.kind)
  const ray = ['attack', 'target', 'equip'].includes(event.kind)
  const portal = event.kind === 'summon'
  const impact = ['attack', 'destroy', 'banish', 'chain', 'negate', 'position'].includes(event.kind)
  const seconds = mode === 'fast' ? '.24s' : '.95s'
  return <svg ref={root} className={`duel-motion-layer duel-scene-motion motion-${mode}`} data-event-kind={event.kind} data-summon-method={portal ? event.method : undefined} aria-hidden="true" style={{ '--scene-color': color, '--scene-duration': seconds } as CSSProperties}>
    {from && to && ray && <g className="duel-attack-ray">
      <path d={`M${from.x} ${from.y} L${to.x} ${to.y}`} stroke={color} strokeWidth="24" opacity=".12" />
      <path d={`M${from.x} ${from.y} L${to.x} ${to.y}`} stroke={color} strokeWidth="8" opacity=".7" />
      <path className="duel-ray-core" pathLength="1" d={`M${from.x} ${from.y} L${to.x} ${to.y}`} stroke="#f0faff" strokeWidth="2" />
      <circle cx={from.x} cy={from.y} r="19" stroke={color} strokeWidth="2" fill="none" />
    </g>}
    {from && to && travel && mode !== 'reduced' && <g className="duel-travel-card">
      <image href={cardBack} x="-26" y="-38" width="52" height="76" preserveAspectRatio="xMidYMid meet" />
      <animateMotion dur={seconds} path={`M${from.x} ${from.y} Q${(from.x + to.x) / 2} ${Math.min(from.y, to.y) - 55} ${to.x} ${to.y}`} fill="freeze" />
    </g>}
    {to && (portal || impact) && <g transform={`translate(${to.x} ${to.y})`}>
      <g className={portal ? 'duel-summon-portal' : 'duel-impact-ring'}>
        <ellipse rx="62" ry="28" fill={color} opacity=".1" />
        <ellipse rx="55" ry="25" stroke={color} strokeWidth="3" fill="none" />
        <ellipse rx="72" ry="34" stroke={color} strokeWidth="1" strokeDasharray="9 6" fill="none" />
        <path d="M-80 0H80 M0-44V44" stroke={color} opacity=".5" />
      </g>
      {mode !== 'reduced' && <g className="duel-scene-sparks">{Array.from({ length: 12 }, (_, index) => {
        const angle = index * Math.PI / 6
        return <path key={index} d={`M${Math.cos(angle) * 25} ${Math.sin(angle) * 25} L${Math.cos(angle) * 75} ${Math.sin(angle) * 75}`} stroke={color} strokeWidth={index % 3 ? 1 : 3} />
      })}</g>}
    </g>}
    {to && event.kind === 'lp' && event.delta !== undefined && event.delta !== 0 && <g transform={`translate(${to.x} ${to.y})`}>
      <text className={'duel-lp-delta ' + (event.delta > 0 ? 'is-gain' : 'is-damage')} textAnchor="middle" dominantBaseline="middle">{event.delta > 0 ? '+' : '−'}{Math.abs(event.delta).toLocaleString('de-DE')}</text>
    </g>}
  </svg>
}
