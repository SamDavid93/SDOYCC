export const labels: Record<string, string> = {
  unknown: 'Ausgabe nicht bestimmt',
  DARK: 'Finsternis', LIGHT: 'Licht', EARTH: 'Erde', WATER: 'Wasser', FIRE: 'Feuer', WIND: 'Wind', DIVINE: 'Göttlich', SPELL: 'Zauber', TRAP: 'Falle',
  common: 'Gewöhnlich', rare: 'Selten', super_rare: 'Superselten', ultra_rare: 'Ultraselten', secret_rare: 'Geheim selten', ultimate_rare: 'Ultimativ selten', ghost_rare: 'Geisterselten', starlight_rare: 'Sternenlicht-selten', quarter_century_secret_rare: 'Jubiläums-Geheimselten', platinum_secret_rare: 'Platin-Geheimselten', other: 'Weitere Seltenheit',
  Dragon: 'Drache', Spellcaster: 'Hexer', Warrior: 'Krieger', 'Beast-Warrior': 'Ungeheuer-Krieger', Beast: 'Ungeheuer', 'Winged Beast': 'Geflügeltes Ungeheuer', Fiend: 'Unterweltler', Fairy: 'Fee', Insect: 'Insekt', Dinosaur: 'Dinosaurier', Reptile: 'Reptil', Fish: 'Fisch', 'Sea Serpent': 'Seeschlange', Aqua: 'Aqua', Pyro: 'Pyro', Thunder: 'Donner', Rock: 'Fels', Plant: 'Pflanze', Machine: 'Maschine', Psychic: 'Psi', 'Divine-Beast': 'Göttliches Ungeheuer', 'Creator God': 'Schöpfergott', Wyrm: 'Wyrm', Cyberse: 'Cyberse', Illusion: 'Illusion', Zombie: 'Zombie',
  Continuous: 'Permanent', Counter: 'Konter', Equip: 'Ausrüstung', Field: 'Spielfeld', Normal: 'Normal', 'Quick-Play': 'Schnell', Ritual: 'Ritual',
  Unlimited: 'Unbegrenzt', Limited: 'Limitiert', 'Semi-Limited': 'Halblimitiert', Banned: 'Verboten', Forbidden: 'Verboten',
  Top: 'Oben', Bottom: 'Unten', Left: 'Links', Right: 'Rechts', 'Top-Left': 'Oben links', 'Top-Right': 'Oben rechts', 'Bottom-Left': 'Unten links', 'Bottom-Right': 'Unten rechts',
}
export function label(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return 'Nicht angegeben'
  const text = String(value)
  if (labels[text]) return labels[text]
  const normalized = text.toLowerCase().replaceAll(' ', '_')
  if (labels[normalized]) return labels[normalized]
  const types: Record<string, string> = { 'Spell Card': 'Zauberkarte', 'Normal Spell': 'Normale Zauberkarte', 'Trap Card': 'Fallenkarte', 'Skill Card': 'Fähigkeitskarte', Token: 'Spielmarke' }
  if (types[text]) return types[text]
  if (text.includes('Monster')) return text.replaceAll('Pendulum', 'Pendel').replaceAll('Effect', 'Effekt').replaceAll('Tuner', 'Empfänger').replaceAll('Gemini', 'Zwilling').replaceAll('XYZ', 'Xyz').replaceAll('Spirit', 'Spirit').replaceAll(' ', '-')
  return text // Proper names (sets, characters and archetypes) retain their official spelling.
}
export function rarityInfo(value: string) {
  if (value === 'unknown') return { code: '?', tone: 'silver', name: 'Ausgabe nicht bestimmt' }
  const rarity = value.toLowerCase().replaceAll(' ', '_')
  if (/secret|starlight|quarter|platinum/.test(rarity)) return { code: 'GR', tone: 'prismatic', name: label(rarity) }
  if (/ultimate|ghost/.test(rarity)) return { code: 'UR+', tone: 'prismatic', name: label(rarity) }
  if (/ultra|gold/.test(rarity)) return { code: 'UR', tone: 'gold', name: label(rarity) }
  if (/super/.test(rarity)) return { code: 'SR', tone: 'violet', name: label(rarity) }
  if (rarity === 'rare') return { code: 'R', tone: 'blue', name: label(rarity) }
  return { code: rarity === 'common' ? 'N' : '★', tone: 'silver', name: label(rarity) }
}
