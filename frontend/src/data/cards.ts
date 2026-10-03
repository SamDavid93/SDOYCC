export type CardRarity = string
export type OwnedVariant = { id: number | null; rarity: string | null; legacy: boolean; source: string | null; quantity: number; reserved: number; available: number; bound: boolean }

export type CardRecord = {
  image_available?: boolean
  image_language?: 'de' | 'original'
  fallbackImageUrl?: string
  localized?: boolean
  description?: string | null
  description_language?: 'de' | 'en'
  race?: string | null
  archetype?: string | null
  level?: number | null
  atk?: number | null
  defense?: number | null
  scale?: number | null
  link_value?: number | null
  link_markers?: string[]
  ban_status?: string | null
  collected_rarities?: string[]
  owned_variants?: OwnedVariant[]
  id: number
  name: string
  set: string
  setCode: string
  rarity: CardRarity
  type: string
  attribute: string
  imageUrl: string
  quantity: number
  price: string
  tone: 'blue' | 'violet' | 'red' | 'gold' | 'teal'
}

const imageUrl = (id: number) => `https://images.ygoprodeck.com/images/cards/${id}.jpg`

export const cards: CardRecord[] = [
  { id: 89631139, name: 'Blue-Eyes White Dragon', set: 'Legend of Blue Eyes', setCode: 'LOB-001', rarity: 'Ultra Rare', type: 'Normal Monster', attribute: 'LIGHT', imageUrl: imageUrl(89631139), quantity: 3, price: '€18.40', tone: 'blue' },
  { id: 46986414, name: 'Dark Magician', set: 'Starter Deck Yugi', setCode: 'SDY-006', rarity: 'Rare', type: 'Normal Monster', attribute: 'DARK', imageUrl: imageUrl(46986414), quantity: 2, price: '€7.80', tone: 'violet' },
  { id: 14558127, name: 'Ash Blossom & Joyous Spring', set: 'Maximum Crisis', setCode: 'MACR-EN036', rarity: 'Secret Rare', type: 'Effect Monster', attribute: 'FIRE', imageUrl: imageUrl(14558127), quantity: 1, price: '€24.10', tone: 'red' },
  { id: 74677422, name: 'Red-Eyes Black Dragon', set: 'Legend of Blue Eyes', setCode: 'LOB-070', rarity: 'Ultra Rare', type: 'Normal Monster', attribute: 'DARK', imageUrl: imageUrl(74677422), quantity: 4, price: '€11.25', tone: 'red' },
  { id: 86066372, name: 'Accesscode Talker', set: 'Eternity Code', setCode: 'ETCO-EN046', rarity: 'Secret Rare', type: 'Link Monster', attribute: 'DARK', imageUrl: imageUrl(86066372), quantity: 1, price: '€16.90', tone: 'teal' },
  { id: 55144522, name: 'Pot of Greed', set: 'Metal Raiders', setCode: 'MRD-040', rarity: 'Common', type: 'Normal Spell', attribute: 'SPELL', imageUrl: imageUrl(55144522), quantity: 6, price: '€1.20', tone: 'gold' },
]

export const recentCards = cards.slice(0, 3)
