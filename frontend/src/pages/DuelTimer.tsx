import { useEffect, useState, type CSSProperties } from 'react'
import { Hourglass, Pause } from 'lucide-react'
import './duel-timer.css'

export type DuelTimerState = {
  ownRemaining: number
  opponentRemaining: number
  active: 'own' | 'opponent' | null
  /** performance.now() when this authoritative clock snapshot was received. */
  updatedAt: number
  limit?: number
  pausedReason?: string
}

const seconds = (value: number) => Number.isFinite(value) ? Math.max(0, value) : 0
const time = (value: number) => {
  const remaining = Math.ceil(seconds(value))
  return `${Math.floor(remaining / 60).toString().padStart(2, '0')}:${(remaining % 60).toString().padStart(2, '0')}`
}

export function DuelTimer({ ownRemaining, opponentRemaining, active, updatedAt, limit = 360, pausedReason }: DuelTimerState) {
  const [now, setNow] = useState(() => performance.now())
  useEffect(() => {
    setNow(performance.now())
    if (!active) return
    const tick = window.setInterval(() => setNow(performance.now()), 100)
    return () => window.clearInterval(tick)
  }, [active, updatedAt])

  // A paused snapshot never loses time, including during a socket reconnect or
  // while a submitted answer is being processed. The server owns the balance.
  const elapsed = active ? Math.max(0, (now - updatedAt) / 1000) : 0
  const own = seconds(ownRemaining - (active === 'own' ? elapsed : 0))
  const opponent = seconds(opponentRemaining - (active === 'opponent' ? elapsed : 0))
  const low = own <= 30
  const status = active === 'own' ? low ? 'Zeit wird knapp' : 'Du entscheidest' : active === 'opponent' ? 'Gegner entscheidet' : 'Pausiert'
  const detail = active ? status : pausedReason || 'Die Zeit pausiert, solange keine Spielentscheidung möglich ist.'
  const StatusIcon = active === 'own' ? Hourglass : Pause
  const progress = Math.min(1, own / Math.max(1, limit))

  return <section className={'arena-timer-control' + (low ? ' is-low-time' : '')}
    aria-label="Duellzeit" data-clock-active={active || 'paused'} title={detail}>
    <div className="arena-timer-dial" style={{ '--timer-progress': progress } as CSSProperties}>
      <svg className="arena-timer-ring" viewBox="0 0 100 100" aria-hidden="true">
        <circle className="arena-timer-track" cx="50" cy="50" r="46" />
        <circle className="arena-timer-progress" cx="50" cy="50" r="46" pathLength="1" strokeDasharray={`${progress} 1`} />
      </svg>
      <span className="arena-timer-caption">Deine Zeit</span>
      <strong className="arena-timer-value" role="timer" aria-live="off"
        aria-label={`Deine verbleibende Duellzeit: ${Math.ceil(own)} Sekunden`}>{time(own)}</strong>
      <span className="arena-timer-status" role="status" aria-live="polite" aria-label={detail}>
        <StatusIcon size={11} aria-hidden="true" /><span>{status}</span>
      </span>
      <span className="arena-timer-opponent" data-active={active === 'opponent' ? 'true' : 'false'}>
        <span>Gegner</span><b role="timer" aria-live="off" aria-label={`Gegnerische verbleibende Duellzeit: ${Math.ceil(opponent)} Sekunden`}>{time(opponent)}</b>
      </span>
    </div>
  </section>
}
