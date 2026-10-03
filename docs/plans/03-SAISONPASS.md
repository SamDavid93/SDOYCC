# SDOYCC: Saisonpass

Status: **Lokal umgesetzt und geprüft (03.10.2026)**. Konkrete Regeln, Rollen, Grenzen und offene externe Freigabe: [Abschlussstand](../FINAL_STATUS.md). Dieses Dokument hält auch frühere Produktannahmen und ausdrücklich spätere Erweiterungen fest.

## Ziel und erste Produktversion

Ein kostenloser Saisonpass belohnt nachvollziehbare Aktivitäten im Hub mit Erfahrungspunkten und freischaltbaren Stufen. Belohnungen können Sammelpunkte, Booster, konkrete Kartenvarianten oder kosmetische Sammlerabzeichen sein.

Erste Planannahme: eine aktive Saison, kostenlose Belohnungsspur, feste Regeln und klarer Zeitraum. Premium-Spur, Bezahlung, gekaufte Stufen, Ranglisten und nachträgliche Migration in Bezahlmodelle sind nicht Teil der ersten Version. Stufenzahl, Laufzeit, XP-Werte und Belohnungen werden vor Veröffentlichung im Admin-Bereich festgelegt; keine erfundenen Live-Werte aus dem heutigen Demo-Endpunkt übernehmen.

## Benutzeransicht

- Saisonname, echte verbleibende Zeit, aktuelles Level, gesammelte XP und Fortschritt bis zur nächsten Stufe.
- Belohnungsleiste mit Karten-/Booster-Vorschau und Zuständen „Gesperrt“, „Abholbereit“, „Abgeholt“.
- Tages-/Wochenaufgaben mit überprüfbarer Bedingung, Fortschritt und Rücksetzzeit.
- Belohnung abholen → dauerhafte Bestätigung mit tatsächlichen neuen Beständen und Links zu Sammlung/Pack-Tresor/Konto.
- „Alle abholbereiten Belohnungen abholen“ erst nach stabiler Einzelabholung; eindeutiges Ergebnis je Belohnung.
- Vergangene Saisons und Belege lesbar archivieren. Abholfrist getrennt vom Ende des XP-Sammelns anzeigen.
- Leerer Zustand: „Aktuell läuft keine Saison“; kein künstlicher Countdown.

Alle Zeitpunkte werden serverseitig in UTC gespeichert und im deutschen UI mit verständlicher Zeitzone dargestellt. Sommerzeitwechsel darf keinen doppelten Aufgabenreset verursachen.

## XP und Aufgaben

Nur serverseitig bestätigte Ereignisse erzeugen XP. Ein UI-Klick, das Öffnen einer Seite oder erneut gesendete Anfragen reichen nicht.

| Ereignis | Erste Regel |
| --- | --- |
| Erfolgreiche Boosteröffnung | Konfigurierbare XP je gespeicherter Öffnungs-ID, maximal einmal |
| Erste neue Kartenidentität einer Saison | Optional; anhand Erwerbsereignis und eigener Saison-Eindeutigkeit |
| Tages-/Wochenaufgabe | Bonus einmal je Aufgabe und Benutzer/Periode |
| Admin-Vergabe | Standardmäßig keine XP, damit Vergaben keine unbeabsichtigten Belohnungsketten auslösen |
| Tauschen | In erster Version keine XP, um Hin-und-Her-Tausch nicht zu belohnen |
| Anmeldung | Optional eine klar begrenzte Tagesaufgabe, keine XP pro Request |
| Twitch-Einlösung | Optional erst nach Entscheidung; nur anhand verifizierter Redemption-ID |

Keine Watchtime-Aufgabe, solange keine verlässliche, autorisierte Ereignisquelle vorhanden ist. Keine zusätzliche Twitch-Developer-Anwendung als Voraussetzung einführen.

Aufgabenbeispiele: „Öffne zwei Booster“ oder „Erhalte drei bisher nicht in dieser Saison erfasste Karten“. Jede Bedingung muss mit vorhandenen Ereignissen beweisbar sein. Eine Karte aus einem Tausch erneut zu erhalten darf „erstmals erhalten“ nicht endlos auslösen. Quest-Erfüllung und XP-Buchung sind idempotent.

Vor Veröffentlichung XP-Kurve, mögliche Tages-/Wochenlimits und Erreichbarkeit anhand eines Beispielverlaufs durchrechnen. Keine verpflichtenden Sammelpunkteausgaben erfinden, ohne deren Auswirkung auf den Fortschritt zu zeigen.

## Saisonlebenszyklus

Zustände: `draft → scheduled → active → ended → archived`. Beginn/Ende aus serverseitigen Zeitpunkten bestimmen; ein ausgefallener Scheduler darf keine XP nach Ende zulassen.

1. Entwurf: Name, Beschreibung, Zeitfenster, Levelschwellen, Aufgaben und konkrete Belohnungspakete konfigurieren.
2. Validierung: steigende XP-Schwellen, keine negativen Mengen, gültige aktive Karten-/Boosterreferenzen, klar definierte Aufgabenperioden.
3. Vorschau: Desktop/Mobilansicht und Beispiel-Fortschrittsverlauf, Gesamtsumme ausgebbarer Punkte/Karten sichtbar.
4. Veröffentlichung: Regelversion festhalten. Aktive Belohnungen und bereits zugesagter Fortschritt nicht still ändern.
5. Ende: keine neuen XP; Abholung bereits erreichter Belohnungen bis eigener `claim_until`-Frist möglich.
6. Archiv: Fortschritt und Belege bleiben erhalten. Neue Saison beginnt mit neuem Fortschritt; Inventar und Guthaben bleiben erhalten.

