import { useEffect, useState } from 'react'
import { api } from '../api/transport'
import { ErrorBox, Pager, useRead, type Page } from '../components/Workflow'

type Receipt = { id: string; state: string; reason: string; ended_at: string; seat: number; winner_seat: number | null; replay_available: boolean; match?: { score: number[]; game: number } | null }
type Frame = { revision: number; seat: number; game?: number; turn_number: number; boards: { lp: number; hand: ({ name: string } | null)[]; field: { card: { name: string } | null }[] }[] }
type Replay = Receipt & { format: string; frames: Frame[]; truncated: boolean; expires_at: string }

export function DuelHistory() {
  const [page, setPage] = useState(1), [selected, setSelected] = useState<Replay | null>(null)
  const [index, setIndex] = useState(0), [playing, setPlaying] = useState(false), [error, setError] = useState('')
  const history = useRead<Page<Receipt>>('/duel-zone/history?page=' + page)
  useEffect(() => {
    if (!playing || !selected) return
    const timer = setInterval(() => setIndex(old => { if (old >= selected.frames.length - 1) { setPlaying(false); return old } return old + 1 }), 800)
    return () => clearInterval(timer)
  }, [playing, selected])
  async function open(id: string) {
    try { const replay = await api<Replay>(`/duel-zone/history/${id}/replay`); setSelected(replay); setIndex(0); setPlaying(false); setError('') }
    catch (cause) { setError((cause as Error).message) }
  }
  function download() {
    if (!selected || !window.confirm('Der Download enthält deine damals sichtbaren Karten einschließlich deiner Hand. Wenn du die Datei weitergibst, teilst du diese Informationen bewusst. Fortfahren?')) return
    const url = URL.createObjectURL(new Blob([JSON.stringify(selected, null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `sdoycc-duell-${selected.id}.json`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const frame = selected?.frames[index]
  return <details className="deck-panel duel-history"><summary>Meine abgeschlossenen Duelle</summary>
    <ErrorBox message={error || history.error} />
    {history.data?.items.map(row => <article key={row.id}><p>{new Date(row.ended_at).toLocaleString('de-DE')} · {row.state === 'aborted' ? 'Ohne Wertung abgebrochen' : row.winner_seat === null ? 'Unentschieden' : row.winner_seat === row.seat ? 'Gewonnen' : 'Verloren'}</p>
      {row.match && <p>Match: {row.match.score[row.seat]} : {row.match.score[1-row.seat]} · {row.match.game} Spiele</p>}
      <button disabled={!row.replay_available} onClick={() => void open(row.id)}>{row.replay_available ? 'Privaten Spielverlauf ansehen' : 'Spielverlauf nicht verfügbar'}</button>
    </article>)}
    {history.data && !history.data.items.length && <p>Noch keine abgeschlossenen Duelle.</p>}
    {history.data && <Pager page={page} setPage={setPage} total={history.data.total} />}
    {selected && <section aria-label="Privater Duellspielverlauf"><h2>Deine damalige Ansicht</h2><p>Der Verlauf zeigt nur die für dich sichtbaren Spielstände. Verdeckte gegnerische Informationen bleiben verborgen. Aufbewahrung bis {new Date(selected.expires_at).toLocaleDateString('de-DE')}.</p>
      {selected.truncated && <p>Der Verlauf endet vor dem Duellabschluss, weil das Speicherlimit erreicht wurde.</p>}
      <label>Spielstand {index + 1} von {selected.frames.length}<input type="range" min={0} max={Math.max(0, selected.frames.length - 1)} value={index} onChange={event => { setPlaying(false); setIndex(Number(event.target.value)) }} /></label>
      <div className="deck-actions"><button disabled={!selected.frames.length} onClick={() => setPlaying(!playing)}>{playing ? 'Pause' : 'Abspielen'}</button><button onClick={download}>Spielverlauf herunterladen</button><button onClick={() => { setPlaying(false); setSelected(null) }}>Verlauf schließen</button></div>
      {frame && <><p>{frame.game ? `Spiel ${frame.game} · ` : ''}Zug {frame.turn_number} · Spielstand {frame.revision}</p>{frame.boards.map((side, seat) => <article key={seat}><h3>{seat === frame.seat ? 'Deine Seite' : 'Gegnerische Seite'} · {side.lp} LP</h3><p>Hand: {side.hand.map(card => card?.name || 'Verdeckt').join(' · ') || 'Leer'}</p><p>Feld: {side.field.map(entry => entry.card?.name || 'Verdeckt').join(' · ') || 'Leer'}</p></article>)}</>}
    </section>}
  </details>
}
