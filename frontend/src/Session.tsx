import logoUrl from './assets/sdoycc-logo.png'
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, sessionToken, setSessionToken, jsonPost } from './api/transport'

export type HubUser = { id: number; username: string; display_name: string; role: string; diamonds: number; twitch_id: string | null }
type AuthConfig = { auth_mode: 'password'; streamerbot_enabled: boolean; demo_enabled: boolean; channel: string; reward_cost: number; reward_points: number; currency: string }
type SessionState = { revision: number; user: HubUser | null; config: AuthConfig | null; loading: boolean; error: string; refresh: () => Promise<void>; logout: () => Promise<void> }
const SessionContext = createContext<SessionState | null>(null)
export function useSession() { return useContext(SessionContext)! }

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<HubUser | null>(null)
  const [config, setConfig] = useState<AuthConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const refresh = useCallback(async () => {
    const token = sessionToken()
    if (!token) { setUser(null); setLoading(false); return }
    try {
      const next = await api<HubUser>('/users/me')
      if (token === sessionToken()) { setUser(current => current && JSON.stringify(current) === JSON.stringify(next) ? current : next); setError('') }
    } catch (cause) {
      if (token === sessionToken()) setError(cause instanceof Error ? cause.message : 'Konto konnte nicht geladen werden')
    } finally { setLoading(false) }
  }, [])
  useEffect(() => {
    api<AuthConfig>('/auth/config').then(setConfig).catch(cause => setError(String(cause.message)))
    void refresh()
    const listener = () => { setRevision(value => value + 1); void refresh() }
    const visible = () => { if (document.visibilityState === 'visible') void refresh() }
    const timer = window.setInterval(visible, 30000)
    window.addEventListener('hub-data-changed', listener)
    window.addEventListener('hub-session-changed', listener)
    document.addEventListener('visibilitychange', visible)
    return () => {
      clearInterval(timer)
      window.removeEventListener('hub-data-changed', listener)
      window.removeEventListener('hub-session-changed', listener)
      document.removeEventListener('visibilitychange', visible)
    }
  }, [refresh])
  const logout = async () => {
    try { await api('/auth/logout', { method: 'POST' }); setSessionToken(null); setUser(null) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Abmeldung fehlgeschlagen') }
  }
  return <SessionContext.Provider value={{ user, config, loading, error, refresh, logout, revision }}>{children}</SessionContext.Provider>
}

export function LoginPage() {
  const { config, error, loading } = useSession()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const login = async (demo = false) => {
    if (busy) return
    setBusy(true); setActionError('')
    try {
      const result = demo ? await api<{ token: string }>('/auth/demo') : await api<{ token: string }>('/auth/login', jsonPost({ username, password }))
      setPassword(''); setSessionToken(result.token)
    } catch (cause) { setActionError(cause instanceof Error ? cause.message : 'Anmeldung fehlgeschlagen') }
    finally { setBusy(false) }
  }
  return <main className="login-page"><section className="login-panel"><img className="auth-brand-logo" src={logoUrl} width="1254" height="1254" alt="SDOYCC – SamDavidOfficial’s Yu-Gi-Oh Card Collector" />
    <h1>Dein Stream.<br />Deine Kartensammlung.</h1>
    <p>Melde dich mit deinem Twitch-Benutzernamen und deinem Hub-Passwort an.</p>
    {(error || actionError) && <div className="api-notice" role="alert">{actionError || error}</div>}
    {loading ? <p role="status">Konto wird geladen …</p> : <form className="auth-form" onSubmit={event => { event.preventDefault(); void login() }}>
      <label>Twitch-Benutzername<input autoComplete="username" required maxLength={64} value={username} onChange={event => setUsername(event.target.value)} /></label>
      <label>Passwort<input type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={event => setPassword(event.target.value)} /></label>
      <button className="primary-button" disabled={busy} type="submit">{busy ? 'Wird angemeldet …' : 'Anmelden'}</button>
    </form>}
    <div className="registration-help"><strong>Noch kein Konto?</strong><p>Schreibe <code>!register</code> im Twitch-Chat von {config?.channel || 'SamDavidOfficial'} oder löse dort die Sammelpunkte-Belohnung ein. Öffne den Link aus der öffentlichen Chat-Antwort und bestätige den Code von dieser Seite mit <code>!confirm CODE</code> im Chat. Danach legst du dein Hub-Passwort fest.</p></div>
    {config?.demo_enabled && <button className="outline-button" disabled={busy} onClick={() => void login(true)}>Lokale Demo öffnen</button>}
    {error && <button className="outline-button" onClick={() => window.location.reload()}>Erneut laden</button>}
    <small>{config?.reward_cost.toLocaleString('de-DE') || '1.000'} Kanalpunkte ergeben {config?.reward_points || 100} Sammelpunkte. Vorhandene Booster öffnest du kostenlos.</small>
  </section></main>
}
