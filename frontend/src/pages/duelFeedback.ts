import type { DuelLocation, WorkerPrompt } from './DuelDecisions'

const sameLocation = (left: DuelLocation | undefined, right: DuelLocation) => left?.owner === right.owner && left.zone === right.zone && left.sequence === right.sequence

export function effectAvailableAt(prompt: WorkerPrompt | null | undefined, location: DuelLocation) {
  if (!prompt) return false
  if (sameLocation(prompt.effect_location, location)) return true
  const chain = prompt.kind === 'chain' || prompt.title === 'Auf die Kette reagieren'
  return prompt.choices.some(choice => (sameLocation(choice.location, location) || (location.zone === 4 && choice.location?.owner === location.owner && choice.location.zone === 132 && choice.location.sequence === location.sequence)) && (choice.action === 'activate' || (chain && Boolean(choice.card))))
}

export function phaseAnnouncement(event: { kind: string; phase?: number; player?: number; number?: number }, seat?: number) {
  const own = event.player === seat
  const player = own ? 'Dein Zug' : 'Gegnerischer Zug'
  if (event.kind === 'phase_request') return { title: 'Beendet Zug', detail: `${player} · Reaktionen sind noch möglich`, own }
  if (event.kind === 'turn_end') return { title: 'Zug beendet', detail: `${player} · Zug ${event.number}`, own }
  if (event.kind === 'turn') return { title: own ? 'Dein Zug' : 'Gegner ist am Zug', detail: `Zug ${event.number}`, own }
  if (event.kind !== 'phase') return null
  const name = ({ 1: 'Ziehphase', 2: 'Standby-Phase', 4: 'Hauptphase 1', 8: 'Kampfphase', 16: 'Kampfphase', 32: 'Kampfphase', 64: 'Kampfphase', 128: 'Kampfphase', 256: 'Hauptphase 2', 512: 'Endphase' } as Record<number, string>)[event.phase || 0]
  return name ? { title: name, detail: `${player} · Zug ${event.number}`, own } : null
}
