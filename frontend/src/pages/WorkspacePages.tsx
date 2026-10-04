import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { ProductLimit, buyLabel, BoosterCover, BoosterTile, BoosterProgress, DiscoveryNav } from '../components/BoosterDisplay'
import { PurchaseFeedback, usePurchaseFeedback } from '../components/PurchaseFeedback'
import { usePackOpening } from '../components/PackOpening'
import { label } from '../i18n'
import { CardVisual, CardSkeletons } from '../components/CardVisual'
import type { CardRecord } from '../data/cards'
import { getBooster, getBoosterHistory, getBoosters, getBoostersForSet, getBoostersForCard, getCardDetail, getCardPage, getCardPrintings, getCardSets, getInventory, getSetCards, openBooster, type BoosterSummary, type CardSetSummary, type Inventory } from '../api/client'
import { useSession } from '../Session'

function useAction() {
  const running = useRef(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async (action: () => Promise<void>) => {
    if (running.current) return
    running.current = true; setBusy(true); setError('')
    try { await action() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Aktion fehlgeschlagen') }
    finally { running.current = false; setBusy(false) }
  }
  return { busy, error, setError, run }
}
function Notice({ message }: { message: string }) { return message ? <div className="api-notice" role="alert">{message}</div> : null }
function Empty({ children }: { children: React.ReactNode }) { return <div className="empty-state">{children}</div> }
function Pagination({ page, pages, change }: { page: number; pages: number; change: (page: number) => void }) {
  return <div className="pagination"><button className="icon-button" disabled={page <= 1} onClick={() => change(page - 1)} aria-label="Vorherige Seite"><ChevronLeft size={17} /></button><span>{page} / {pages}</span><button className="icon-button" disabled={page >= pages} onClick={() => change(page + 1)} aria-label="Nächste Seite"><ChevronRight size={17} /></button></div>
}

export function CatalogPage() {
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  useEffect(() => { const timer = setTimeout(() => setSearch(query), 250); return () => clearTimeout(timer) }, [query])
  const [remoteCards, setRemoteCards] = useState<CardRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [rarity, setRarity] = useState('')
  const [attribute, setAttribute] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true; setLoading(true)
    getCardPage({ search, rarity, attribute, page }).then(result => { if (active) { setRemoteCards(result.items); setTotal(result.total); setError('') } }).catch(cause => { if (active) { setError(cause.message); setRemoteCards([]) } }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [search, rarity, attribute, page])
  return <PageFrame eyebrow="KARTENKATALOG" title="Entdecke deine nächste Karte" description="Suche eine Wunschkarte. In ihren Details siehst du, in welchen Boostern du sie ziehen kannst."><DiscoveryNav /><div className="catalog-toolbar"><label className="search-field"><Search size={16} /><input aria-label="Karten suchen" value={query} onChange={event => { setQuery(event.target.value); setPage(1) }} placeholder="Kartenname oder Kartennummer suchen" /></label><select className="catalog-select" aria-label="Seltenheit" value={rarity} onChange={event => { setRarity(event.target.value); setPage(1) }}><option value="">Alle Seltenheiten</option>{['common', 'rare', 'super_rare', 'ultra_rare', 'secret_rare'].map(value => <option key={value} value={value}>{label(value)}</option>)}</select><select className="catalog-select" aria-label="Attribut" value={attribute} onChange={event => { setAttribute(event.target.value); setPage(1) }}><option value="">Alle Attribute</option>{['DARK', 'LIGHT', 'EARTH', 'WATER', 'FIRE', 'WIND', 'DIVINE'].map(value => <option key={value} value={value}>{label(value)}</option>)}</select></div><Notice message={error} /><div className="catalog-result-meta"><span>{total.toLocaleString('de-DE')} Karten</span>{loading && <span role="status">Wird geladen …</span>}</div>{loading ? <CardSkeletons /> : <div className="catalog-grid">{remoteCards.map(card => <NavLink className="card-link" to={`/cards/${card.id}`} key={card.id}><CardVisual card={card} /></NavLink>)}</div>}{!loading && !error && !remoteCards.length && <Empty>Keine passenden Karten gefunden.</Empty>}<Pagination page={page} pages={Math.max(1, Math.ceil(total / 24))} change={setPage} /></PageFrame>
}

export function SetsPage() {
  const [query, setQuery] = useState('')
  const [sets, setSets] = useState<CardSetSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let active = true; setLoading(true)
    getCardSets(query, page).then(result => { if (active) { setSets(result.items); setTotal(result.total); setError('') } }).catch(cause => { if (active) setError(cause.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [query, page])
  return <PageFrame eyebrow="KARTENSETS" title="Alle Sets entdecken" description="Finde die Karten und Booster deiner Lieblingssets."><DiscoveryNav /><label className="search-field set-search"><Search size={16} /><input aria-label="Sets suchen" value={query} onChange={event => { setQuery(event.target.value); setPage(1) }} placeholder="Sets suchen" /></label><Notice message={error} /><div className="catalog-result-meta"><span>{total.toLocaleString('de-DE')} Sets</span>{loading && <span role="status">Wird geladen …</span>}</div><div className="set-grid">{sets.map(set => <NavLink className="set-card" to={`/sets/${set.id}`} key={set.id}><BoosterCover name={set.name} imageUrl={set.cover_image_url} /><div><strong>{set.name}</strong><span>{set.code || 'Ohne Code'} · {set.card_count || 0} Karten</span><small>{set.release_date || 'Datum unbekannt'}</small></div></NavLink>)}</div><Pagination page={page} pages={Math.max(1, Math.ceil(total / 30))} change={setPage} /></PageFrame>
}

export function CardDetailPage({ cardId }: { cardId: number }) {
  const [card, setCard] = useState<CardRecord | null>(null)
  const [packs, setPacks] = useState<BoosterSummary[]>([])
  const [printings, setPrintings] = useState<Awaited<ReturnType<typeof getCardPrintings>>>([])
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true; setCard(null); setPacks([]); setError('')
    Promise.all([getCardDetail(cardId), getCardPrintings(cardId), getBoostersForCard(cardId)]).then(([item, versions, matchingPacks]) => { if (active) { setCard(item); setPrintings(versions); setPacks(matchingPacks) } }).catch(cause => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [cardId])
  return <PageFrame eyebrow="KARTENDETAILS" title={card?.name || 'Karte wird geladen …'} description="Kartendetails und bekannte Ausgaben."><NavLink className="back-link" to="/cards"><ArrowLeft size={15} />Zum Katalog</NavLink><Notice message={error} />{card && <div className="card-detail-layout"><div className="detail-card-image"><CardVisual card={card} /></div><div className="card-detail-copy"><span className="status-label">{label(card.rarity)}</span><h2>{card.name}</h2><p>{label(card.type)} · {label(card.attribute)}</p><dl className="card-specifications">{[['Typ', label(card.race)], ['Stufe / Rang', card.level], ['Angriff', card.atk], ['Verteidigung', card.defense], ['Pendelskala', card.scale], ['Linkwert', card.link_value]].filter(([, value]) => value !== null && value !== undefined).map(([title, value]) => <div key={title}><dt>{title}</dt><dd>{value}</dd></div>)}</dl>{card.description && card.description_language === 'en' && <small className="text-language-label">Englischer Originaltext · Deutsche Übersetzung nicht verfügbar</small>}<p className="card-description">{card.description || 'Für diese Karte liegt noch kein Kartentext vor.'}</p><details className="printing-panel"><summary>{printings.length} bekannte Ausgaben und ihre Sets</summary>{printings.map(printing => <div className="printing-row" key={printing.id}><strong>{printing.set_id ? <NavLink to={`/sets/${printing.set_id}`}>{printing.set_code || 'Zum Set'}</NavLink> : printing.set_code || 'Ohne Code'}</strong><span>{label(printing.rarity || printing.provider_rarity_name)}</span></div>)}</details></div></div>}<section className="discovery-section"><div className="section-heading"><div><p className="eyebrow accent">DEINE WUNSCHKARTE FINDEN</p><h2>In diesen Boostern enthalten</h2><p>Diese Packs enthalten die Karte im tatsächlichen Ziehungspool. Ein Kauf garantiert keine bestimmte Karte.</p></div></div><div className="booster-grid">{packs.map(pack => <BoosterTile booster={pack} key={pack.id} />)}</div>{card && !error && !packs.length && <Empty>Diese Karte ist aktuell in keinem verfügbaren Booster enthalten. Die bekannten Set-Ausgaben findest du oben.</Empty>}</section></PageFrame>
}

export function SetDetailPage({ setId }: { setId: number }) {
  const { user } = useSession()
  const [setCards, setSetCards] = useState<CardRecord[]>([])
  const [boosters, setBoosters] = useState<BoosterSummary[]>([])
  const [loading, setLoading] = useState(true)
  const purchase = usePurchaseFeedback()
  const { busy, error, setError, run } = useAction()
  useEffect(() => {
    let active = true; setLoading(true)
    Promise.all([getSetCards(setId), getBoostersForSet(setId)]).then(([items, packs]) => { if (active) { setSetCards(items); setBoosters(packs); setError('') } }).catch(cause => { if (active) setError(cause.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [setId])
  const buy = (booster: BoosterSummary) => run(async () => {
    const result = await purchase.buyPack(booster)
    setBoosters(current => current.map(pack => pack.id === booster.id ? { ...pack, owned: result.owned, purchased_total: result.purchased_total, purchases_remaining: result.purchases_remaining } : pack))

  })
  return <PageFrame eyebrow="SETDETAILS" title={boosters[0]?.set_name || 'Karten dieses Sets'} description="Entdecke den Kartenpool und die verfügbaren Booster."><NavLink className="back-link" to="/sets"><ArrowLeft size={15} />Alle Sets</NavLink><Notice message={error} /><PurchaseFeedback {...purchase} busy={busy} />{loading && <p role="status">Set wird geladen …</p>}{boosters.map(booster => <div className="set-booster-row" key={booster.id}><BoosterCover name={booster.name} imageUrl={booster.image_url} /><div><strong>{booster.name}</strong><span>{booster.cards_per_pack} Karten · {booster.cost} Sammelpunkte · {booster.owned} im Bestand</span><ProductLimit booster={booster} /></div><button className="primary-button" disabled={busy || !booster.cards_per_pack || booster.purchases_remaining === 0 || (user?.diamonds || 0) < booster.cost} onClick={() => void buy(booster)} aria-busy={purchase.purchasingId === booster.id}>{purchase.purchasingId === booster.id ? 'Wird gekauft …' : buyLabel(booster)}</button><NavLink className="outline-button" to={`/boosters/${booster.id}`}>Ansehen & öffnen</NavLink></div>)}{!loading && !error && !boosters.length && <p>Für dieses Set ist noch kein Booster verfügbar.</p>}<div className="catalog-result-meta">{setCards.length} Karten im Set</div><div className="catalog-grid">{setCards.map(card => <NavLink className="card-link" to={`/cards/${card.id}`} key={card.id}><CardVisual card={card} /></NavLink>)}</div></PageFrame>
}

export function InventoryPage() {
  const { user } = useSession()
  const [inventory, setInventory] = useState<Inventory | null>(null)
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    getInventory().then(result => { if (active) { setInventory(result); setError('') } }).catch(cause => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [user])
  const visible = inventory?.items.filter(card => card.name.toLowerCase().includes(query.toLowerCase())) || []
  return <PageFrame eyebrow="MEINE SAMMLUNG" title="Deine Karten" description="Jede gezogene Karte landet hier. Doppelte Exemplare erhöhen die Stückzahl."><Notice message={error} /><div className="inventory-summary"><strong>{inventory?.total_quantity ?? '…'}</strong><span>Karten insgesamt</span><strong>{inventory?.unique_cards ?? '…'}</strong><span>verschiedene Karten</span></div><label className="search-field"><Search size={16} /><input aria-label="Sammlung durchsuchen" placeholder="Deine Sammlung durchsuchen" value={query} onChange={event => setQuery(event.target.value)} /></label><div className="catalog-grid inventory-cards">{visible.map(card => <NavLink className="card-link" to={`/cards/${card.id}`} key={card.id}><CardVisual card={card} showQuantity /></NavLink>)}</div>{inventory && !visible.length && <Empty>{inventory.total_quantity ? 'Keine passenden Karten gefunden.' : 'Deine Sammlung ist noch leer. Öffne deinen ersten Booster.'}</Empty>}</PageFrame>
}

export function BoostersPage() {
  const { openPack } = usePackOpening()
  const { user, revision } = useSession()
  const [boosters, setBoosters] = useState<BoosterSummary[]>([])
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [ownedOnly, setOwnedOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [result, setResult] = useState<Awaited<ReturnType<typeof openBooster>> | null>(null)
  const purchase = usePurchaseFeedback()
  const { busy, error, setError, run } = useAction()
  useEffect(() => {
    let active = true
    getBoosters().then(items => { if (active) { setBoosters(items); setError('') } }).catch(cause => { if (active) setError(cause.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [revision, user?.id])
  const buy = (booster: BoosterSummary) => run(async () => {
    const purchased = await purchase.buyPack(booster)
    setBoosters(current => current.map(pack => pack.id === booster.id ? { ...pack, owned: purchased.owned, purchased_total: purchased.purchased_total, purchases_remaining: purchased.purchases_remaining } : pack))

  })
  const open = (booster: BoosterSummary) => run(async () => {
    purchase.dismiss()
    const opened = await openPack(booster)
    if (!opened) return
    setResult(opened)
    setBoosters(current => current.map(pack => pack.id === booster.id ? { ...pack, owned: opened.remaining } : pack))
    purchase.dismiss()
  })
  const visible = boosters.filter(booster => (!ownedOnly || booster.owned > 0) && `${booster.name} ${booster.set_name || ''} ${booster.set_code || ''}`.toLowerCase().includes(query.trim().toLowerCase()))
  const currentPage = Math.min(page, Math.max(1, Math.ceil(visible.length / 24)))
  return <PageFrame eyebrow="BOOSTER-AUSWAHL" title="Dein nächster Fund beginnt hier." description="Booster kosten 100 Sammelpunkte. Structure Decks kosten 600 Punkte und liefern ihre vollständige Deckliste; maximal drei Käufe pro Deck und Konto. Wähle ein Set, prüfe die enthaltenen Karten und öffne dein Pack.">
    <DiscoveryNav />
    <NavLink className="pack-vault-banner" to="/my-packs"><div className="vault-banner-icon">✦</div><div><span className="eyebrow">DEINE GEKAUFTEN BOOSTER</span><strong>{boosters.reduce((sum, pack) => sum + pack.owned, 0)} Packs in deinem Tresor</strong><p>Alle ungeöffneten Packs an einem Ort. Bereit für deine nächste Ziehung.</p></div><span className="vault-banner-cta">Meine Packs öffnen →</span></NavLink>
    <div className="discovery-guide"><div><strong>Du suchst eine bestimmte Karte?</strong><p>Der Kartenkatalog zeigt dir direkt die passenden Booster.</p></div><NavLink className="outline-button" to="/cards">Wunschkarte suchen</NavLink><NavLink className="back-link" to="/boosters/history">Öffnungshistorie</NavLink></div>
    <Notice message={error} /><PurchaseFeedback {...purchase} busy={busy} onOpen={booster => void open(booster)} />
    {result && <><OpeningResult result={result} /><button className="outline-button" onClick={() => setResult(null)}>Ergebnis schließen</button></>}
    <div className="catalog-toolbar"><label className="search-field booster-search"><Search size={16} /><input aria-label="Booster suchen" value={query} onChange={event => { setQuery(event.target.value); setPage(1) }} placeholder="Booster, Set oder Set-Kürzel suchen …" /></label><label className="owned-filter"><input type="checkbox" checked={ownedOnly} onChange={event => { setOwnedOnly(event.target.checked); setPage(1) }} />Nur meine ungeöffneten Packs</label></div>
    <div className="catalog-result-meta"><span>{loading ? 'Booster werden geladen …' : `${visible.length.toLocaleString('de-DE')} Booster${ownedOnly ? ' in deinem Bestand' : ' gefunden'}`}</span><span>Booster: 100 · Structure Deck: 600 · Öffnen: kostenlos</span></div>
    <div className="booster-grid">{visible.slice((currentPage - 1) * 24, currentPage * 24).map(booster => <BoosterTile booster={booster} key={booster.id}><button className="outline-button" disabled={busy || !booster.cards_per_pack || booster.purchases_remaining === 0 || (user?.diamonds || 0) < booster.cost} onClick={() => void buy(booster)} aria-busy={purchase.purchasingId === booster.id}>{purchase.purchasingId === booster.id ? 'Wird gekauft …' : buyLabel(booster)}</button><button className="primary-button" disabled={busy || !booster.cards_per_pack || booster.owned < 1} onClick={() => void open(booster)}>Öffnen</button></BoosterTile>)}</div>
    {!loading && !error && !visible.length && <Empty>{ownedOnly ? 'Keine passenden ungeöffneten Packs. Deaktiviere den Filter, um neue Booster zu entdecken.' : 'Keine Booster gefunden. Suche nach einem Set-Namen oder suche deine Wunschkarte im Kartenkatalog.'}</Empty>}
    <Pagination page={currentPage} pages={Math.max(1, Math.ceil(visible.length / 24))} change={setPage} />
  </PageFrame>
}

export function BoosterDetailPage({ boosterId }: { boosterId: number }) {
  const { openPack } = usePackOpening()
  const { user, revision } = useSession()
  const [booster, setBooster] = useState<Awaited<ReturnType<typeof getBooster>> | null>(null)
  const [result, setResult] = useState<Awaited<ReturnType<typeof openBooster>> | null>(null)
  const purchase = usePurchaseFeedback()
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const { busy, error, setError, run } = useAction()
  useEffect(() => {
    setBooster(null); setResult(null); setQuery(''); setPage(1); purchase.dismiss()
  }, [boosterId])
  useEffect(() => {
    let active = true
    getBooster(boosterId).then(item => { if (active) { setBooster(item); setError('') } }).catch(cause => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [boosterId, revision, user?.id])
  const buy = () => run(async () => {
    if (!booster) return
    const purchased = await purchase.buyPack(booster)
    setBooster(current => current && { ...current, owned: purchased.owned, purchased_total: purchased.purchased_total, purchases_remaining: purchased.purchases_remaining })

  })
  const open = () => run(async () => {
    if (!booster) return
    purchase.dismiss()
    const opened = await openPack(booster)
    if (!opened) return
    setResult(opened)
    setBooster(current => current && { ...current, owned: opened.remaining })
  })
  const pool = booster?.pool.filter(entry => entry.card.name.toLowerCase().includes(query.trim().toLowerCase())) || []
  const totalWeight = booster?.pool.reduce((sum, entry) => sum + entry.weight, 0) || 0
  return <PageFrame eyebrow="BOOSTERDETAILS" title={booster?.name || 'Booster wird geladen …'} description="Prüfe vor dem Kauf, welche Karten du in diesem Booster ziehen kannst.">
    <NavLink className="back-link" to="/boosters"><ArrowLeft size={15} />Alle Booster</NavLink><Notice message={error} />
    {booster && <section className="booster-detail-hero"><BoosterCover name={booster.name} imageUrl={booster.image_url} /><div className="booster-detail-copy"><p className="eyebrow accent">DEIN PACK AUF EINEN BLICK</p><h2>{booster.cards_per_pack} {booster.product_type === 'structure_deck' ? (booster.bonus_cards ? 'Karten inklusive Bonus' : 'garantierte Karten') : 'zufällige Karten'} für {booster.cost} Punkte</h2><ProductLimit booster={booster} /><BoosterProgress booster={booster} /><p>{booster.product_type === 'structure_deck' ? (booster.bonus_cards ? `Du erhältst ${booster.fixed_cards} feste Karten einschließlich Mehrfachexemplaren und ${booster.bonus_cards} zusätzliche Bonuskarte.` : 'Du erhältst die feste Deckliste einschließlich aller Mehrfachexemplare.') : `Aus einem Pool von ${booster.pool_size} Karten.`} Nach dem Kauf gehört das Pack dir – du kannst es jederzeit kostenlos öffnen.</p><p><strong>{booster.owned} ungeöffnete Packs</strong> in deinem Bestand</p><div className="booster-detail-buttons"><button className="outline-button" disabled={busy || !booster.cards_per_pack || booster.purchases_remaining === 0 || (user?.diamonds || 0) < booster.cost} onClick={() => void buy()} aria-busy={purchase.purchasingId === boosterId}>{purchase.purchasingId === boosterId ? 'Wird gekauft …' : buyLabel(booster)}</button><button className="primary-button" disabled={busy || !booster.cards_per_pack || booster.owned < 1} onClick={() => void open()}>Kostenlos öffnen</button></div>{(user?.diamonds || 0) < booster.cost && <NavLink className="back-link" to="/account">Sammelpunkte im Stream sammeln</NavLink>}{booster.set_id && <NavLink className="back-link" to={`/sets/${booster.set_id}`}>Zugehöriges Kartenset ansehen →</NavLink>}</div></section>}
    <PurchaseFeedback {...purchase} busy={busy} onOpen={() => void open()} />{result && <OpeningResult result={result} />}
    {booster?.bonus_slots.map((slot, index) => <section className="pool-panel deck-bonus-panel" key={index} aria-label="Bonusauswahl"><h2>{slot.name}</h2><p>Du erhältst genau eine der folgenden Karten zusätzlich zum festen Deckinhalt. Die Auswahl erfolgt einmal beim Öffnen.</p>{booster.content_notes && <p className="deck-content-note">{booster.content_notes}</p>}<div className="catalog-grid bonus-card-grid">{slot.choices.filter(choice => choice.card.name.toLowerCase().includes(query.trim().toLowerCase())).map((choice, choiceIndex) => <div key={choiceIndex}><NavLink className="card-link" to={`/cards/${choice.card.id}`}><CardVisual card={choice.card} /></NavLink><small>{(choice.probability * 100).toLocaleString('de-DE', { maximumFractionDigits: 2 })}% Bonuschance im Hub · nicht garantiert</small></div>)}</div></section>)}
    <section className="pool-panel"><h2>{booster?.product_type === 'structure_deck' ? 'Garantierter Deckinhalt' : 'Welche Karten kann ich ziehen?'}</h2><p>{booster?.product_type === 'structure_deck' ? 'Jede aufgeführte Karte ist in der angegebenen Stückzahl enthalten.' : 'Jede Karte wird unabhängig gezogen. Doppelte Exemplare sind möglich; eine bestimmte Karte ist nicht garantiert.'}</p><label className="search-field"><Search size={16} /><input aria-label="Karten in diesem Booster suchen" placeholder="Wunschkarte in diesem Booster suchen …" value={query} onChange={event => { setQuery(event.target.value); setPage(1) }} /></label><div className="catalog-result-meta">{booster?.product_type === 'structure_deck' ? `${pool.length} Karteneinträge im festen Inhalt` : `${pool.length} von ${booster?.pool_size || 0} möglichen Karten`}</div><div className="catalog-grid">{pool.slice((page - 1) * 24, page * 24).map((entry, index) => <div key={`${entry.card.id}-${entry.rarity}-${index}`}><NavLink className="card-link" to={`/cards/${entry.card.id}`}><CardVisual card={entry.card} /></NavLink><small>{entry.quantity != null ? `${entry.quantity} × garantiert enthalten` : `Chance je Ziehung: ${(totalWeight > 0 ? entry.weight / totalWeight * 100 : 0).toLocaleString('de-DE', { maximumFractionDigits: 2 })}%`}</small></div>)}</div>{booster && !pool.length && !booster.bonus_slots.some(slot => slot.choices.some(choice => choice.card.name.toLowerCase().includes(query.trim().toLowerCase()))) && <Empty>{booster.product_type === 'structure_deck' && !booster.cards_per_pack ? 'Die vollständige Deckliste wird noch geprüft.' : 'Diese Karte ist in diesem Booster nicht enthalten.'} <NavLink to="/cards">Im gesamten Katalog suchen</NavLink></Empty>}<Pagination page={page} pages={Math.max(1, Math.ceil(pool.length / 24))} change={setPage} /></section>
  </PageFrame>
}

export function BoosterHistoryPage() {
  const [history, setHistory] = useState<Awaited<ReturnType<typeof getBoosterHistory>>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    getBoosterHistory().then(items => { if (active) setHistory(items) }).catch(cause => { if (active) setError(cause.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])
  return <PageFrame eyebrow="ÖFFNUNGSHISTORIE" title="Deine letzten Booster" description="Deine letzten 20 Öffnungen und die daraus erhaltenen Karten."><Notice message={error} />{loading && <p role="status">Historie wird geladen …</p>}<div className="history-list">{history.map(opening => <div className="history-entry" key={opening.id}><div className="history-meta"><div><strong>{opening.booster_name}</strong><span>{new Date(opening.created_at.endsWith('Z') ? opening.created_at : opening.created_at + 'Z').toLocaleString('de-DE')} · {opening.credits_spent ? `${opening.credits_spent} Sammelpunkte Öffnungskosten (Altbestand)` : 'Kostenlos geöffnet'}</span></div><span>{opening.cards.length} Karten</span></div><div className="history-cards">{opening.cards.map((entry, index) => <div className="history-card" key={index}><div className="history-card-preview"><CardVisual card={entry.card} compact /></div><div><strong>{entry.card.name}</strong><span>{label(entry.rarity)}{entry.is_new ? ' · NEU' : ''}</span></div></div>)}</div></div>)}{!loading && !error && !history.length && <Empty>Du hast noch keine Booster geöffnet.</Empty>}</div></PageFrame>
}

function OpeningResult({ result }: { result: Awaited<ReturnType<typeof openBooster>> }) {
  const resultRef = useRef<HTMLElement>(null)
  useEffect(() => { resultRef.current?.scrollIntoView({ block: 'start', behavior: 'instant' }) }, [result.opening_id])
  return <section ref={resultRef} className="opening-result" aria-live="polite"><div className="result-heading"><p className="eyebrow accent">BOOSTER GEÖFFNET</p><h2>Deine gezogenen Karten</h2><span>{result.remaining} Packs verbleiben · {result.credits_remaining} Sammelpunkte · Öffnung kostenlos</span></div><div className="result-cards">{result.cards.map((card, index) => <CardVisual card={card} key={index} />)}</div><NavLink className="outline-button" to="/inventory">Zur Sammlung</NavLink><NavLink className="outline-button" to="/boosters/history">Zur Öffnungshistorie</NavLink></section>
}
export function TradePage() {
  return <PageFrame eyebrow="HANDEL" title="Karten mit der Community tauschen" description="Der Handel wird vorbereitet."><Empty>Das Erstellen und Annehmen verbindlicher Tauschangebote ist noch nicht verfügbar. Deine Karten bleiben in deiner Sammlung.</Empty></PageFrame>
}
export function BattlePassPage() {
  return <PageFrame eyebrow="SAISONPASS" title="Neue Sammelziele folgen" description="Missionen und Belohnungen werden vorbereitet."><Empty>Aktuell ist noch kein Saisonpass aktiv. Du kannst bereits Sammelpunkte sammeln und Booster öffnen.</Empty></PageFrame>
}
function PageFrame({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children: React.ReactNode }) {
  return <div className="page-wrap workspace-page"><section className="page-heading"><div><p className="eyebrow accent">{eyebrow}</p><h1>{title}</h1><p className="lede">{description}</p></div></section>{children}</div>
}
