import logoUrl from '../assets/sdoycc-logo.png'
import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { api, jsonPost, setSessionToken } from '../api/transport'

type Challenge = { token: string; code: string; username: string; channel: string; expires_at: string; expires_in_minutes: number }
type Identity = { username: string; display_name: string; confirmed: boolean }

export function RegistrationPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const username = (location.pathname.split('/')[2] || '').toLowerCase()
  const storageKey = `hub-registration:${username}`
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [identity, setIdentity] = useState<Identity | null>(null)
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [polling, setPolling] = useState(false)
  const validName = /^[a-z0-9_]{1,25}$/.test(username)

  useEffect(() => {
    setChallenge(null); setIdentity(null); setError(''); setPassword(''); setConfirmation('')
    try {
      const stored = JSON.parse(sessionStorage.getItem(storageKey) || 'null') as Challenge | null
      if (stored && stored.username === username && Date.parse(stored.expires_at) > Date.now()) setChallenge(stored)
      else sessionStorage.removeItem(storageKey)
    } catch { sessionStorage.removeItem(storageKey) }
  }, [storageKey, username])

  useEffect(() => {
    if (!challenge || challenge.username !== username) return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const check = async () => {
      setPolling(true)
      try {
        const next = await api<Identity>('/auth/register/inspect', jsonPost({ username, token: challenge.token }))
        if (!active) return
        setIdentity(next); setError('')
        if (!next.confirmed) timer = setTimeout(() => { void check() }, 3000)
        else setPolling(false)
      } catch (cause) {
        if (active) { setError(cause instanceof Error ? cause.message : 'Bestätigung konnte nicht geprüft werden.'); setPolling(false) }
      }
    }
    void check()
    return () => { active = false; clearTimeout(timer) }
  }, [challenge, username])

  const start = async () => {
    if (busy || !validName) return
    setBusy(true); setError('')
    try {
      const next = await api<Challenge>('/auth/register/start', jsonPost({ username }))
      sessionStorage.setItem(storageKey, JSON.stringify(next))
      setIdentity(null); setChallenge(next); setPassword(''); setConfirmation('')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Registrierung konnte nicht gestartet werden.') }
    finally { setBusy(false) }
  }
  const register = async () => {
    if (busy || !identity?.confirmed || !challenge) return
    if (password !== confirmation) { setError('Die Passwörter stimmen nicht überein.'); return }
    setBusy(true); setError('')
    try {
      const result = await api<{ token: string }>('/auth/register', jsonPost({ username, token: challenge.token, password }))
      sessionStorage.removeItem(storageKey)
      setPassword(''); setConfirmation(''); setSessionToken(result.token)
      navigate('/', { replace: true })
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Registrierung fehlgeschlagen') }
    finally { setBusy(false) }
  }
  return <main className="login-page"><section className="login-panel"><img className="auth-brand-logo" src={logoUrl} width="1254" height="1254" alt="SDOYCC – SamDavidOfficial’s Yu-Gi-Oh Card Collector" />
    <p className="eyebrow accent">DEIN TWITCH-KONTO · DEINE SAMMLUNG</p>
    <h1>Willkommen im Hub.</h1>
    <p>Bestätige dein Twitch-Konto im Chat. Anschließend legst du dein Hub-Passwort fest.</p>
    {error && <div className="api-notice" role="alert">{error}</div>}
    {!validName ? <p>Bitte öffne den vollständigen Registrierungslink aus dem Twitch-Chat.</p> : <>
      <div className="auth-form"><label>Twitch-Benutzername<input value={username} readOnly autoComplete="username" /></label></div>
      {!challenge && <button className="primary-button" disabled={busy} onClick={() => void start()}>{busy ? 'Code wird erstellt …' : 'Bestätigungscode erstellen'}</button>}
      {challenge && !identity?.confirmed && <div className="registration-help">
        <strong>Bestätige diesen Browser im Twitch-Chat</strong>
        <p>Sende mit <strong>@{username}</strong> im Kanal <strong>{challenge.channel}</strong> genau diesen Befehl:</p>
        <p><code data-testid="confirmation-command">!confirm {challenge.code}</code></p>
        <p>Gültig für {challenge.expires_in_minutes} Minuten. Verwende nur den Code, den du selbst auf dieser Seite angefordert hast.</p>
        {polling && <p role="status">Warte auf deine Chat-Bestätigung …</p>}
        {!polling && error && <button className="outline-button" onClick={() => setChallenge({ ...challenge })}>Status erneut prüfen</button>}
        <button className="outline-button" disabled={busy} onClick={() => void start()}>Neuen Code erstellen</button>
      </div>}
      {identity?.confirmed && <form className="auth-form" onSubmit={event => { event.preventDefault(); void register() }}>
        <p role="status">Twitch-Konto bestätigt. Lege jetzt dein Passwort fest.</p>
        <label>Neues Passwort<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={event => setPassword(event.target.value)} /></label>
        <small>Mindestens 12 Zeichen. Verwende ein eigenes Passwort für den Hub.</small>
        <label>Passwort wiederholen<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
        <button className="primary-button" type="submit" disabled={busy}>{busy ? 'Konto wird aktiviert …' : 'Passwort festlegen & starten'}</button>
      </form>}
    </>}
    <NavLink className="outline-button" to="/">Zur Anmeldung</NavLink>
    <small>Bereits gutgeschriebene Sammelpunkte bleiben erhalten. Nach der Registrierung meldest du dich mit Twitch-Benutzername und Hub-Passwort an.</small>
  </section></main>
}