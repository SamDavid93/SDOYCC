import { Cross, Hand, Layers3, CircleSlash, RadioTower, LayoutGrid } from 'lucide-react'
import './card-symbols.css'

export function isTuner(type?: string | number | null) {
  // OCGCore TYPE_TUNER, independent of effect text mentioning other Tuners.
  if (typeof type === 'number') return Boolean(type & 0x1000)
  return typeof type === 'string' && /\bTuner\b|Empfänger/i.test(type) && !/\bnon[- ]tuner\b|Nicht[- ]Empfänger/i.test(type)
}

export function TunerBadge({ type, compact = false }: { type?: string | number | null; compact?: boolean }) {
  return isTuner(type) ? <span className={`card-tuner-symbol${compact ? ' is-compact' : ''}`} role="img" aria-label="Empfänger-Monster" title="Empfänger-Monster"><RadioTower aria-hidden="true" />{!compact && <strong>Empfänger</strong>}</span> : null
}

const areas = [
  { zone: 2, name: 'Hand', Icon: Hand, match: /\bHand(?:karten?|monster|effekt)?\b|\bhands?\b/i },
  { zone: 16, name: 'Friedhof', Icon: Cross, match: /Friedh(?:of|öfe|ofs)|\bgraveyards?\b|\bGY\b/i },
  { zone: 32, name: 'Verbannt', Icon: CircleSlash, match: /verbann|\bbanish|removed from play/i },
  { zone: 1, name: 'Deck', Icon: Layers3, match: /\bDeck(?:s|karten?)?\b/i },
]

export function CardOrigin({ zone, opponent = false }: { zone?: number; opponent?: boolean }) {
  const area = areas.find(item => item.zone === zone) || (zone === 64 ? { name: 'Extra-Deck', Icon: Layers3 }
    : zone === 4 || zone === 8 ? { name: 'Spielfeld', Icon: LayoutGrid } : null)
  if (!area) return null
  const { Icon, name } = area
  const label = opponent ? `Gegner: ${name}` : name
  return <span className={`card-origin-symbol effect-area-${zone}`} data-origin-zone={zone} role="img" aria-label={label} title={`Diese Karte befindet sich hier: ${label}`}><Icon aria-hidden="true" /><strong>{label}</strong></span>
}

export function EffectLocations({ text, zones = [] }: { text?: string | null; zones?: number[] }) {
  const visible = areas.filter(area => zones.includes(area.zone) || area.match.test(text || ''))
  return visible.length ? <div className="effect-location-symbols" role="group" aria-label="Effektbereiche">
    {visible.map(({ zone, name, Icon }) => <span className={`effect-location-symbol effect-area-${zone}`} key={zone} title={name}><Icon aria-hidden="true" /><strong>{name}</strong></span>)}
  </div> : null
}
