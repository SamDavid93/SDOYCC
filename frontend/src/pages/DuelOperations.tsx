import { useState } from 'react'
import { Confirm, ErrorBox, useAction, useRead } from '../components/Workflow'
import { DuelControls } from './DuelControls'

type Run = { id: string; state: string; age_seconds: number; local: boolean; process_evidence: boolean }
type Admission = { accepting_new: boolean; version: number; active_matches: number; max_active_matches: number; available_slots: number }

export function DuelOperations({ owner }: { owner: boolean }) {
  const [revision, setRevision] = useState(0), [selected, setSelected] = useState<Run | null>(null)
  const [message, setMessage] = useState(''), action = useAction()
  const [policyTarget, setPolicyTarget] = useState<{ accepting_new: boolean; version: number } | null>(null)
  const status = useRead<{ enabled: boolean; admission: Admission; runs: Run[] }>('/admin/duels/operations', revision)
  async function changePolicy(password: string, reason: string) {
    if (!policyTarget) return
    const value = await action.run<Admission>('/admin/duels/policy', { ...policyTarget, password, reason })
    if (value) { setPolicyTarget(null); setRevision(n => n + 1); setMessage(value.accepting_new ? 'Neue Duelle wieder zugelassen.' : 'Neue Duelle pausiert. Laufende Matches bleiben spielbar.') }
  }
  async function execute(password: string, reason: string) {
    if (!selected) return
    const value = await action.run(`/admin/duels/runs/${selected.id}/${selected.local ? 'abort' : 'recover'}`, { password, reason })
    if (value) { setSelected(null); setRevision(n => n + 1); setMessage('Prozessstopp bestätigt. Das Duell ist abgeschlossen und die Karten sind freigegeben.') }
  }
  return <><section className="content-panel"><h2>Duellbetrieb</h2><ErrorBox message={status.error || action.error} />
    {message && <p role="status">{message}</p>}
    <p>{status.data?.enabled ? 'Geschlossener Duellworker aktiv' : 'Duellworker ausgeschaltet'}</p>
    {status.data && <div><p>{status.data.admission.active_matches} von {status.data.admission.max_active_matches} Duellplätzen belegt · {status.data.admission.accepting_new ? 'Neue Duelle zugelassen' : 'Wartung: neue Duelle pausiert'}</p>
      {owner && <button className="outline-button" disabled={action.busy} onClick={() => status.data && setPolicyTarget({ accepting_new: !status.data.admission.accepting_new, version: status.data.admission.version })}>{status.data.admission.accepting_new ? 'Neue Duelle pausieren' : 'Neue Duelle wieder zulassen'}</button>}
    </div>}
    {status.data?.runs.map(run => <article key={run.id}><h3>Duell {run.id.slice(0, 8)}</h3>
      <p>{run.local ? 'Lokaler Prozess' : 'Wiederanlaufprüfung erforderlich'} · {Math.floor(run.age_seconds / 60)} Minuten</p>
      <p>{run.process_evidence ? 'Prozessidentität dokumentiert' : 'Kein automatischer Prozessnachweis vorhanden'}</p>
      {owner && status.data?.enabled && <button className="outline-button" onClick={() => setSelected(run)}>{run.local ? 'Technisch abbrechen' : 'Prozessstopp prüfen'}</button>}
    </article>)}
    {status.data && !status.data.runs.length && <p>Keine offenen Duellprozesse.</p>}
    <button className="outline-button" onClick={() => setRevision(n => n + 1)}>Duellbetrieb aktualisieren</button>
    {selected && <Confirm title={selected.local ? 'Duell ohne Wertung abbrechen' : 'Verwaisten Duellprozess prüfen'} admin busy={action.busy} error={action.error} close={() => setSelected(null)} confirm={(password, reason) => void execute(password, reason)}>
      <p>Die Aktion wird protokolliert. Karten werden ausschließlich nach nachgewiesenem Prozessstopp freigegeben. Eine laufende fremde Serverinstanz wird nicht übernommen.</p>
    </Confirm>}
    {policyTarget && <Confirm title={policyTarget.accepting_new ? 'Neue Duelle wieder zulassen' : 'Duellbetrieb in Wartung setzen'} admin busy={action.busy} error={action.error} close={() => setPolicyTarget(null)} confirm={(password, reason) => void changePolicy(password, reason)}>
      <p>Die Änderung wird mit deiner Begründung protokolliert. Laufende Duelle und Sideboarding bleiben unverändert. Dieser Schalter aktiviert keinen ausgeschalteten Worker.</p>
    </Confirm>}
  </section><DuelControls owner={owner} /></>
}
