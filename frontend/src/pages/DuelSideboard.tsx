import { useEffect, useState } from 'react'

type Sections = Record<'main' | 'extra' | 'side', number[]>
export type MatchProgress = { version: number; game: number; phase: string; score: number[];
  ready: boolean[]; chooser: number | null; next_starter: number | null; decks?: Sections;
  cards?: Record<string, { name: string; type: number }> }
const labels = { main: 'Hauptdeck', extra: 'Extra-Deck', side: 'Side-Deck' }

export function DuelSideboard({ match, seat, disabled, send }: { match: MatchProgress; seat: number;
  disabled: boolean; send: (kind: string, body: Record<string, unknown>) => void }) {
  const [sections, setSections] = useState<Sections>({ main: [], extra: [], side: [] })
  const [starter, setStarter] = useState<number | null>(null)
  useEffect(() => {
    if (match.decks) setSections(structuredClone(match.decks))
  }, [match.game, JSON.stringify(match.decks), match.ready[seat]])
  useEffect(() => { setStarter(match.next_starter) }, [match.next_starter])
  function move(from: keyof Sections, index: number, to: keyof Sections) {
    setSections(old => {
      const next = structuredClone(old), [code] = next[from].splice(index, 1)
      next[to].push(code); return next
    })
  }
  const correctSizes = match.decks && (Object.keys(labels) as (keyof Sections)[]).every(key => sections[key].length === match.decks![key].length)
  return <section className="deck-panel duel-sideboard"><h2>Sideboarding nach Spiel {match.game}</h2>
    <p>Du kannst ausschließlich die reservierten Karten austauschen. Alle drei Bereiche müssen ihre Anfangsgröße behalten. Deine Liste bleibt privat.</p>
    <p role="status">Du: {match.ready[seat] ? 'bereit' : 'in Vorbereitung'} · Gegner: {match.ready[1 - seat] ? 'bereit' : 'in Vorbereitung'}</p>
    {(Object.keys(labels) as (keyof Sections)[]).map(section => <details key={section} open><summary>{labels[section]} ({sections[section].length}/{match.decks?.[section].length})</summary>
      <ul>{sections[section].map((code, index) => <li key={`${code}:${index}`}><span>{match.cards?.[code]?.name || code}</span> <select aria-label={`${match.cards?.[code]?.name || code} verschieben`} value={section} disabled={disabled || match.ready[seat]} onChange={event => move(section, index, event.target.value as keyof Sections)}>
        {(Object.keys(labels) as (keyof Sections)[]).filter(target => target === 'side' || Boolean((match.cards?.[code]?.type || 0) & (0x40 | 0x2000 | 0x800000 | 0x4000000)) === (target === 'extra')).map(target => <option key={target} value={target}>{labels[target]}</option>)}
      </select></li>)}</ul></details>)}
    {match.chooser === seat ? <label>Wer beginnt das nächste Spiel?<select value={starter ?? ''} disabled={disabled || match.ready[seat]} onChange={event => setStarter(Number(event.target.value))}><option value="" disabled>Bitte auswählen</option><option value={seat}>Ich beginne</option><option value={1 - seat}>Mein Gegner beginnt</option></select></label> : <p>Der berechtigte Gegner wählt den Startspieler.</p>}
    <button disabled={disabled || (!match.ready[seat] && (!correctSizes || (match.chooser === seat && starter === null)))} onClick={() => send('sideboard', { version: match.version, sections, ready: !match.ready[seat], ...(match.chooser === seat ? { starter } : {}) })}>{match.ready[seat] ? 'Bereit zurücknehmen' : 'Side-Deck bestätigen und bereit'}</button>
    <button disabled={disabled} onClick={() => { if (window.confirm('Das gesamte Match aufgeben?')) send('surrender', {}) }}>Match aufgeben</button>
  </section>
}
