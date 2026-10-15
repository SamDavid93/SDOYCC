from unittest import TestCase
from app.modules.duel_localization import german_effect, german_description


class DuelLocalizationTests(TestCase):
    def test_mixed_pendulum_feed_never_labels_english_as_german(self):
        text = '[ Pendulum Effect ] \\nOnce per turn: You can destroy this card.\\n[ Monster Effect ] \\nFalls diese Karte zerstört wird: Ziehe 1 Karte.'
        result = german_description(text)
        self.assertIn('[Pendeleffekt]', result)
        self.assertIn('Übersetzung dieses Abschnitts', result)
        self.assertIn('Falls diese Karte zerstört wird', result)
        self.assertNotIn('Once per turn', result)
        self.assertNotIn('Monster Effect', result)

    def test_missing_or_mislabeled_translation_never_falls_back_to_english(self):
        for text in ('You can target 1 monster.', 'A powerful dragon from ancient times.', '[ Pendulum Effect ] Draw 1 card.'):
            self.assertIsNone(german_description(text))
            self.assertNotIn(text, german_effect('Unknown option', text))
        self.assertIsNone(german_description('Identical text', 'Identical text'))
        self.assertEqual(german_description('Beschwöre „The Phantom Knights“ als Spezialbeschwörung.'), 'Beschwöre „The Phantom Knights“ als Spezialbeschwörung.')
        self.assertEqual(german_description('Überspringe deine nächsten 2 Draw Phasen.'), 'Überspringe deine nächsten 2 Ziehphasen.')

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
