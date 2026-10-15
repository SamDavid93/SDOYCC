import type { EngineCard } from './DuelWorkerTable'

// The engine sends zero for rating fields that do not apply to this card type.
// Those zeros must never take precedence over a monster's actual level.
export function duelCardRating(card: Pick<EngineCard, 'type' | 'level' | 'rank' | 'link'>) {
  if ((card.type ?? 0) & 0x4000000) return card.link ?? card.level
  if ((card.type ?? 0) & 0x800000) return card.rank ?? card.level
  return card.level
}
