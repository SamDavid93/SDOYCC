import { TradeHub } from './pages/TradeHub'
import { SeasonHub } from './pages/SeasonHub'
import { AdvancedAdmin } from './pages/AdvancedAdmin'
import { Notifications } from './components/Notifications'
import logoUrl from './assets/sdoycc-logo.png'
import bannerUrl from './assets/sdoycc-banner.png'
import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { BookOpen, Layers3, ArrowRight, Boxes, ChevronRight, Gem, LayoutDashboard, LogOut, Menu, PackageOpen, Sparkles, Swords, Tags, Users, X } from 'lucide-react'
import { BoosterTile } from './components/BoosterDisplay'
import { CardVisual } from './components/CardVisual'
import { LoginPage, useSession } from './Session'
import { getBoosters, type BoosterSummary, getBoosterHistory, getSummary, getWalletHistory, type Summary, type WalletEntry } from './api/client'
import { CollectionPage } from './pages/CollectionPage'
import { AdminPage, canReadAdmin } from './pages/AdminPage'
import { MyPacksPage } from './pages/MyPacksPage'
import { RegistrationPage } from './pages/RegistrationPage'
import { BattlePassPage, BoosterDetailPage, BoosterHistoryPage, BoostersPage, CardDetailPage, CatalogPage, InventoryPage, SetDetailPage, SetsPage, TradePage } from './pages/WorkspacePages'

const navItems = [
  { label: 'Übersicht', path: '/', icon: LayoutDashboard },
  { label: 'Booster', path: '/boosters', icon: PackageOpen },
  { label: 'Meine Packs', path: '/my-packs', icon: Layers3 },
  { label: 'Meine Sammlung', path: '/inventory', icon: Boxes },
  { label: 'Kartenkatalog', path: '/cards', icon: BookOpen },
  { label: 'Handel', path: '/trade', icon: Tags },
  { label: 'Saisonpass', path: '/battle-pass', icon: Swords },
]

