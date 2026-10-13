import type { CSSProperties } from 'react'
import { Shield, Swords } from 'lucide-react'

export function DuelPlayerHUD({ owner, own, lp, active, hand }: { owner: number; own: boolean; lp: number; active: boolean; hand: number }) {
  return <header className={'duel-player-hud' + (active ? ' is-active-player' : '')} data-duel-hud={owner}>
    <div className="duel-player-emblem" aria-hidden="true">{own ? <Shield size={22} /> : <Swords size={22} />}</div>
    <div className="duel-player-identity"><h2>{own ? 'Dein Spielfeld' : 'Gegnerisches Spielfeld'}</h2><span>{active ? 'Am Zug' : 'Wartet'} · {hand} Handkarten</span></div>
    <div className="duel-life-panel"><span className="duel-life-caption">LEBENSPUNKTE</span><strong className="duel-life" key={lp}>{lp.toLocaleString('de-DE')} <small>LP</small></strong>
      <div className="duel-life-track" aria-hidden="true" style={{ '--life-fill': `${Math.max(0, Math.min(100, lp / 8000 * 100))}%` } as CSSProperties}><span /></div>
    </div>
  </header>
}
