import { setActionsLast } from './DuelActionLabel'
import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '../api/transport'
import { includeChoice, selectionComplete } from './duelSelection'
import { DuelSelectionProgress } from './DuelSelectionProgress'
import type { EngineCard } from './DuelWorkerTable'
import { CardOrigin } from '../components/CardSymbols'

export type DuelLocation = { owner: number; zone: number; sequence: number }
export type WorkerPrompt = { id: number; title: string; kind?: string; placement?: boolean; hint?: string; select?: boolean; ordered?: boolean; cancel?: boolean;
  effect_location?: DuelLocation;
  selection_progress?: { minimum: number; maximum: number; selected: number; can_finish: boolean };
  effect_card?: { code: number; name: string; image_url?: string; description?: string };
  counter?: boolean; counter_limits?: number[]; counter_total?: number; minimum?: number; maximum?: number;
  choices: { label: string; card: (Partial<EngineCard> & { name: string }) | null; action?: string; location?: DuelLocation }[] }

export function DuelDecisions({ prompt, disabled, send, zoneSelection = [], onZoneSelection, hideChoices = false, hideSurrender = false, attackTarget = false, choiceIndices, hideConfirmation = false, showOrigins=false, onPreview, onActivate, seat }: { prompt: WorkerPrompt | null | undefined; disabled: boolean; showOrigins?:boolean; seat?: number;
  onActivate?: (card: Partial<EngineCard> & { name: string }) => void;
  onPreview?: (card: Partial<EngineCard> & { name: string }, location?: DuelLocation) => void;
  hideConfirmation?: boolean;
  choiceIndices?: number[];
  hideChoices?: boolean; hideSurrender?: boolean; attackTarget?: boolean;
  zoneSelection?: number[]; onZoneSelection?: (value: number[]) => void;
  send: (kind: string, body: Record<string, unknown>, finishSelection?: boolean) => void }) {
  const [localSelection, setLocalSelection] = useState<number[]>([])
  const click = useRef<{ prompt: number; index: number; before: number[] } | null>(null)
  const pendingClick = useRef<ReturnType<typeof setTimeout> | null>(null)
  const list = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const element = list.current
    if (!element) return
    const wheel = (event: WheelEvent) => {
      if (!element.closest('.arena-card-choice-popup')) return
      if (element.scrollWidth <= element.clientWidth || Math.abs(event.deltaX) >= Math.abs(event.deltaY) || event.ctrlKey) return
      event.preventDefault()
      element.scrollLeft += event.deltaY * (event.deltaMode === 1 ? 20 : event.deltaMode === 2 ? element.clientWidth : 1)
    }
    element.addEventListener('wheel', wheel, { passive: false })
    return () => element.removeEventListener('wheel', wheel)
  }, [prompt?.id, hideChoices])
  useEffect(() => () => { if (pendingClick.current) clearTimeout(pendingClick.current) }, [prompt?.id])
  const chain = prompt?.kind === 'chain' || prompt?.title === 'Auf die Kette reagieren'
  useEffect(() => {
    if (chain) document.querySelector<HTMLButtonElement>('.duel-chain-overlay .duel-choice-list button')?.focus({ preventScroll: true })
  }, [prompt?.id, chain])
  const selection = onZoneSelection ? zoneSelection : localSelection
  const setSelection = (value: number[] | ((old: number[]) => number[])) => {
    const next = typeof value === 'function' ? value(selection) : value
    if (onZoneSelection) onZoneSelection(next); else setLocalSelection(next)
  }
  const [filter, setFilter] = useState(''), [limit, setLimit] = useState(60)
  useEffect(() => { click.current = null; setSelection(prompt?.counter ? prompt.choices.map(() => 0) : []) }, [prompt?.id])
  useEffect(() => { setFilter(''); setLimit(60) }, [prompt?.id])
  const choices = prompt?.choices.map((choice, index) => ({ choice, index })).filter(({ choice, index }) => (!choiceIndices || choiceIndices.includes(index)) && choice.label.toLocaleLowerCase('de').includes(filter.toLocaleLowerCase('de'))).sort((a, b) => setActionsLast(a.choice, b.choice)) || []
  const validCount = prompt?.counter ? selection.reduce((sum, value) => sum + value, 0) === prompt.counter_total :
    selection.length >= (prompt?.minimum || 0) && selection.length <= (prompt?.maximum || 0)
  const origin=(zone?:number)=>({1:'Deck',2:'Hand',4:'Spielfeld',8:'Spielfeld',16:'Friedhof',32:'Verbannt',64:'Extra-Deck'} as Record<number,string>)[zone || 0] || 'Karte'
  return <section className="deck-panel duel-decisions" aria-label="Spielentscheidung"><h2 tabIndex={-1}>{showOrigins ? prompt?.choices.every(choice => choice.location?.zone === 2) ? 'Handkarten für den Effekt auswählen' : 'Karten für den Effekt auswählen' : attackTarget ? 'Angriffsziel wählen' : prompt?.title || 'Warte auf den Gegner'}</h2>
    {showOrigins && <p className="duel-hand-choice-hint">Deine Hand enthält mögliche Karten für diese Auswahl. Wähle hier die benötigten Karten aus.</p>}
    {hideChoices && <p>Klicke die markierten Karten auf dem Spielfeld an. {selection.length} ausgewählt.</p>}
    {prompt?.hint && <p>{prompt.hint}</p>}
    {prompt && (prompt.select || prompt.counter || prompt.selection_progress) && <DuelSelectionProgress prompt={prompt} count={prompt.selection_progress?.selected ?? (prompt.counter ? selection.reduce((sum, value) => sum + value, 0) : selection.length)} />}
    {prompt?.ordered && <p>Klicke die Karten in der gewünschten Reihenfolge an.</p>}
    {prompt?.counter && <p>Verteile {prompt.counter_total} zu entfernende Zählmarken.</p>}
    {prompt && prompt.choices.length > 30 && <label>Karten / Optionen suchen<input value={filter} onChange={event => { setFilter(event.target.value); setLimit(60) }} /></label>}
    {!hideChoices && <div ref={list} className="duel-choice-list">{prompt && choices.slice(0, limit).map(({ choice, index }) => prompt.counter ?
      <label key={index}>{choice.label} · höchstens {prompt.counter_limits?.[index]}<input type="number" min={0} max={prompt.counter_limits?.[index]} value={selection[index] || 0} disabled={disabled} onChange={event => setSelection(old => old.map((value, i) => i === index ? Math.max(0, Math.min(prompt.counter_limits?.[index] || 0, Math.floor(Number(event.target.value)))) : value))} /></label> :
      <button key={index} data-duel-action={choice.action} data-choice-zone={choice.location?.zone} data-choice-owner={choice.location?.owner} aria-description={choice.location ? `${seat !== undefined && choice.location.owner !== seat ? 'Gegner: ' : ''}${origin(choice.location.zone)}` : undefined} className={!disabled && (choice.action === 'activate' || (chain && choice.card) || (prompt.effect_location && choice.label === 'Ja')) ? 'effect-available' : undefined} disabled={disabled} aria-pressed={prompt.select ? selection.includes(index) : undefined} onClick={event => {
        if (disabled || event.detail > 1) return
        if (choice.card) onPreview?.(choice.card, choice.location)
        if (choice.card && !prompt.select && !prompt.selection_progress && (choice.action === 'activate' || chain)) onActivate?.(choice.card)
        if (prompt.selection_progress) {
          if (pendingClick.current) clearTimeout(pendingClick.current)
          pendingClick.current = setTimeout(() => { pendingClick.current = null; send('answer', { prompt: prompt.id, selected: [index] }) }, 300)
          return
        }
        if (!prompt.select) { send('answer', { prompt: prompt.id, selected: [index] }); return }
        click.current = { prompt: prompt.id, index, before: [...selection] }
        setSelection(old => old.includes(index) ? old.filter(i => i !== index) : includeChoice(old, index, prompt.maximum || 0))
      }} onDoubleClick={() => {
        if (disabled) return
        if (prompt.selection_progress) {
          if (pendingClick.current) clearTimeout(pendingClick.current)
          pendingClick.current = null
          send('answer', { prompt: prompt.id, selected: [index] }, true)
          return
        }
        if (!prompt.select) return
        const before = click.current?.prompt === prompt.id && click.current.index === index ? click.current.before : selection
        const next = includeChoice(before, index, prompt.maximum || 0)
        setSelection(next)
        if (next.includes(index) && selectionComplete(next, prompt.minimum || 0, prompt.maximum || 0)) send('answer', { prompt: prompt.id, selected: next })
      }}>
        {choice.card?.image_url && <img className="duel-chain-card" src={API_BASE_URL.replace(/\/api\/?$/, '') + choice.card.image_url} alt="" onError={event => { event.currentTarget.hidden = true }} />}
        <span>{prompt.ordered && selection.includes(index) && `${selection.indexOf(index) + 1}. `}{choice.label}</span>
        {choice.card && choice.location && <div className="duel-choice-origin" aria-hidden="true"><CardOrigin zone={choice.location.zone} opponent={seat !== undefined && choice.location.owner !== seat} /></div>}
      </button>)}</div>}
    {choices.length > limit && <button onClick={() => setLimit(old => old + 60)}>Weitere Optionen anzeigen ({choices.length - limit})</button>}
    {!hideConfirmation && (prompt?.select || prompt?.counter) && <button disabled={disabled || !validCount} onClick={() => send('answer', { prompt: prompt.id, selected: selection })}>{attackTarget ? 'Angriff bestätigen' : 'Auswahl bestätigen'}</button>}
    {!hideConfirmation && prompt?.select && selection.length > 0 && <button disabled={disabled} onClick={() => setSelection([])}>Auswahl zurücksetzen</button>}
    {prompt?.cancel && <button disabled={disabled} onClick={() => send('answer', { prompt: prompt.id, selected: [], cancel: true })}>{prompt.selection_progress?.can_finish ? 'Auswahl bestätigen' : 'Auswahl abbrechen'}</button>}
    {!hideSurrender && <button className="duel-surrender" disabled={disabled} onClick={() => { if (window.confirm('Duell wirklich aufgeben? Dein Gegner gewinnt und die Karten werden wieder freigegeben.')) send('surrender', {}) }}>Duell aufgeben</button>}
  </section>
}
