import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { ArrowRight, Gem, PackageOpen } from 'lucide-react'
import type { BoosterSummary } from '../api/client'

export function BoosterCover({ name, imageUrl }: { name: string; imageUrl?: string | null }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  return <div className="booster-cover">
    {imageUrl && failedUrl !== imageUrl
      ? <img src={imageUrl} alt={`Cover: ${name}`} loading="lazy" onError={() => setFailedUrl(imageUrl)} />
      : <div className="booster-cover-missing"><PackageOpen size={36} /><strong>{name}</strong><span>Kein Cover verfügbar</span></div>}
  </div>
}

export function DiscoveryNav() {
  return <nav className="catalog-subnav" aria-label="Karten und Booster">
    <NavLink to="/boosters" end>Booster-Shop</NavLink><NavLink to="/my-packs">Meine Packs</NavLink><NavLink to="/cards">Karte suchen</NavLink><NavLink to="/sets">Sets entdecken</NavLink>
  </nav>
}

export function ProductLimit({ booster }: { booster: BoosterSummary }) {
  if (booster.product_type !== 'structure_deck') return null
  return <p className="product-limit" role="status">{!booster.cards_per_pack ? 'Deckliste wird geprüft · Noch nicht kaufbar' : booster.purchases_remaining === 0 ? 'Kauflimit erreicht · 3 von 3 gekauft' : `Noch ${booster.purchases_remaining} von 3 Käufen verfügbar`}<small>600 Sammelpunkte · {booster.bonus_cards ? `${booster.fixed_cards} feste Karten + ${booster.bonus_cards} Bonuskarte.` : 'Vollständige Deckliste mit Mehrfachexemplaren.'} Das Limit gilt dauerhaft pro Konto.</small></p>
}

export function buyLabel(booster: BoosterSummary) {
  return booster.product_type === 'structure_deck' && !booster.cards_per_pack ? 'In Prüfung' : booster.purchases_remaining === 0 ? 'Limit erreicht' : 'Kaufen'
}

export function BoosterTile({ booster, children }: { booster: BoosterSummary; children?: React.ReactNode }) {
  return <article className="booster-tile">
    <NavLink className="booster-tile-link" to={`/boosters/${booster.id}`}>
      <BoosterCover name={booster.name} imageUrl={booster.image_url} />
      <div className="booster-tile-copy"><span className="eyebrow">{booster.set_code || 'SAMMELBOOSTER'} · {booster.cards_per_pack} Karten pro Pack</span><h3>{booster.name}</h3><p>{booster.product_type === 'structure_deck' ? `${booster.pool_size} Kartenarten · ${booster.bonus_cards ? 'Deck + Bonus' : 'Fester Inhalt'}` : `${booster.pool_size} mögliche Karten`}</p></div>
    </NavLink>
    <div className="booster-tile-footer"><div className="booster-price"><Gem size={16} /><strong>{booster.cost}</strong><span>Sammelpunkte</span></div><span className="stock-label">{booster.owned} im Bestand</span>
      <NavLink className="booster-pool-link" to={`/boosters/${booster.id}`}>Enthaltene Karten ansehen <ArrowRight size={15} /></NavLink>
      <ProductLimit booster={booster} />
      {children && <div className="booster-tile-actions">{children}</div>}
    </div>
  </article>
}
