import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { ArrowRight, Layers3, PackageOpen, Search, Sparkles } from 'lucide-react'
import { getBoosters, type BoosterSummary } from '../api/client'
import { BoosterCover, BoosterProgress, DiscoveryNav } from '../components/BoosterDisplay'
import { usePackOpening } from '../components/PackOpening'
import { useSession } from '../Session'

export function MyPacksPage() {
  const { user, revision } = useSession()
  const { openPack } = usePackOpening()
  const [packs, setPacks] = useState<BoosterSummary[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    getBoosters().then(items => { if (active) { setPacks(items.filter(pack => pack.owned > 0)); setError('') } }).catch(cause => { if (active) setError(cause.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [user?.id, revision])
  const total = packs.reduce((sum, pack) => sum + pack.owned, 0)
  const cards = packs.reduce((sum, pack) => sum + pack.owned * pack.cards_per_pack, 0)
  const visible = packs.filter(pack => `${pack.name} ${pack.set_code || ''}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => b.owned - a.owned)
  const open = async (pack: BoosterSummary) => {
    setBusy(true)
    try {
      const result = await openPack(pack)
      if (result) setPacks(current => current.map(item => item.id === pack.id ? { ...item, owned: result.remaining } : item).filter(item => item.owned > 0))
    } finally { setBusy(false) }
  }
  return <div className="page-wrap workspace-page vault-page"><section className="page-heading"><div><p className="eyebrow accent">DEIN PERSÖNLICHER PACK-TRESOR</p><h1>Meine Packs</h1><p className="lede">Schon gekauft. Noch voller Möglichkeiten. Hier warten deine ungeöffneten Booster.</p></div><NavLink className="outline-button" to="/boosters">Zum Booster-Shop <ArrowRight size={16} /></NavLink></section><DiscoveryNav />
    <section className="vault-hero"><div className="vault-emblem" aria-hidden="true"><Layers3 size={54} /></div><div><p className="eyebrow">BEREIT FÜR DEINE NÄCHSTE ÖFFNUNG</p><h2>{loading ? 'Deine Packs werden geladen.' : total ? `${total} ${total === 1 ? 'Pack wartet' : 'Packs warten'} auf dich.` : 'Dein nächstes Pack wartet im Shop.'}</h2><p>Öffnen ist kostenlos. Jede gezogene Karte landet direkt in deiner Sammlung.</p></div><div className="vault-metrics"><div><strong>{loading ? '—' : total}</strong><span>ungeöffnet</span></div><div><strong>{loading ? '—' : packs.length}</strong><span>verschiedene Booster</span></div><div><strong>{loading ? '—' : cards}</strong><span>Karten warten auf dich</span></div></div></section>
    {error && <div className="api-notice" role="alert">{error}</div>}
    <div className="section-heading"><div><p className="eyebrow accent">DEINE BOOSTER-STAPEL</p><h2>Womit fängst du an?</h2></div><NavLink className="back-link" to="/boosters/history">Bisherige Öffnungen <ArrowRight size={15} /></NavLink></div>
    <label className="search-field vault-search"><Search size={17} /><input aria-label="Meine Packs durchsuchen" placeholder="In deinen gekauften Packs suchen …" value={query} onChange={event => setQuery(event.target.value)} /></label>
    <div className="vault-grid">{visible.map(pack => <article className="vault-stack" key={pack.id}><div className="vault-stack-art"><div className="stack-shadow stack-shadow-one" /><div className="stack-shadow stack-shadow-two" /><BoosterCover name={pack.name} imageUrl={pack.image_url} /><span className="vault-quantity">×{pack.owned}<small>{pack.owned === 1 ? 'PACK' : 'PACKS'}</small></span><span className="vault-ready"><span />BEREIT ZUM ÖFFNEN</span></div><div className="vault-stack-copy"><p className="eyebrow">{pack.set_code || 'SAMMELEDITION'} · {pack.cards_per_pack} KARTEN PRO PACK</p><h3>{pack.name}</h3><p>{pack.owned * pack.cards_per_pack} Karten warten in diesem Stapel.</p><BoosterProgress booster={pack} /><button className="primary-button" disabled={busy || !pack.cards_per_pack} onClick={() => void open(pack)}><Sparkles size={17} />Pack öffnen <ArrowRight size={17} /></button><NavLink to={`/boosters/${pack.id}`}>Kartenpool ansehen</NavLink></div></article>)}</div>
    {!loading && !error && !visible.length && <div className="vault-empty"><PackageOpen size={44} /><h2>{query ? 'Kein passender Stapel gefunden.' : 'Hier beginnt deine nächste Öffnung.'}</h2><p>{query ? 'Versuche einen anderen Namen oder ein Set-Kürzel.' : 'Kaufe im Shop einen Booster für 100 Sammelpunkte. Dein Pack erscheint anschließend hier.'}</p>{!query && <NavLink className="primary-button" to="/boosters">Booster entdecken <ArrowRight size={16} /></NavLink>}</div>}
  </div>
}
