import type { CardRecord } from '../data/cards'
import { API_BASE_URL, apiFetch as fetch, api } from './transport'


export type ApiCard = Omit<CardRecord, 'set' | 'setCode' | 'imageUrl' | 'quantity' | 'price' | 'tone'> & {
  set: string
  set_code: string
  image_url: string
  fallback_image_url?: string | null
}

export function toCardRecord(card: ApiCard, index = 0): CardRecord {
  return {
    ...card,
    setCode: card.set_code,
    imageUrl: card.image_url ? new URL(card.image_url, API_BASE_URL).href : '',
    fallbackImageUrl: card.fallback_image_url ? new URL(card.fallback_image_url, API_BASE_URL).href : undefined,
    quantity: 1,
    price: '—',
    tone: ['blue', 'violet', 'red', 'gold', 'teal'][index % 5] as CardRecord['tone'],
  }
}

export async function getApiHealth(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE_URL}/health`)
  if (!response.ok) throw new Error('Schnittstelle nicht erreichbar')
  return response.json() as Promise<{ status: string }>
}

export async function getCards(search = ''): Promise<CardRecord[]> {
  const query = search ? `?search=${encodeURIComponent(search)}` : ''
  const response = await fetch(`${API_BASE_URL}/cards${query}`)
  if (!response.ok) throw new Error('Kartenkatalog konnte nicht geladen werden')
  const payload = await response.json() as { items: ApiCard[] }
  return payload.items.map(toCardRecord)
}

export type CardPage = { items: CardRecord[]; total: number; page: number; page_size: number }

export async function getCardPage(params: { search?: string; rarity?: string; cardType?: string; attribute?: string; setId?: number; page?: number; pageSize?: number } = {}): Promise<CardPage> {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.rarity) query.set('rarity', params.rarity)
  if (params.cardType) query.set('card_type', params.cardType)
  if (params.attribute) query.set('attribute', params.attribute)
  if (params.setId) query.set('set_id', String(params.setId))
  query.set('page', String(params.page || 1))
  query.set('page_size', String(params.pageSize || 24))
  const response = await fetch(`${API_BASE_URL}/cards?${query}`)
  if (!response.ok) throw new Error('Kartenkatalog konnte nicht geladen werden')
  const payload = await response.json() as { items: ApiCard[]; total: number; page: number; page_size: number }
  return { items: payload.items.map(toCardRecord), total: payload.total, page: payload.page, page_size: payload.page_size }
}

export type CardSetSummary = { id: number; external_id: string; name: string; code: string | null; release_date: string | null; card_count: number | null; cover_image_url: string | null }

export async function getCardSets(search = '', page = 1): Promise<{ items: CardSetSummary[]; total: number }> {
  const response = await fetch(`${API_BASE_URL}/card-sets?search=${encodeURIComponent(search)}&page=${page}&page_size=30`)
  if (!response.ok) throw new Error('Kartensets konnten nicht geladen werden')
  return response.json()
}

export async function getCardDetail(id: number): Promise<CardRecord> {
  const response = await fetch(`${API_BASE_URL}/cards/${id}`)
  if (!response.ok) throw new Error('Karte konnte nicht geladen werden')
  return toCardRecord(await response.json())
}

export async function getCardPrintings(id: number): Promise<{ id: number; set_id: number | null; external_printing_id: string; set_code: string | null; rarity: string | null; provider_rarity_name: string | null; image_url: string | null }[]> {
  const response = await fetch(`${API_BASE_URL}/cards/${id}/printings`)
  if (!response.ok) throw new Error('Kartenausgaben konnten nicht geladen werden')
  return response.json()
}

export async function getSetCards(id: number): Promise<CardRecord[]> {
  const response = await fetch(`${API_BASE_URL}/card-sets/${id}/cards`)
  if (!response.ok) throw new Error('Set-Karten konnten nicht geladen werden')
  const payload = await response.json() as ApiCard[]
  return payload.map(toCardRecord)
}

export type PackSummary = { id: number; name: string; code: string | null; release_date: string | null; card_count: number | null; cover_image_url: string | null }
export type BoosterSummary = { id: number; key: string; name: string; set_id?: number | null; set_name?: string | null; set_code?: string | null; image_url?: string | null; cards_per_pack: number; cost: number; owned: number; pool_size: number; collection_progress?: { owned: number; total: number; percent: number }; fixed_cards: number; bonus_cards: number; content_notes: string | null; product_type: string; purchase_limit: number | null; purchased_total: number; purchases_remaining: number | null }
export type BoosterOpening = { opening_id: number; booster_id: number; cards: CardRecord[]; remaining: number; credits_remaining: number }

export async function getPacks(search = ''): Promise<PackSummary[]> {
  const query = search ? `?search=${encodeURIComponent(search)}` : ''
  const response = await fetch(`${API_BASE_URL}/packs${query}`)
  if (!response.ok) throw new Error('Booster-Katalog nicht verfügbar')
  const payload = await response.json() as { items: PackSummary[] }
  return payload.items
}


export async function getBoosters(): Promise<BoosterSummary[]> {
  const response = await fetch(`${API_BASE_URL}/boosters`)
  if (!response.ok) throw new Error('Booster konnten nicht geladen werden')
  return response.json() as Promise<BoosterSummary[]>
}

export async function purchaseBooster(id: number, quantity = 1): Promise<{ booster_id: number; purchased: number; owned: number; credits_remaining: number; total_cost: number; purchased_total: number; purchases_remaining: number | null }> {
  const response = await fetch(`${API_BASE_URL}/boosters/${id}/purchase`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ quantity }) })
  if (!response.ok) throw new Error((await response.json() as { detail?: string }).detail || 'Booster konnte nicht gekauft werden')
  return response.json()
}

export async function getBoostersForSet(setId: number): Promise<BoosterSummary[]> {
  const response = await fetch(`${API_BASE_URL}/card-sets/${setId}/boosters`)
  if (!response.ok) throw new Error('Set-Booster konnten nicht geladen werden')
  return response.json()
}

export type BonusSlot = { name: string; quantity: number; choices: { card: CardRecord; rarity: string; probability: number }[] }

export async function getBooster(id: number): Promise<BoosterSummary & { bonus_slots: BonusSlot[]; rarities: { rarity: string; cards: number }[]; pool: { card: CardRecord; rarity: string; weight: number; quantity: number | null }[] }> {
  const response = await fetch(`${API_BASE_URL}/boosters/${id}`)
  if (!response.ok) throw new Error('Booster konnte nicht geladen werden')
  const payload = await response.json() as BoosterSummary & { bonus_slots: { name: string; quantity: number; choices: { card: ApiCard; rarity: string; probability: number }[] }[]; rarities: { rarity: string; cards: number }[]; pool: { card: ApiCard; rarity: string; weight: number; quantity: number | null }[] }
  return { ...payload, bonus_slots: payload.bonus_slots.map(slot => ({ ...slot, choices: slot.choices.map((choice, index) => ({ ...choice, card: toCardRecord(choice.card, index) })) })), pool: payload.pool.map((entry, index) => ({ ...entry, card: toCardRecord(entry.card, index) })) }
}

export async function openBooster(id: number): Promise<BoosterOpening> {
  const response = await fetch(`${API_BASE_URL}/boosters/${id}/open`, { method: 'POST' })
  if (!response.ok) throw new Error((await response.json() as { detail?: string }).detail || 'Booster konnte nicht geöffnet werden')
  const payload = await response.json() as { opening_id: number; booster_id: number; cards: ApiCard[]; remaining: number; credits_remaining: number }
  return { ...payload, cards: payload.cards.map(toCardRecord) }
}

export async function getBoosterHistory(): Promise<{ id: number; booster_id: number; booster_name: string; credits_spent: number; created_at: string; cards: { rarity: string; is_new: boolean; card: CardRecord }[] }[]> {
  const response = await fetch(`${API_BASE_URL}/boosters/me/history`)
  if (!response.ok) throw new Error('Öffnungshistorie konnte nicht geladen werden')
  const payload = await response.json() as { id: number; booster_id: number; booster_name: string; credits_spent: number; created_at: string; cards: { rarity: string; is_new: boolean; card: ApiCard }[] }[]
  return payload.map(opening => ({ ...opening, cards: opening.cards.map((entry, index) => ({ ...entry, card: toCardRecord({ ...entry.card, rarity: entry.rarity }, index) })) }))
}

export { API_BASE_URL }

export type Inventory = { items: CardRecord[]; total_quantity: number; unique_cards: number }
export async function getInventory(): Promise<Inventory> {
  const result = await api<{ items: { card: ApiCard; quantity: number }[]; total_quantity: number; unique_cards: number }>('/inventory/me')
  return { ...result, items: result.items.map((item, index) => ({ ...toCardRecord(item.card, index), quantity: item.quantity })) }
}
export type Summary = { total_cards: number; unique_cards: number; packs_opened: number; owned_packs: number }
export const getSummary = () => api<Summary>('/users/me/summary')
export type WalletEntry = { id: number; amount: number; balance_after: number; reason: string; created_at: string }
export const getWalletHistory = () => api<WalletEntry[]>('/wallet/me/history')

export const getBoostersForCard = (cardId: number) => api<BoosterSummary[]>(`/cards/${cardId}/boosters`)

export type CollectionFilters = Record<string, (string | number | { value: number; label: string })[]>
export const getCollectionFilters = () => api<CollectionFilters>('/collection/filters')
export async function getCollection(params: Record<string, string>) {
  const result = await api<{ items: { card: ApiCard; quantity: number }[]; total: number; total_quantity: number; unique_cards: number }>(`/collection?${new URLSearchParams(params)}`)
  return { ...result, items: result.items.map((item, index) => ({ ...toCardRecord(item.card, index), quantity: item.quantity })) }
}
