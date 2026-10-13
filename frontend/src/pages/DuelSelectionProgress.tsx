import type { WorkerPrompt } from './DuelDecisions'

export function DuelSelectionProgress({ prompt, count }: { prompt: WorkerPrompt; count: number }) {
  const minimum = prompt.counter ? prompt.counter_total || 0 : prompt.selection_progress?.minimum ?? prompt.minimum ?? 0
  const maximum = prompt.counter ? minimum : prompt.selection_progress?.maximum ?? prompt.maximum ?? 0
  const complete = prompt.selection_progress ? prompt.selection_progress.can_finish : count >= minimum && count <= maximum
  const unit = prompt.counter ? 'Zählmarken' : 'Karten'
  const needed = Math.max(0, minimum - count)
  const title = minimum === maximum ? `Wähle genau ${minimum} ${minimum === 1 && !prompt.counter ? 'Karte' : unit}` : `Wähle ${minimum} bis ${maximum} ${unit}`
  return <div className={'duel-selection-progress' + (complete ? ' is-complete' : '')} role="status" aria-label="Auswahlfortschritt">
    <strong>{title}</strong><b>{count} / {maximum} ausgewählt</b>
    <progress max={Math.max(1, maximum)} value={count} aria-label="Gewählte Karten" />
    <small>{needed ? `Noch ${needed} ${needed === 1 && !prompt.counter ? 'Karte' : unit} erforderlich` : complete ? 'Auswahl bereit' : 'Weitere passende Karten wählen'}{!prompt.counter && ' · Doppelklick bestätigt eine vollständige Auswahl'}</small>
  </div>
}
