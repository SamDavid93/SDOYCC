from unittest import TestCase
from app.modules.duel_localization import german_effect


class DuelLocalizationTests(TestCase):
    def test_known_effects_keep_their_distinct_meaning(self):
        self.assertEqual(german_effect('Draw 2 cards'), '2 Karten ziehen')
        self.assertEqual(german_effect('Special Summon this card from your hand'), 'Diese Karte von deiner Hand als Spezialbeschwörung beschwören')
        self.assertEqual(german_effect('Destroy 1 monster your opponent controls'), '1 Monster unter gegnerischer Kontrolle zerstören')

    def test_missing_translation_does_not_invent_an_effect_from_card_sentence_order(self):
        text = german_effect('Unsupported custom effect', 'Deutscher Kartentext', 2)
        self.assertIn('Effektoption 3', text)
        self.assertIn('Deutscher Kartentext', text)
        self.assertNotIn('Unsupported', text)
        self.assertIn('noch nicht verfügbar', german_effect('Other effect'))
        self.assertIsNone(german_effect(''))
