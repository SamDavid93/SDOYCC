type GermanCard = { description?: string; description_language?: string } | null | undefined
export const missingGermanText = 'Für diese Karte ist noch kein deutscher Kartentext verfügbar.'

export function germanCardText(card: GermanCard) {
  return card?.description_language === 'de' && card.description?.trim() ? card.description : missingGermanText
}

export function germanEffectText(text: string | null | undefined, language: string | null | undefined, card?: GermanCard) {
  return language === 'de' && text?.trim() ? text : germanCardText(card)
}
