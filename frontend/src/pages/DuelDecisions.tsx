import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../api/transport'

export type DuelLocation = { owner: number; zone: number; sequence: number }
export type WorkerPrompt = { id: number; title: string; kind?: string; placement?: boolean; hint?: string; select?: boolean; ordered?: boolean; cancel?: boolean;
  counter?: boolean; counter_limits?: number[]; counter_total?: number; minimum?: number; maximum?: number;
  choices: { label: string; card: { name: string; image_url?: string } | null; action?: string; location?: DuelLocation }[] }

export function DuelDecisions({ prompt, disabled, send, zoneSelection = [], onZoneSelection }: { prompt: WorkerPrompt | null | undefined; disabled: boolean;
  zoneSelection?: number[]; onZoneSelection?: (value: number[]) => void;
  send: (kind: string, body: Record<string, unknown>) => void }) {
  const [localSelection, setLocalSelection] = useState<number[]>([])
  const chain = prompt?.kind === 'chain' || prompt?.title === 'Auf die Kette reagieren'
  useEffect(() => {
    if (chain) document.querySelector<HTMLButtonElement>('.duel-chain-overlay .duel-choice-list button')?.focus({ preventScroll: true })
  }, [prompt?.id, chain])
  const selection = prompt?.kind === 'zones' ? zoneSelection : localSelection
  const setSelection = (value: number[] | ((old: number[]) => number[])) => {
    const next = typeof value === 'function' ? value(selection) : value
    if (prompt?.kind === 'zones' && onZoneSelection) onZoneSelection(next); else setLocalSelection(next)
  }
  const [filter, setFilter] = useState(''), [limit, setLimit] = useState(60)
  useEffect(() => { setSelection(prompt?.counter ? prompt.choices.map(() => 0) : []) }, [prompt?.id])
  useEffect(() => { setFilter(''); setLimit(60) }, [prompt?.id])
  const choices = prompt?.choices.map((choice, index) => ({ choice, index })).filter(({ choice }) => choice.label.toLocaleLowerCase('de').includes(filter.toLocaleLowerCase('de'))) || []
  const validCount = prompt?.counter ? selection.reduce((sum, value) => sum + value, 0) === prompt.counter_total :
    selection.length >= (prompt?.minimum || 0) && selection.length <= (prompt?.maximum || 0)
  return <section className="deck-panel duel-decisions" aria-label="Spielentscheidung"><h2>{prompt?.title || 'Warte auf den Gegner'}</h2>
    {prompt?.hint && <p>{prompt.hint}</p>}
    {prompt?.select && <p>{prompt.ordered ? 'Klicke die Karten in der gewünschten Reihenfolge an.' : `Wähle ${prompt.minimum} bis ${prompt.maximum} Karten. Die Engine prüft die Auswahl.`}</p>}
    {prompt?.counter && <p>Verteile {prompt.counter_total} zu entfernende Zählmarken.</p>}
    {prompt && prompt.choices.length > 30 && <label>Karten / Optionen suchen<input value={filter} onChange={event => { setFilter(event.target.value); setLimit(60) }} /></label>}
    <div className="duel-choice-list">{prompt && choices.slice(0, limit).map(({ choice, index }) => prompt.counter ?
      <label key={index}>{choice.label} · höchstens {prompt.counter_limits?.[index]}<input type="number" min={0} max={prompt.counter_limits?.[index]} value={selection[index] || 0} disabled={disabled} onChange={event => setSelection(old => old.map((value, i) => i === index ? Math.max(0, Math.min(prompt.counter_limits?.[index] || 0, Math.floor(Number(event.target.value)))) : value))} /></label> :
      <button key={index} disabled={disabled} aria-pressed={prompt.select ? selection.includes(index) : undefined} onClick={() => prompt.select ? setSelection(old => old.includes(index) ? old.filter(i => i !== index) : [...old, index]) : send('answer', { prompt: prompt.id, selected: [index] })}>
        {chain && choice.card?.image_url && <img className="duel-chain-card" src={API_BASE_URL.replace(/\/api\/?$/, '') + choice.card.image_url} alt="" onError={event => { event.currentTarget.hidden = true }} />}
        <span>{prompt.ordered && selection.includes(index) && `${selection.indexOf(index) + 1}. `}{choice.label}</span>
      </button>)}</div>
    {choices.length > limit && <button onClick={() => setLimit(old => old + 60)}>Weitere Optionen anzeigen ({choices.length - limit})</button>}
    {(prompt?.select || prompt?.counter) && <button disabled={disabled || !validCount} onClick={() => send('answer', { prompt: prompt.id, selected: selection })}>Auswahl bestätigen</button>}
    {prompt?.cancel && <button disabled={disabled} onClick={() => send('answer', { prompt: prompt.id, selected: [], cancel: true })}>{prompt.title === 'Auswahl ändern' ? 'Auswahl abschließen / abbrechen' : 'Auswahl abbrechen'}</button>}
    <button className="duel-surrender" disabled={disabled} onClick={() => { if (window.confirm('Duell wirklich aufgeben? Dein Gegner gewinnt und die Karten werden wieder freigegeben.')) send('surrender', {}) }}>Duell aufgeben</button>
  </section>
}