Korrekturen an einer aktiven Saison als versionierte, protokollierte Eingriffe behandeln. Erweiterungen/Verlängerungen benötigen eine sichtbare neue Frist. Bereits abgeholte Belohnungen nicht aus historischen Datensätzen löschen.

## Gemeinsame Belohnungslogik

- Der `GrantService` aus dem Admin-Plan führt die eigentliche Vergabe aus.
- Eindeutiger Anspruch pro `(user_id, season_id, reward_id)`; zusätzliche Client-Aktionskennung schützt Transportwiederholungen.
- Berechtigung, Saisonzeit, Stufe und bereits erfolgte Abholung unter Sperre prüfen.
- Anspruchsbeleg, Punkte-/Inventarbuchung und Benachrichtigung in derselben Transaktion.
- Bei Fehler keine „abgeholt“-Markierung ohne Belohnung und keine Belohnung ohne Anspruchsbeleg.
- Belohnungsvorlagen referenzieren konkrete Varianten/Mengen, keine beim späteren Abruf zufällig geänderten Katalogsuchen.
- Erste Version bevorzugt feste Belohnungen. Zufällige Sonderbelohnungen erst mit eigenem transparentem Pool und dauerhaft gespeichertem Ergebnis.
- Gesperrte Konten können während der Sperre keine Belohnungen abholen; Umgang mit Fristablauf während einer aufgehobenen Fehlsperre als nachvollziehbare Admin-Korrektur planen.

## Daten und Schnittstellen

| Modell | Zweck |
| --- | --- |
| `Season` / Regelversion | Status, Beginn/Ende, Abholfrist, Veröffentlichung und unveränderliche Regeln |
| `SeasonLevel` / `SeasonReward` | XP-Schwelle und konkretes Belohnungspaket |
| `SeasonProgress` | Gesamt-XP pro Benutzer/Saison; Level daraus ableiten oder konsistent aktualisieren |
| `SeasonXpEvent` | Quelle/Ereignis-ID, XP, Zeitpunkt, eindeutige Wiederholungsverhinderung |
| `SeasonQuest` / `QuestProgress` | Bedingung, Periode, Fortschritt und Bonusbeleg |
| `SeasonRewardClaim` | Benutzer, Belohnung, Zeitpunkt und Referenz zur tatsächlichen Vergabe |

Geplant: `GET /api/seasons/current`, `GET /api/seasons/{id}/me`, `GET .../quests`, `POST .../rewards/{rewardId}/claim`, `GET /api/seasons/me/history`; Admin-Endpunkte für Entwurf, Validierung, Vorschau und Veröffentlichung. Der alte `/battle-pass/me`-Prototyp wird umgestellt oder sauber abgelöst. Keine echten Fortschritte aus dem Demo-Level 18 ableiten.

## Ereignisse und Betrieb

Eine erfolgreiche Öffnung speichert ein fachliches Ereignis zusammen mit dem Ergebnis. XP-Verarbeitung ist wiederholbar. Werden XP synchron verbucht, darf ein Fehler nicht zu einer halben Boosteröffnung führen; bei asynchroner Verarbeitung einen transaktionalen Ereignisausgang und eindeutige Verarbeitung verwenden. Für die erste Version eine Variante auswählen und durchgehend anwenden.

Nach Ausfall offene Ereignisse nachverarbeiten; Ereigniszeitpunkt entscheidet über die passende Saison, nicht die spätere Verarbeitungszeit. Ein Ende-/Abholfrist-Rennen wird durch serverseitige Prüfung innerhalb der Buchung entschieden. Vorzusehen sind Betriebsansichten für unbearbeitete Ereignisse, fehlgeschlagene Belohnungen und XP-Abweichungen.

## Arbeitspakete und Abnahme

- [x] S1: Produktregeln, Zeitfenster, XP-Kurve und Belohnungsbudget konkretisieren.
- [x] S2: Saisonmodell und Admin-Entwurf/Validierung/Vorschau; Demo-Daten von echten Fortschritten trennen.
- [x] S3: Ereignisse, idempotente XP-Buchung und Aufgabenperioden.
- [x] S4: Fortschrittsansicht, Belohnungsleiste und gemeinsame Vergabe.
- [x] S5: Fristen, Archiv, Wiederanlauf und kontrollierte Korrekturen.
- [x] S6: Probesaison in isolierter Umgebung und erst danach gesonderte Freigabe.

Pflichttests: gleiche Öffnung mehrfach verarbeitet; parallele Abholung; Belohnung vor Freischaltung; Saisonwechsel exakt an der Grenze; Serverausfall und verspätete Ereignisse; Aufgabenreset bei Sommerzeitwechsel; gesperrtes Konto; Fehler bei einer mehrteiligen Belohnung; Abholung bis/ab Frist; aktiver Regelwechsel; Beibehaltung bestehender Kontostände und Karten beim Saisonwechsel. Fortschritt und Belohnungsbelege müssen nach Neuladen identisch bleiben.
