import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useSession } from '../Session'
import { type ApiCard, toCardRecord } from '../api/client'
import { CardVisual } from '../components/CardVisual'
import { ErrorBox, useAction, useRead } from '../components/Workflow'
import './decks.css'

type Template = { id: string; name: string; deck_version: number; expires_at: string; revoked: boolean }
const linkFor = (id: string) => new URL(`${window.location.pathname}#/deck-template/${id}`, window.location.origin).href

export function DeckSharing({ deckId, version, disabled }: { deckId: string; version: number; disabled: boolean }) {
  const [revision, setRevision] = useState(0), [message, setMessage] = useState('')
  const list = useRead<Template[]>('/deck-templates/mine/' + deckId, revision), action = useAction()
  async function share() {
    if (!window.confirm('Gespeicherte Deckliste als Vorlage teilen? Jeder mit dem Link kann diese Version 30 Tage ansehen und kopieren. Deine Notizen und Bestände bleiben privat.')) return
    const result = await action.run<Template>('/deck-templates/decks/' + deckId, { version })
    if (result) { setRevision(n => n + 1); setMessage('Freigabelink erstellt. Spätere Änderungen deines Decks verändern diese Vorlage nicht.') }
  }
  async function copyLink(id: string) {
    try { await navigator.clipboard.writeText(linkFor(id)); setMessage('Vorlagenlink kopiert.') }
    catch { setMessage('Link bitte aus dem sichtbaren Feld kopieren.') }
  }
  async function revoke(id: string) {
    const result = await action.run('/deck-templates/' + id + '/revoke')
    if (result) { setRevision(n => n + 1); setMessage('Link widerrufen. Bereits kopierte Deckentwürfe bleiben bei ihren Besitzern.') }
  }
  return <details className="deck-share-panel"><summary>Deckvorlagen teilen</summary><p>Teile bewusst eine gespeicherte Deckversion. Notizen und Kartenbesitz werden nicht geteilt.</p>
    <ErrorBox message={list.error || action.error} />{message && <p role="status">{message}</p>}
    <button disabled={disabled || action.busy} onClick={() => void share()}>Freigabelink erstellen</button>
    {list.data?.map(template => <article key={template.id}><p>Version {template.deck_version} · bis {new Date(template.expires_at).toLocaleDateString('de-DE')}</p>
      <label>Vorlagenlink<input readOnly value={linkFor(template.id)} onFocus={event => event.currentTarget.select()} /></label>
      <div className="deck-actions"><button onClick={() => void copyLink(template.id)}>Link kopieren</button><button disabled={action.busy} onClick={() => void revoke(template.id)}>Link widerrufen</button></div>
    </article>)}
  </details>
}

export function DeckTemplatePage({ id }: { id: string }) {
  const { user } = useSession(), navigate = useNavigate(), action = useAction()
  const template = useRead<Template & { entries: { card_id: number; quantity: number; section: string }[]; cards: Record<number, ApiCard> }>('/deck-templates/' + id)
  async function copy() {
    const result = await action.run<{ id: string }>('/deck-templates/' + id + '/copy')
    if (result) navigate('/decks/' + result.id)
  }
  return <main className="page-wrap decks-page"><NavLink to="/decks">← Meine Decks</NavLink><h1>{template.data?.name || 'Geteilte Deckvorlage'}</h1>
    <ErrorBox message={template.error || action.error} />
    {!template.data && !template.error && <p role="status">Vorlage laden …</p>}
    {template.data && <><p>Version {template.data.deck_version} · bis {new Date(template.data.expires_at).toLocaleDateString('de-DE')}. Beim Kopieren werden keine Karten vergeben. Dein eigener Besitz und die aktuellen Regeln werden geprüft.</p>
      {user ? <button className="primary-button" disabled={action.busy} onClick={() => void copy()}>Als eigenen Deckentwurf kopieren</button> : <p>Zum Kopieren bitte <NavLink to="/">am Hub anmelden</NavLink> und danach diesen Link erneut öffnen.</p>}
      {['main', 'extra', 'side'].map(section => <section className="deck-panel" key={section}><h2>{({ main: 'Hauptdeck', extra: 'Extra-Deck', side: 'Side-Deck' } as Record<string, string>)[section]}</h2>
        <div className="deck-list">{template.data!.entries.filter(entry => entry.section === section).map(entry => <article key={entry.card_id}><p>{entry.quantity} × {template.data!.cards[entry.card_id]?.name}</p><div style={{ maxWidth: 140 }}><CardVisual card={toCardRecord(template.data!.cards[entry.card_id])} compact /></div></article>)}</div>
      </section>)}
    </>}
  </main>
}
