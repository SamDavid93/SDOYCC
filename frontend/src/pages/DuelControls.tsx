import { useState } from 'react'
import { Confirm, ErrorBox, SearchPick, useAction, useRead } from '../components/Workflow'

type Profile = { id: string; name: string; list_name: string; version: number; evidence: string; engine_approved: boolean; region_approved: boolean; worker_compatible: boolean; official_regional_reference: boolean }
type Restriction = { user_id: number; username: string; display_name: string; active: boolean; until: string | null; reason: string; version: number }
type Pending = { path: string; title: string; body: Record<string, unknown> }

export function DuelControls({ owner }: { owner: boolean }) {
  const [revision, setRevision] = useState(0), [profileId, setProfileId] = useState('')
  const [engine, setEngine] = useState(false), [region, setRegion] = useState(false), [evidence, setEvidence] = useState('')
  const [userId, setUserId] = useState<number | null>(null), [hours, setHours] = useState(24)
  const [pending, setPending] = useState<Pending | null>(null), [message, setMessage] = useState('')
  const profiles = useRead<{ items: Profile[] }>('/admin/duels/rule-profiles', revision)
  const restriction = useRead<Restriction>(userId ? `/admin/duels/restrictions/${userId}` : null, revision)
  const action = useAction(), selected = profiles.data?.items.find(profile => profile.id === profileId)
  function choose(id: string) {
    const profile = profiles.data?.items.find(profile => profile.id === id)
    setProfileId(id); setEngine(profile?.engine_approved || false); setRegion(profile?.region_approved || false); setEvidence(profile?.evidence || '')
  }
  async function execute(password: string, reason: string) {
    if (!pending) return
    const result = await action.run(pending.path, { ...pending.body, password, reason })
    if (result) { setPending(null); setRevision(value => value + 1); setMessage('Duellverwaltung gespeichert und protokolliert.') }
  }
  return <section className="content-panel"><h2>Duellregeln & Duellsperren</h2>
    <ErrorBox message={profiles.error || restriction.error || action.error} />
    {message && <p role="status">{message}</p>}
    <label>Versioniertes Regelprofil<select aria-label="Versioniertes Regelprofil" value={profileId} onChange={event => choose(event.target.value)}><option value="">Regelstand wählen</option>
      {profiles.data?.items.map(profile => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
    </select></label>
    {selected && <div><p>Liste: {selected.list_name}</p>
      <p>{selected.worker_compatible ? 'Passt zum installierten Worker.' : 'Für eine neue Engine-Freigabe muss der passende Worker aktiv sein.'}</p>
      <p>{selected.official_regional_reference ? 'Offizieller EU-Listenstand ist im Import dokumentiert.' : 'Die Regionsfreigabe benötigt einen offiziellen EU-Listenimport.'}</p>
      <label className="workflow-check"><input type="checkbox" checked={engine} disabled={!owner || (!selected.engine_approved && !selected.worker_compatible)} onChange={event => setEngine(event.target.checked)} />Engine-Abnahme bestätigt</label>
      <label className="workflow-check"><input type="checkbox" checked={region} disabled={!owner || (!selected.region_approved && !selected.official_regional_reference)} onChange={event => setRegion(event.target.checked)} />Europäische Karten- und Formatfreigabe bestätigt</label>
      <label>Abnahmenachweise und Quellen<textarea maxLength={2000} value={evidence} disabled={!owner} onChange={event => setEvidence(event.target.value)} /></label>
      {owner && <button disabled={action.busy || evidence.trim().length < 10} className="outline-button" onClick={() => setPending({ path: `/admin/duels/rule-profiles/${selected.id}`, title: 'Regelfreigabe dokumentieren', body: { version: selected.version, engine_approved: engine, region_approved: region, evidence } })}>Regelfreigabe prüfen</button>}
    </div>}
    <SearchPick path="/admin/users?state=all&role=all" title="Konto für Duellsperre suchen" choose={user => setUserId(user.id)} />
    {restriction.data && <div><h3>@{restriction.data.username}</h3><p>{restriction.data.active && restriction.data.until ? `Duellsperre bis ${new Date(restriction.data.until).toLocaleString('de-DE')}` : 'Keine aktive Duellsperre'}</p>
      {restriction.data.reason && <p>Letzte Begründung: {restriction.data.reason}</p>}
      {owner && <><label>Sperrdauer in Stunden<input type="number" min="1" max="8760" value={hours} onChange={event => setHours(Number(event.target.value))} /></label>
        <button className="outline-button" disabled={action.busy || !Number.isInteger(hours) || hours < 1 || hours > 8760} onClick={() => restriction.data && setPending({ path: `/admin/duels/restrictions/${restriction.data.user_id}`, title: `Duellsperre für @${restriction.data.username}`, body: { hours, version: restriction.data.version } })}>Duellsperre festlegen</button>
        <button className="outline-button" disabled={action.busy || !restriction.data.active} onClick={() => restriction.data && setPending({ path: `/admin/duels/restrictions/${restriction.data.user_id}`, title: `Duellsperre für @${restriction.data.username} aufheben`, body: { hours: 0, version: restriction.data.version } })}>Duellsperre aufheben</button>
      </>}
    </div>}
    {pending && <Confirm title={pending.title} admin busy={action.busy} error={action.error} close={() => setPending(null)} confirm={(password, reason) => void execute(password, reason)}>
      <p>{pending.path.includes('/restrictions/') ? 'Die Sperre betrifft ausschließlich Duelle. Guthaben, Karten und andere Hub-Funktionen bleiben erhalten. Laufende Duelle werden nach sicherem Prozessstopp ohne Wertung beendet.' : 'Die Änderung gilt für dieses unveränderliche Regelprofil. Entzogene Freigaben beenden betroffene laufende Duelle ohne Wertung. Quellenangaben ersetzen keine tatsächliche Abnahme oder Nutzungsrechte.'}</p>
    </Confirm>}
  </section>
}
