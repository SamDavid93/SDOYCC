import { useEffect, useState } from 'react'
import { Confirm, ErrorBox, Pager, useAction, useRead, type Page } from './Workflow'

type Product = { id: number; name: string; product_type: string; cost: number; cards_per_pack: number; rare_guaranteed: boolean; price_override: number | null; draw_count_override: number | null; active: boolean }

export function AdminProducts() {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [revision, setRevision] = useState(0)
  const [selected, setSelected] = useState<Product>()
  const [price, setPrice] = useState('')
  const [count, setCount] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [receipt, setReceipt] = useState('')
  const request = useRead<Page<Product>>(`/admin/products?search=${encodeURIComponent(query)}&page=${page}`, revision)
  const act = useAction()
  useEffect(() => { const timer = setTimeout(() => { setQuery(search); setPage(1) }, 250); return () => clearTimeout(timer) }, [search])
  function edit(product: Product) {
    setSelected(product)
    setPrice(product.price_override == null ? '' : String(product.price_override))
    setCount(product.draw_count_override == null ? '' : String(product.draw_count_override))
  }
  const valid = (price === '' || (Number.isInteger(Number(price)) && Number(price) >= 0 && Number(price) <= 1000000)) && (count === '' || (Number.isInteger(Number(count)) && Number(count) >= 1 && Number(count) <= 100))
  return <section className="content-panel workflow-page">
    <h2>Preise & Packinhalt</h2>
    <p>Individuelle Regeln pro Produkt. Leere Felder verwenden wieder den Standardpreis beziehungsweise die ursprünglichen Ziehungsregeln.</p>
    {receipt && <p className="success-notice" role="status">{receipt}</p>}
    <label>Produkt suchen<input value={search} maxLength={100} onChange={event => setSearch(event.target.value)} placeholder="Booster oder Structure Deck …" /></label>
    <ErrorBox message={request.error} />
    {!request.data ? <p role="status">Produkte werden geladen …</p> : <>
      <div className="admin-account-list">{request.data.items.map(product => <div className="admin-entry" key={product.id}>
        <div><strong>{product.name}</strong><small>{product.product_type === 'structure_deck' ? 'Structure Deck · feste Deckliste' : `${product.cards_per_pack || 'In Prüfung'} Karten${product.rare_guaranteed ? ' · Rare garantiert' : ''}`} · {product.cost.toLocaleString('de-DE')} Punkte{!product.active ? ' · Inaktiv' : ''}</small></div>
        <button className="outline-button" onClick={() => edit(product)}>Anpassen</button>
      </div>)}</div>
      {!request.data.items.length && <p>Keine Produkte gefunden.</p>}
      <Pager page={page} setPage={setPage} total={request.data.total} />
    </>}
    {selected && <div className="workflow-receipt">
      <h3>{selected.name}</h3>
      <div className="workflow-fields">
        <label>Preis in Sammelpunkten<input aria-label="Produktpreis" type="number" min="0" max="1000000" step="1" value={price} placeholder={selected.product_type === 'structure_deck' ? 'Standard: 600' : 'Standard: 100'} onChange={event => setPrice(event.target.value)} /></label>
        {selected.product_type !== 'structure_deck' && <label>Karten pro Pack<input aria-label="Karten pro Pack" type="number" min="1" max="100" step="1" value={count} placeholder="Standard-Ziehungsregeln" onChange={event => setCount(event.target.value)} /></label>}
      </div>
      <p>{selected.product_type === 'structure_deck' ? 'Feste Kartenliste, Bonuskarten und Kauflimit bleiben erhalten.' : 'Bei individueller Kartenanzahl ist eine Rare oder höher enthalten. Ohne passende Karte im Pool bleibt das Pack gesperrt.'}</p>
      <p>Preisänderungen gelten für neue Käufe. Die Kartenanzahl gilt auch für bereits gekaufte, noch ungeöffnete Packs.</p>
      <button className="primary-button" disabled={!valid} onClick={() => setConfirm(true)}>Änderung prüfen</button>{' '}
      <button className="text-button" onClick={() => { setPrice(''); setCount('') }}>Auf Standard zurücksetzen</button>{' '}
      <button className="text-button" onClick={() => setSelected(undefined)}>Schließen</button>
    </div>}
    {selected && confirm && <Confirm title="Produktregeln ändern" admin busy={act.busy} error={act.error} close={() => setConfirm(false)} confirm={async (password, reason) => {
      const result = await act.run<{ audit_id: number }>(`/admin/products/${selected.id}`, {
        price_override: price === '' ? null : Number(price), draw_count_override: count === '' ? null : Number(count),
        expected_price_override: selected.price_override, expected_draw_count_override: selected.draw_count_override, password, reason,
      })
      if (result) { setReceipt(`${selected.name}: Änderungen gespeichert · Beleg #${result.audit_id}`); setConfirm(false); setSelected(undefined); setRevision(value => value + 1) }
    }}>
      <p><strong>{selected.name}</strong></p>
      <p>Preis: {selected.cost} → {price === '' ? (selected.product_type === 'structure_deck' ? 600 : 100) : price} Sammelpunkte</p>
      {selected.product_type !== 'structure_deck' && <p>Karten pro Pack: {selected.cards_per_pack || 'In Prüfung'} → {count || 'Standard-Ziehungsregeln'}</p>}
    </Confirm>}
  </section>
}