export default function App() {
  const { user, error, logout, revision } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)
  const [packCount, setPackCount] = useState<number | null>(null)
  useEffect(() => {
    let active = true
    if (user) getSummary().then(summary => { if (active) setPackCount(summary.owned_packs) }).catch(() => { if (active) setPackCount(null) })
    else setPackCount(null)
    return () => { active = false }
  }, [user, revision])
  const location = useLocation()
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }) }, [location.pathname])
  if (location.pathname.startsWith('/register/')) return <RegistrationPage />
  if (!user) return <LoginPage />
  const pageTitle = location.pathname.startsWith('/admin') ? 'Verwaltung' : location.pathname.startsWith('/trade/') ? 'Handel' : navItems.find(item => item.path === location.pathname)?.label || (location.pathname.startsWith('/boosters/') ? 'Booster' : /^\/(cards|sets)(\/|$)/.test(location.pathname) ? 'Kartenkatalog' : 'Kartenzentrale')
  const path = location.pathname
  let page = <OverviewPage />
  if (path === '/cards') page = <CatalogPage />
  else if (path === '/sets') page = <SetsPage />
  else if (/^\/cards\/\d+$/.test(path)) page = <CardDetailPage cardId={Number(path.split('/')[2])} />
  else if (/^\/sets\/\d+$/.test(path)) page = <SetDetailPage setId={Number(path.split('/')[2])} />
  else if (path === '/inventory') page = <CollectionPage />
  else if (path === '/boosters') page = <BoostersPage />
  else if (path === '/my-packs') page = <MyPacksPage />
  else if (path === '/boosters/history') page = <BoosterHistoryPage />
  else if (/^\/boosters\/\d+$/.test(path)) page = <BoosterDetailPage boosterId={Number(path.split('/')[2])} />
  else if (path === '/trade') page = <TradeHub />
  else if (/^\/trade\/\d+$/.test(path)) page = <TradeHub key={path} listingId={Number(path.split('/')[2])} />
  else if (path === '/battle-pass') page = <SeasonHub />
  else if (path === '/admin/advanced') page = <AdvancedAdmin />
  else if (path === '/account') page = <AccountPage />
  else if (path === '/admin') page = <AdminPage />
  else if (/^\/admin\/users\/\d+$/.test(path)) page = <AdminPage userId={Number(path.split('/')[3])} />
  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? 'is-open' : ''}`}>
      <div className="brand-row brand-art-row"><NavLink to="/" className="brand-home" aria-label="SDOYCC – Zur Startseite" onClick={() => setMenuOpen(false)}><img className="brand-logo" src={logoUrl} width="1254" height="1254" alt="SDOYCC – SamDavidOfficial’s Yu-Gi-Oh Card Collector" /></NavLink><button className="icon-button mobile-close" onClick={() => setMenuOpen(false)} aria-label="Menü schließen"><X size={18} /></button></div>
      <div className="profile-chip"><div className="avatar">{user.display_name.slice(0, 2).toUpperCase()}</div><div className="profile-copy"><strong>{user.display_name}</strong><span>{user.twitch_id ? '@' + user.username : 'Lokales Demo-Konto'}</span></div></div>
      <nav className="main-nav" aria-label="Hauptnavigation"><p className="eyebrow">DEIN HUB</p>{navItems.map(({ label, path: target, icon: Icon }) => <NavLink key={target} to={target} end={target === '/'} onClick={() => setMenuOpen(false)} className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}><Icon size={18} /><span>{label}</span>{target === '/my-packs' && packCount !== null && <b className="nav-pack-count">{packCount}</b>}</NavLink>)}</nav>
      <div className="sidebar-bottom">{canReadAdmin(user.role) && <NavLink className="nav-item" to="/admin" onClick={() => setMenuOpen(false)}><Users size={18} />Admin-Menü</NavLink>}<NavLink className="nav-item" to="/account"><Users size={18} />Konto & Sammelpunkte</NavLink><button className="nav-item logout-button" onClick={() => void logout()}><LogOut size={18} />Abmelden</button></div>
    </aside>
    {menuOpen && <button className="mobile-scrim" onClick={() => setMenuOpen(false)} aria-label="Menü schließen" />}
    <main className="main-content"><header className="topbar"><button className="icon-button mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Menü öffnen"><Menu size={20} /></button><div className="breadcrumbs"><span>Hub</span><ChevronRight size={14} /><strong>{pageTitle}</strong></div><div className="top-actions"><Notifications key={user.id} /><NavLink className="top-pack-link" to="/my-packs"><Layers3 size={16} /><span>{packCount ?? '…'} Packs</span></NavLink><NavLink to="/account" className="currency"><Gem size={15} />{user.diamonds.toLocaleString('de-DE')} Sammelpunkte</NavLink></div></header>
    {error && <div className="api-notice" role="alert">{error}</div>}
    <div key={user.id}>{page}</div></main>
  </div>
}

function OverviewPage() {
  const { user, config, revision } = useSession()
  const [boosters, setBoosters] = useState<BoosterSummary[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [history, setHistory] = useState<Awaited<ReturnType<typeof getBoosterHistory>>>([])
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    Promise.all([getSummary(), getBoosterHistory(), getBoosters()]).then(([next, openings, packs]) => { if (active) { setSummary(next); setHistory(openings); setBoosters([...packs.filter(pack => pack.image_url), ...packs.filter(pack => !pack.image_url)].slice(0, 3)); setError('') } }).catch(cause => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [user, revision])
  return <div className="page-wrap">
    <section className="welcome-row"><div><p className="eyebrow accent">DEINE KARTENSAMMLUNG</p><h1>Willkommen, {user?.display_name}.</h1><p className="lede">Sammle Punkte im Stream und entdecke deine nächsten Karten.</p></div><NavLink className="outline-button" to="/cards">Katalog entdecken</NavLink></section>
    <section className="hub-hero brand-hero"><img className="hub-brand-banner" src={bannerUrl} width="1672" height="941" fetchPriority="high" alt="SDOYCC – SamDavidOfficial’s Yu-Gi-Oh Card Collector in einer goldenen Kartenhalle" /><div className="hub-hero-copy"><p className="eyebrow"><span className="live-dot" /> {config?.channel || 'SamDavidOfficial'} · SAMMELKARTEN-GEMEINSCHAFT</p><h2>Dein nächster<br /><em>legendärer Moment.</em></h2><p>Vom Stream in deine Sammlung. Tausche {config?.reward_cost.toLocaleString('de-DE') || '1.000'} Kanalpunkte gegen {config?.reward_points || 100} Sammelpunkte und entdecke, was in deinem nächsten Pack steckt.</p><div className="hub-hero-actions"><NavLink className="primary-button" to="/my-packs"><Sparkles size={17} />Meine Packs öffnen <ArrowRight size={17} /></NavLink><NavLink className="hero-secondary" to="/boosters">Booster entdecken →</NavLink></div></div></section>
    <NavLink className="pack-vault-banner" to="/my-packs"><div className="vault-banner-icon"><Layers3 size={30} /></div><div><span className="eyebrow">DEIN PACK-TRESOR</span><strong>{summary?.owned_packs ?? '…'} ungeöffnete Packs</strong><p>Deine gekauften Booster warten hier auf ihren großen Auftritt.</p></div><span className="vault-banner-cta">Zu meinen Packs <ArrowRight size={17} /></span></NavLink>
    <div className="hub-journey"><NavLink to="/boosters"><span>01</span><div><strong>Booster wählen</strong><small>Booster 100 · Structure Decks 600</small></div><PackageOpen size={20} /></NavLink><NavLink to="/my-packs"><span>02</span><div><strong>Packs öffnen</strong><small>Dein Bestand · kostenlos öffnen</small></div><Sparkles size={20} /></NavLink><NavLink to="/inventory"><span>03</span><div><strong>Karten sammeln</strong><small>Alle Funde · deine Sammlung</small></div><Boxes size={20} /></NavLink></div>
    {error && <div className="api-notice" role="alert">{error}</div>}
    <section className="stats-grid">{[['Karten insgesamt', summary?.total_cards], ['Verschiedene Karten', summary?.unique_cards], ['Geöffnete Booster', summary?.packs_opened], ['Ungeöffnete Booster', summary?.owned_packs]].map(([label, value]) => <div className="stat-card" key={label}><span className="stat-label">{label}</span><strong className="stat-value">{value === undefined ? '…' : Number(value).toLocaleString('de-DE')}</strong></div>)}</section>
    <section className="discovery-section"><div className="section-heading"><div><p className="eyebrow accent">DEIN NÄCHSTER BOOSTER</p><h2>Dein Pack. Deine nächsten Karten.</h2><p>Sieh dir die enthaltenen Karten an und finde das passende Pack für deine Sammlung.</p></div><NavLink className="outline-button" to="/boosters">Alle Booster</NavLink></div><div className="booster-grid">{boosters.map(booster => <BoosterTile booster={booster} key={booster.id} />)}</div><NavLink className="back-link" to="/cards">Du suchst eine bestimmte Karte? Zum Kartenkatalog →</NavLink></section>
    <section className="content-panel"><div className="panel-heading"><div><p className="eyebrow">LETZTE ÖFFNUNG</p><h3>Deine zuletzt gezogenen Karten</h3></div><NavLink to="/boosters/history">{history[0]?.cards.length > 6 ? `Alle ${history[0].cards.length} Karten ansehen` : 'Zur Historie'}</NavLink></div>{history[0] ? <div className="result-cards">{history[0].cards.slice(0, 6).map((entry, index) => <CardVisual card={entry.card} key={index} compact />)}</div> : <p>{summary ? 'Noch keine Booster geöffnet. Deine erste Ziehung wartet auf dich.' : 'Sammlung wird geladen …'}</p>}</section>
  </div>
}

function AccountPage() {
  const { user, config, refresh, revision } = useSession()
  const [entries, setEntries] = useState<WalletEntry[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    getWalletHistory().then(items => { if (active) setEntries(items) }).catch(cause => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [user, revision])
  return <div className="page-wrap"><section className="page-heading"><p className="eyebrow accent">DEIN KONTO</p><h1>{user?.display_name}</h1><p>{user?.diamonds.toLocaleString('de-DE')} Sammelpunkte</p></section>
    {error && <div className="api-notice" role="alert">{error}</div>}
    <div className="content-panel"><h3>Sammelpunkte sammeln</h3><p>Löse bei {config?.channel} {config?.reward_cost.toLocaleString('de-DE')} Kanalpunkte gegen {config?.reward_points} Sammelpunkte ein. Nach erfolgreicher Einlösung erscheint die Gutschrift hier. Der Kontostand aktualisiert sich automatisch alle 30 Sekunden.</p><a className="outline-button" href={`https://www.twitch.tv/${config?.channel || 'SamDavidOfficial'}`} target="_blank" rel="noreferrer">Zum Twitch-Kanal</a><button className="outline-button" onClick={() => void refresh()}>Kontostand aktualisieren</button></div>
    <div className="history-list account-section"><h3>Deine letzten Buchungen</h3>{entries.length ? entries.map(entry => <div className="wallet-row" key={entry.id}><div><strong>{entry.reason === 'admin_correction' ? 'Admin-Korrektur' : entry.reason === 'season_reward' ? 'Saisonbelohnung' : entry.reason === 'admin_grant' ? 'Admin-Gutschrift' : entry.reason === 'twitch_redemption' ? 'Twitch-Kanalpunkte' : entry.reason === 'opening_balance' ? 'Übernommenes Guthaben' : 'Booster-Kauf'}</strong><small>{new Date(entry.created_at).toLocaleString('de-DE')}</small></div><strong>{entry.amount > 0 ? '+' : ''}{entry.amount} Sammelpunkte</strong><span>Stand: {entry.balance_after}</span></div>) : <p>Noch keine Buchungen vorhanden.</p>}</div>
  </div>
}
