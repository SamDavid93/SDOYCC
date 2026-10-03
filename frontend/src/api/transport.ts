export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002/api'
const tokenKey = 'hub-session'
const reads = new Map<string, { until: number; request: Promise<Response> }>()
const pending = new Map<string, string>()

export function sessionToken() { return sessionStorage.getItem(tokenKey) }
export function setSessionToken(token: string | null) {
  if (token) sessionStorage.setItem(tokenKey, token)
  else sessionStorage.removeItem(tokenKey)
  pending.clear()
  reads.clear()
  window.dispatchEvent(new Event('hub-session-changed'))
}

async function networkFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers)
  const token = sessionToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.method && options.method !== 'GET') reads.clear()
  const isAction = options.method === 'POST' && /\/(purchase|open)$/.test(url)
  const action = `${token}:${url}:${String(options.body || '')}`
  if (isAction) {
    if (!pending.has(action)) pending.set(action, crypto.randomUUID())
    headers.set('Idempotency-Key', pending.get(action)!)
  }
  let response: Response
  try {
    response = await fetch(url, { ...options, headers, signal: options.signal || AbortSignal.timeout(20000) })
  } catch {
    throw new Error('Verbindung zum Hub fehlgeschlagen. Bitte erneut versuchen; dieselbe Aktion wird nicht doppelt gebucht.')
  }
  if (response.status === 401 && token && token === sessionToken()) setSessionToken(null)
  if (isAction && response.status < 500) pending.delete(action)
  if (isAction && response.ok) reads.clear()
  if (isAction && response.ok) window.dispatchEvent(new Event('hub-data-changed'))
  return response
}

// Share concurrent reads (including StrictMode) and short-lived page data.
// Keys include the session; every mutation and login/logout invalidates cached reads.
export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const cacheable = (!options.method || options.method === 'GET') && !options.signal && !/\/auth\/|\/users\/me$/.test(url)
  if (!cacheable) return networkFetch(url, options)
  const key = `${sessionToken() || 'public'}:${url}`
  const previous = reads.get(key)
  if (previous && previous.until > Date.now()) return (await previous.request).clone()
  if (reads.size >= 128) reads.delete(reads.keys().next().value!)
  const request = networkFetch(url, options)
  const entry = { until: Date.now() + 15000, request }
  reads.set(key, entry)
  try {
    const response = await request
    if (!response.ok && reads.get(key) === entry) reads.delete(key)
    return response.clone()
  } catch (cause) {
    if (reads.get(key) === entry) reads.delete(key)
    throw cause
  }
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(`${API_BASE_URL}${path}`, options)
  if (!response.ok) {
    const error = await response.json().catch(() => ({})) as { detail?: unknown }
    throw new Error(typeof error.detail === 'string' ? error.detail : `Anfrage fehlgeschlagen (${response.status})`)
  }
  return response.status === 204 ? undefined as T : response.json()
}

export const jsonPost = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
