"""German display text only; effect identifiers, ordering and rules stay untouched."""
import re


EFFECTS = {
    'special summon': 'Spezialbeschwörung',
    'special summon this card': 'Diese Karte als Spezialbeschwörung beschwören',
    'special summon it': 'Die Karte als Spezialbeschwörung beschwören',
    'special summon this card from your hand': 'Diese Karte von deiner Hand als Spezialbeschwörung beschwören',
    'special summon from hand': 'Von der Hand als Spezialbeschwörung beschwören',
    'special summon this card from your gy': 'Diese Karte aus deinem Friedhof als Spezialbeschwörung beschwören',
    'special summon this card from your graveyard': 'Diese Karte aus deinem Friedhof als Spezialbeschwörung beschwören',
    'destroy': 'Zerstören', 'search': 'Karte suchen', 'banish': 'Verbannen',
    'inflict damage': 'Schaden zufügen', 'damage': 'Schaden',
    'inflict damage to your opponent': 'Deinem Gegner Schaden zufügen',
    'add to hand': 'Der Hand hinzufügen', 'add card': 'Karte hinzufügen',
    'add this card to your hand': 'Diese Karte deiner Hand hinzufügen',
    'activate 1 of these effects': 'Einen dieser Effekte aktivieren',
    'return to hand': 'Auf die Hand zurückgeben', 'return to deck': 'Ins Deck zurücklegen',
    'equip': 'Ausrüsten', 'increase atk': 'ATK erhöhen', 'gain attack': 'ATK erhalten',
    'gain atk': 'ATK erhalten', 'change atk': 'ATK ändern', 'reduce atk': 'ATK verringern',
    'draw': 'Karte ziehen', 'draw card': 'Karte ziehen',
    'send to graveyard': 'Auf den Friedhof legen', 'send to gy': 'Auf den Friedhof legen',
    'negate': 'Annullieren', 'negate effect': 'Effekt annullieren',
    'negate that effect': 'Diesen Effekt annullieren', 'negate attack': 'Angriff annullieren',
    'negate the activation': 'Aktivierung annullieren', 'negate activation': 'Aktivierung annullieren',
    'gain lp': 'LP erhalten', 'fusion summon': 'Fusionsbeschwörung',
    'synchro summon': 'Synchrobeschwörung', 'xyz summon': 'Xyz-Beschwörung',
    'link summon': 'Linkbeschwörung', 'ritual summon': 'Ritualbeschwörung',
    'pendulum summon': 'Pendelbeschwörung', 'normal summon': 'Normalbeschwörung',
    'change battle position': 'Kampfposition ändern', 'change position': 'Position ändern',
    'place counter': 'Zählmarke legen', 'remove counter': 'Zählmarke entfernen',
    'activate': 'Aktivieren', 'set': 'Setzen', 'set this card': 'Diese Karte setzen',
    'take control': 'Kontrolle übernehmen', 'normal summon without tribute': 'Ohne Tribut als Normalbeschwörung beschwören',
    'change level': 'Stufe ändern', 'increase level': 'Stufe erhöhen',
    'excavate': 'Karten ausgraben', 'attach': 'Als Material anhängen',
    'change to face-down defense position': 'In die verdeckte Verteidigungsposition ändern',
    'change to defense position': 'In die Verteidigungsposition ändern',
    'place this card in your pendulum zone': 'Diese Karte in deine Pendelzone legen',
    'select the card to add to your hand or special summon': 'Karte zum Hinzufügen auf die Hand oder zur Spezialbeschwörung wählen',
    'coin toss': 'Münze werfen', 'toss a coin': 'Münze werfen', 'roll a die': 'Würfel werfen',
    'yes': 'Ja', 'no': 'Nein',
}


def german_effect(text, description_de=None, index=0):
    key = ' '.join((text or '').strip().rstrip('.?').lower().split())
    if not key:
        return None
    if key in EFFECTS:
        return EFFECTS[key]
    draw = re.fullmatch(r'draw (\d+) cards?', key)
    if draw:
        count = int(draw[1])
        return f'{count} Karte' + ('n' if count != 1 else '') + ' ziehen'
    destroy = re.fullmatch(r'destroy (\d+) (card|monster)(s)? (on the field|your opponent controls)', key)
    if destroy:
        count = int(destroy[1])
        noun = 'Karte' + ('n' if count != 1 else '') if destroy[2] == 'card' else 'Monster'
        location = 'auf dem Spielfeld' if destroy[4] == 'on the field' else 'unter gegnerischer Kontrolle'
        return f'{count} {noun} {location} zerstören'
    # Never infer an effect number from the order of sentences in the card text.
    # A missing short translation shows the real German card text, explicitly
    # marked as context, rather than a fabricated description of that effect.
    if description_de:
        return f'Effektoption {index + 1} · Deutscher Kartentext:\n{description_de}'
    return f'Effektoption {index + 1} · Deutsche Detailbeschreibung noch nicht verfügbar.'
