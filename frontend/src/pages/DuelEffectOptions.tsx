import type { WorkerPrompt } from './DuelDecisions'

export function DuelEffectOptions({ options, disabled, choose }: {
  options: { index: number; choice: WorkerPrompt['choices'][number] }[];
  disabled: boolean; choose: (index: number) => void;
}) {
  return <div className="duel-effect-option-list" aria-label="Verfügbare Effekte">
    {options.map(({ index, choice }, position) => <div className="duel-effect-option" key={index}><button type="button" disabled={disabled} onClick={() => choose(index)}>
      <strong>Effekt {position + 1}</strong>
      {choice.card && <small>{choice.card.name}</small>}
      <p>{choice.effect_text || (choice.card ? 'Für diese Effektoption liegt keine Beschreibung vor. Prüfe den Kartentext im Viewer.' : choice.label)}</p>
      <span>Diesen Effekt wählen</span>
    </button>{choice.effect_original && <details><summary>Originalbeschreibung anzeigen</summary><p lang="en">{choice.effect_original}</p></details>}</div>)}
  </div>
}
