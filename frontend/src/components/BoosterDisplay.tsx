import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { ArrowRight, Gem } from 'lucide-react'
import type { BoosterSummary } from '../api/client'
import { BoosterArtwork } from './BoosterArtwork'
import officialCovers from '../data/officialBoosterCovers.json'

const coverIdentity = (name: string) => name.replace(/\s+Booster$/i, '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '')

export function BoosterCover({ name, code }: { name: string; code?: string | null }) {
  const cover = (officialCovers as Record<string, { file: string; width: number; height: number; focus?: number[] }>)[coverIdentity(name)]
  const url = cover ? import.meta.env.BASE_URL + cover.file : null
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  return <div className="booster-cover">{cover && url && failedUrl !== url
    ? cover.focus ? <svg className="official-product-cover" viewBox={cover.focus.join(' ')} width="100%" height="100%" role="img" aria-label={`Offizielles Cover: ${name}`} style={{ minWidth: 0, minHeight: 0, overflow: 'hidden' }}><image href={url} width={cover.width} height={cover.height} onError={() => setFailedUrl(url)} /></svg>
      : <img src={url} width={cover.width} height={cover.height} alt={`Offizielles Cover: ${name}`} loading="lazy" decoding="async" onError={() => setFailedUrl(url)} />
    : <BoosterArtwork name={name} code={code} />}</div>
}

export function DiscoveryNav() {
  return <nav className="catalog-subnav" aria-label="Karten und Booster">
    <NavLink to="/boosters" end>Booster-Shop</NavLink><NavLink to="/my-packs">Meine Packs</NavLink><NavLink to="/cards">Karte suchen</NavLink><NavLink to="/sets">Sets entdecken</NavLink>
  </nav>
}

export function ProductLimit({ booster }: { booster: BoosterSummary }) {
  if (booster.product_type !== 'structure_deck') return booster.rare_guaranteed ? <p className="product-limit" role="status">{booster.cards_per_pack ? `${booster.cards_per_pack} Karten · Mindestens 1 Rare oder höher garantiert` : 'Kartenpool wird geprüft · Rare-Garantie derzeit nicht erfüllbar'}</p> : null
  return <p className="product-limit" role="status">{!booster.cards_per_pack ? 'Deckliste wird geprüft · Noch nicht kaufbar' : booster.purchases_remaining === 0 ? 'Kauflimit erreicht · 3 von 3 gekauft' : `Noch ${booster.purchases_remaining} von 3 Käufen verfügbar`}<small>{booster.cost} Sammelpunkte · {booster.bonus_cards ? `${booster.fixed_cards} feste Karten + ${booster.bonus_cards} Bonuskarte.` : 'Vollständige Deckliste mit Mehrfachexemplaren.'} Das Limit gilt dauerhaft pro Konto.</small></p>
}

export function buyLabel(booster: BoosterSummary) {
  return booster.product_type === 'structure_deck' && !booster.cards_per_pack ? 'In Prüfung' : booster.purchases_remaining === 0 ? 'Limit erreicht' : 'Kaufen'
}

export function BoosterProgress({ booster }: { booster: BoosterSummary }) {
  const progress = booster.collection_progress
  if (!progress) return null
  const complete = progress.total > 0 && progress.owned === progress.total
  return <div className={`booster-collection-progress${complete ? ' is-complete' : ''}`}>
    <div className="booster-progress-heading"><span>{complete ? 'Sammlung vollständig' : 'Dein Sammelfortschritt'}</span><strong>{progress.percent.toLocaleString('de-DE', { maximumFractionDigits: 1 })} %</strong></div>
    <progress value={progress.owned} max={progress.total || 1} aria-label={`Sammelfortschritt für ${booster.name}`} aria-valuetext={`${progress.owned} von ${progress.total} unterschiedlichen Karten`} />
    <span><strong>{progress.owned.toLocaleString('de-DE')} von {progress.total.toLocaleString('de-DE')}</strong> Karten gesammelt</span>
    <small>Jede Kartenart zählt einmal, unabhängig von Ausgabe und Herkunft.</small>
  </div>
}

export function BoosterTile({ booster, children }: { booster: BoosterSummary; children?: React.ReactNode }) {
  return <article className="booster-tile">
    <NavLink className="booster-tile-link" to={`/boosters/${booster.id}`}>
      <BoosterCover name={booster.name} code={booster.set_code} />
      <div className="booster-tile-copy"><span className="eyebrow">{booster.set_code || 'SAMMELBOOSTER'} · {booster.cards_per_pack} Karten pro Pack</span><h3>{booster.name}</h3><p>{booster.product_type === 'structure_deck' ? `${booster.pool_size} Kartenarten · ${booster.bonus_cards ? 'Deck + Bonus' : 'Fester Inhalt'}` : `${booster.pool_size} mögliche Karten`}</p></div>
    </NavLink>
    <BoosterProgress booster={booster} />
    <div className="booster-tile-footer"><div className="booster-price"><Gem size={16} /><strong>{booster.cost}</strong><span>Sammelpunkte</span></div><span className="stock-label">{booster.owned} im Bestand</span>
      <NavLink className="booster-pool-link" to={`/boosters/${booster.id}`}>Enthaltene Karten ansehen <ArrowRight size={15} /></NavLink>
      <ProductLimit booster={booster} />
      {children && <div className="booster-tile-actions">{children}</div>}
    </div>
  </article>
}
