import type { WorkerPrompt } from './DuelDecisions'

export function DuelEffectOptions({ options, disabled, choose, confirmLabel = 'Diesen Effekt wählen' }: {
  options: { index: number; choice: WorkerPrompt['choices'][number] }[];
  disabled: boolean; choose: (index: number) => void;
  confirmLabel?: string;
}) {
  return <div className="duel-effect-option-list" aria-label="Verfügbare Effekte">
    {options.map(({ index, choice }, position) => <div className="duel-effect-option" key={index}><button type="button" disabled={disabled} onClick={() => choose(index)}>
      <strong>Effekt {position + 1}</strong>
      {choice.card && <small>{choice.card.name}</small>}
      <p>{choice.effect_text || choice.card?.description || (choice.card ? 'Für diese Effektoption liegt keine Beschreibung vor. Prüfe den Kartentext im Viewer.' : choice.label)}</p>
      <span>{confirmLabel}</span>
    </button>{choice.effect_original && <details><summary>Originalbeschreibung anzeigen</summary><p lang="en">{choice.effect_original}</p></details>}</div>)}
  </div>
}
