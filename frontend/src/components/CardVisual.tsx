import { useRef, useState } from 'react'
import { Sparkles } from 'lucide-react'
import type { CardRecord } from '../data/cards'
import { rarityInfo } from '../i18n'

export function CardBack({ failed = false }: { failed?: boolean }) {
  return <div className={`loading-card-back ${failed ? 'image-missing' : ''}`} aria-hidden="true"><span className="loading-card-border" /><span className="loading-card-sigil"><Sparkles size={28} /></span><span className="loading-card-caption">{failed ? 'Kartenbild derzeit nicht verfügbar' : 'Karte wird geladen'}</span>{!failed && <span className="loading-card-dots"><i /><i /><i /></span>}</div>
}

export function CardVisual({ card, compact = false, showQuantity = false }: { card: CardRecord; compact?: boolean; showQuantity?: boolean }) {
  const image = useRef<HTMLImageElement>(null)
  const [loadedUrl, setLoadedUrl] = useState('')
  const [failedUrls, setFailedUrls] = useState<string[]>([])
  const useFallback = failedUrls.includes(card.imageUrl) && !!card.fallbackImageUrl
  const source = useFallback ? card.fallbackImageUrl! : card.imageUrl
  const loaded = !!source && loadedUrl === source
  const failed = card.image_available === false || !source || failedUrls.includes(source)
  const original = useFallback || card.image_language === 'original'
  const rarity = rarityInfo(card.rarity)
  return <article className={`card-visual ${compact ? 'compact' : ''}`} aria-busy={!loaded && !failed}>
    <div className={`card-image-wrap ${card.tone} ${loaded ? 'card-loaded' : 'card-loading'}`}>
      {!loaded && <CardBack failed={failed} />}
      {!failed && <img key={source} ref={element => { image.current = element; if (element?.complete && element.naturalWidth && loadedUrl !== source) setLoadedUrl(source) }} src={source} alt={`${original ? 'Originalabbildung' : 'Deutsche Karte'}: ${card.name}`} loading="lazy" decoding="async" width="199" height="290" onLoad={() => setLoadedUrl(source)} onError={() => setFailedUrls(current => [...current, source])} />}
      {loaded && original && <span className="image-language-label" title="Deutsches Bild nicht verfügbar. Die Originalabbildung kann eine andere Sprache enthalten.">Originalbild</span>}
      <span className={`card-rarity-badge rarity-badge-${rarity.tone}`} aria-label={`Seltenheit: ${rarity.name}`} title={card.collected_rarities?.length ? `Gesammelte Seltenheiten: ${card.collected_rarities.map(value => rarityInfo(value).name).join(', ')}` : rarity.name}>{rarity.code}</span>
      {showQuantity && <span className="quantity-badge">×{card.quantity}</span>}
    </div>
    <div className="card-visual-copy"><div><strong title={card.name}>{card.name}</strong><span title={`${card.set} · ${card.setCode}`}>{card.setCode || card.set}</span></div></div>
  </article>
}

export function CardSkeletons({ count = 12 }: { count?: number }) {
  return <div className="catalog-grid collection-grid" aria-label="Karten werden geladen" role="status">{Array.from({ length: count }, (_, index) => <div className="card-visual" key={index}><div className="card-image-wrap"><CardBack /></div><div className="skeleton-card-name" /></div>)}</div>
}
