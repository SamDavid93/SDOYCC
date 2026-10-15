import type { WorkerPrompt } from './DuelDecisions'
import { germanEffectText } from './duelGermanText'

export function DuelEffectOptions({ options, disabled, choose, confirmLabel = 'Diesen Effekt wählen' }: {
  options: { index: number; choice: WorkerPrompt['choices'][number] }[];
  disabled: boolean; choose: (index: number) => void;
  confirmLabel?: string;
}) {
  return <div className="duel-effect-option-list" aria-label="Verfügbare Effekte">
    {options.map(({ index, choice }, position) => <div className="duel-effect-option" key={index}><button type="button" disabled={disabled} onClick={() => choose(index)}>
      <strong>Effekt {position + 1}</strong>
      {choice.card && <small>{choice.card.name}</small>}
      <p>{germanEffectText(choice.effect_text, choice.effect_language, choice.card)}</p>
      <span>{confirmLabel}</span>
    </button></div>)}
  </div>
}
