import { useEffect, useId, useRef, useState } from 'react'
import type { WorkerPrompt } from './DuelDecisions'

export const duelPhaseName = (phase: number) => ({
  1: 'Ziehphase', 2: 'Vorbereitungsphase', 4: 'Hauptphase 1',
  8: 'Kampfphase', 16: 'Kampfphase', 32: 'Kampfphase', 64: 'Kampfphase', 128: 'Kampfphase',
  256: 'Hauptphase 2', 512: 'Endphase',
} as Record<number, string>)[phase] || 'Phasenwechsel'

export function DuelPhaseControl({ phase, turnNumber, active, disabled, prompt, choose }: {
  phase: number; turnNumber: number; active: boolean; disabled: boolean;
  prompt?: WorkerPrompt | null; choose: (index: number) => void;
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const menuId = useId()
  const options = prompt?.title === 'Aktion wählen' && !prompt.select && !prompt.counter
    ? prompt.choices.map((choice, index) => ({ choice, index })).filter(({ choice }) =>
      !choice.card && !choice.action && !choice.location && ['Kampfphase', 'Hauptphase 2', 'Zug beenden'].includes(choice.label)) : []
  const available = active && !disabled && options.length > 0
  useEffect(() => { setOpen(false) }, [prompt?.id, available])
  useEffect(() => {
    if (!open) return
    function dismiss(event: PointerEvent) { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    function escape(event: KeyboardEvent) { if (event.key === 'Escape') { setOpen(false); button.current?.focus() } }
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', dismiss); document.removeEventListener('keydown', escape) }
  }, [open])
  const name = duelPhaseName(phase)
  const compactName = ({ 1: 'Ziehen', 2: 'Standby', 4: 'Main 1', 256: 'Main 2', 512: 'Ende' } as Record<number, string>)[phase] || (name === 'Kampfphase' ? 'Kampf' : 'Wechsel')
  return <div ref={root} className={'arena-phase-control' + (active ? ' is-own-turn' : ' is-opponent-turn')}>
    <button ref={button} type="button" className="arena-phase-orb" disabled={!available}
      aria-label={`Aktuelle Phase: ${name}. ${available ? 'Phase wechseln' : active ? 'Zurzeit kein Phasenwechsel möglich' : 'Gegner ist am Zug'}`}
      aria-expanded={open && available} aria-controls={menuId}
      title={available ? 'Erlaubte Phasenwechsel anzeigen' : active ? 'Auf die aktuelle Spielentscheidung warten' : 'Dein Gegner ist am Zug'}
      onClick={() => setOpen(value => !value)}>
      <span className="arena-phase-turn">Zug {turnNumber}</span><strong><span className="arena-phase-full">{name}</span><span className="arena-phase-compact" aria-hidden="true">{compactName}</span></strong>
      <span className="arena-phase-hint">{available ? 'Wechseln ▾' : active ? 'Dein Zug' : 'Gegner'}</span>
    </button>
    {open && available && <div id={menuId} className="arena-phase-options" role="group" aria-label="Erlaubte Phasenwechsel">
      {options.map(({ choice, index }) => <button key={index} type="button" onClick={() => { setOpen(false); choose(index) }}>{choice.label === 'Zug beenden' ? 'Endphase · Zug beenden' : choice.label}</button>)}
    </div>}
  </div>
}
