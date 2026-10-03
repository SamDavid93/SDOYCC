import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Search, SlidersHorizontal, X, ChevronLeft, ChevronRight, Layers3 } from 'lucide-react'
import { CardSkeletons, CardVisual } from '../components/CardVisual'
import { getCollection, getCollectionFilters } from '../api/client'
import { label } from '../i18n'
import { InventoryJournal, VariantDetails } from '../components/InventoryDetails'

const groups: Record<string, string> = { rarity: 'Seltenheit', type: 'Kartenart', attribute: 'Attribut', race: 'Typ / Unterart', level: 'Stufe / Rang', atk: 'Angriff', defense: 'Verteidigung', scale: 'Pendelskala', link_value: 'Linkwert', link_markers: 'Linkpfeile', archetype: 'Kartengruppe', set_id: 'Kartenset', ban_status: 'Turnierstatus' }

export function CollectionPage() {
  const [journal, setJournal] = useState(false)
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [facets, setFacets] = useState<Awaited<ReturnType<typeof getCollectionFilters>>>({})
  const [group, setGroup] = useState('')
  const [optionSearch, setOptionSearch] = useState('')
  const [sort, setSort] = useState('name')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<Awaited<ReturnType<typeof getCollection>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => { const timer = setTimeout(() => { setSearch(query); setPage(1) }, 250); return () => clearTimeout(timer) }, [query])
  useEffect(() => { let active = true; getCollectionFilters().then(value => { if (active) setFacets(value) }).catch(cause => { if (active) setError(cause.message) }); return () => { active = false } }, [])
  useEffect(() => {
    let active = true; setLoading(true)
    getCollection({ ...filters, search, sort, page: String(page) }).then(value => { if (active) { setData(value); setError('') } }).catch(cause => { if (active) setError(cause.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [search, filters, page, sort])
  const choose = (key: string, value: string) => { setFilters(current => { const next = { ...current }; if (next[key] === value) delete next[key]; else next[key] = value; return next }); setPage(1) }
  const clear = () => { setFilters({}); setQuery(''); setSearch(''); setPage(1) }
  const filterKey = (key: string) => key === 'type' ? 'card_type' : key === 'link_markers' ? 'link_marker' : key
  return <div className="page-wrap workspace-page collection-page"><section className="page-heading"><div><p className="eyebrow accent">DEIN PERSÖNLICHES KARTENARCHIV</p><h1>Deine Karten</h1><p className="lede">Finde deine Lieblingskarten. Ordne deine Sammlung nach Typ, Werten und Seltenheit.</p></div><NavLink to="/my-packs" className="outline-button"><Layers3 size={16} />Weitere Booster öffnen</NavLink></section>
    <div className="inventory-summary collection-summary"><div><strong>{data?.total_quantity ?? '…'}</strong><span>Karten insgesamt</span></div><div><strong>{data?.unique_cards ?? '…'}</strong><span>verschiedene Karten</span></div><div><strong>{data ? data.total_quantity - data.unique_cards : '…'}</strong><span>doppelte Exemplare</span></div></div>
    <section className="collection-tools" aria-label="Sammlung filtern"><div className="collection-search-row"><label className="search-field"><Search size={17} /><input aria-label="Sammlung durchsuchen" value={query} placeholder="Name, Kartennummer oder Kartentext suchen …" onChange={event => setQuery(event.target.value)} /></label><label className="collection-sort">Sortierung<select value={sort} onChange={event => { setSort(event.target.value); setPage(1) }}><option value="name">Name A–Z</option><option value="recent">Zuletzt erhalten</option><option value="quantity">Häufigste zuerst</option><option value="atk">Höchster Angriff</option><option value="level">Höchste Stufe / Rang</option></select></label></div>
      <div className="filter-group-buttons"><span><SlidersHorizontal size={15} />Filter</span>{Object.entries(groups).map(([key, name]) => <button key={key} className={filters[filterKey(key)] || group === key ? 'selected' : ''} aria-expanded={group === key} onClick={() => { setGroup(group === key ? '' : key); setOptionSearch('') }}>{name}{filters[filterKey(key)] && <i />}</button>)}<button aria-pressed={filters.duplicates === 'true'} className={filters.duplicates ? 'selected' : ''} onClick={() => choose('duplicates', 'true')}>Nur doppelte</button></div>
      {group && <div className="filter-options"><div><strong>{groups[group]} wählen</strong><button className="icon-button" aria-label="Filterauswahl schließen" onClick={() => setGroup('')}><X size={16} /></button></div>{(facets[group]?.length || 0) > 14 && <input className="option-search" aria-label="Filterwerte durchsuchen" placeholder="Filterwert suchen …" value={optionSearch} onChange={event => setOptionSearch(event.target.value)} />}<div className="filter-chips">{facets[group]?.filter(item => label(typeof item === 'object' ? item.label : item).toLowerCase().includes(optionSearch.toLowerCase())).map(item => { const value = String(typeof item === 'object' ? item.value : item); const title = label(typeof item === 'object' ? item.label : item); return <button key={value} aria-pressed={filters[filterKey(group)] === value} className={filters[filterKey(group)] === value ? 'selected' : ''} onClick={() => choose(filterKey(group), value)}>{title}</button> })}{!facets[group]?.length && <p>Für diese Eigenschaft sind in deiner Sammlung noch keine Werte hinterlegt.</p>}</div></div>}
      {Object.keys(filters).length > 0 && <div className="active-filters">{Object.entries(filters).map(([key, value]) => <button key={key} onClick={() => choose(key, value)}>{key === 'duplicates' ? 'Nur doppelte' : `${groups[key === 'card_type' ? 'type' : key === 'link_marker' ? 'link_markers' : key]}: ${key === 'set_id' ? 'Set ' + value : label(value)}`}<X size={12} /></button>)}<button onClick={clear}>Alle Filter zurücksetzen</button></div>}
    </section>
    {error && <div className="api-notice" role="alert">{error}</div>}<div className="catalog-result-meta"><span>{data?.total ?? '…'} passende Karten</span><span>Seite {page} von {Math.max(1, Math.ceil((data?.total || 0) / 36))}</span></div>
    <p className="variant-explanation">Öffne „Bestandsvarianten“ unter einer Karte für Stückzahlen und Herkunft. Das farbige Abzeichen zeigt die höchste belegte Seltenheit; ungeklärter Altbestand erhält keine erfundene Seltenheit.</p>
    {loading ? <CardSkeletons count={12} /> : <div className="catalog-grid collection-grid">{data?.items.map(card => <div className="collection-card-entry" key={card.id}><NavLink className="card-link" to={`/cards/${card.id}`}><CardVisual card={card} showQuantity /></NavLink><VariantDetails variants={card.owned_variants || []} /></div>)}</div>}
    {!loading && !error && !data?.items.length && <div className="empty-state"><h2>{data?.total_quantity ? 'Keine Karte passt zu diesen Filtern.' : 'Deine Sammlung wartet auf die erste Karte.'}</h2>{data?.total_quantity ? <button className="outline-button" onClick={clear}>Filter zurücksetzen</button> : <NavLink className="primary-button" to="/my-packs">Booster öffnen</NavLink>}</div>}
    <div className="pagination"><button className="icon-button" disabled={loading || page <= 1} onClick={() => setPage(page - 1)} aria-label="Vorherige Seite"><ChevronLeft size={18} /></button><span>{page} / {Math.max(1, Math.ceil((data?.total || 0) / 36))}</span><button className="icon-button" disabled={loading || page * 36 >= (data?.total || 0)} onClick={() => setPage(page + 1)} aria-label="Nächste Seite"><ChevronRight size={18} /></button></div>
    <button className="outline-button" aria-expanded={journal} onClick={() => setJournal(value => !value)}>{journal ? 'Kartenbewegungen ausblenden' : 'Kartenbewegungen anzeigen'}</button>{journal && <InventoryJournal />}
  </div>
}
