# Arbeitsplan: Twitch Trading Card Hub

Ziel: SamDavidOfficial – 1.000 Kanalpunkte → 100 Tradingpoints → Booster kaufen → kostenlos öffnen → Karten sammeln.

Aktueller Stand (03.10.2026): Admin A1–A7, Kartenhandel T1–T6 und kostenloser Saisonpass S1–S6 sind umgesetzt und geprüft. 138 Backend-Tests einschließlich Konfigurationsprüfungen, 57 lokale Browser-Prüfpunkte und Produktionsbuild erfolgreich. Die Website ist unter `https://samdavid93.github.io/SDOYCC/` veröffentlicht; das lokale Backend läuft im Produktionsmodus über einen vorübergehenden Cloudflare-Tunnel ohne eigene Domain. Der Betreiber bestätigt Kanalpunkte-Einlösung, Gutschrift, Packkauf und Öffnung im Live-Test. Offen bleiben unter anderem Queue-Abschluss, Neuregistrierung und Handel mit zweitem Konto sowie die erste bewusst konfigurierte Saison. Maßgebliche Übersicht: `docs/FINAL_STATUS.md`. Frühere offene Planungsstände weiter unten sind Entwicklungshistorie.

## Abgeschlossen

### Booster-Fortschritt und öffentliche Fundmeldungen (04.10.2026)

- [x] Sammelfortschritt pro Booster: unterschiedliche aktuell besessene Karten, Duplikate ausgeschlossen, gültiger Pool und Deck-Bonusmöglichkeiten berücksichtigt; gebündelte Datenbankabfrage statt einzelner Anfrage pro Kachel.
- [x] Anzahl, Prozent und Balken im Shop, in Details und im Tresor; Aktualisierung nach Öffnungen.
- [x] Öffnungen erzeugen ab Ultraselten eine transaktionale Chat-Warteschlange mit Karte, Seltenheit und Pack. Idempotente Öffnungen, zeitlich begrenzte Reservierung, Quittierung, Ablauf nach zehn Minuten.
- [x] Streamer.bot-C#-Aktion für den Broadcaster vorbereitet, gegen Version 1.0.7 kompiliert; vier isolierte Versand-/Wiederholungstests bestanden.
- [x] 149 Backend-Tests, vollständiger Browserlauf einschließlich Fortschrittsanzeige und Frontend-Build erfolgreich. Keine echten Twitch-Nachrichten oder Testbuchungen auf echten Konten ausgelöst.
- [ ] Timer-Aktion in Streamer.bot aktivieren und echte Chat-Zustellung prüfen. Anleitung: `docs/RARE_FINDS.md`.

### Veröffentlichung vorbereitet (03.10.2026)

- [x] Lokales Git-Repository auf `main` initialisiert und `origin` mit `https://github.com/SamDavid93/SDOYCC.git` verbunden. Quellcode nach GitHub-Anmeldung hochgeladen.
- [x] Git-Ausschlüsse für SQLite-WAL/SHM/Journal ergänzt; lokale `.env`, Datenbank, Cache und Sicherungen ausgeschlossen.
- [x] `configure-public.bat`: Vorschau und ausdrückliche Übernahme von sechs öffentlichen Einstellungen, atomarer Dateiaustausch und unveränderte Sicherung der bisherigen `.env`.
- [x] Sechs Konfigurationstests erfolgreich; Vorschau verändert die echte `.env` nicht. Lokaler Streamer.bot-Schlüssel in keiner für Git vorgesehenen Datei gefunden.
- [x] Pages-Workflow unterstützt Projekt-Unterpfad und `BENUTZER.github.io`; Cloud-Katalogimport für lokale SQLite-Installation standardmäßig deaktiviert.
- [x] Isolierter Produktionsbuild mit `/sdoycc/` erfolgreich; Asset-Pfade geprüft. Ergebnis: `artifacts/publishing-preparation.json`.
- [x] Konkrete Anleitung einschließlich Tunnel, Pages-Einstellungen und externer Abnahme: `docs/PUBLISHING.md`.
- [x] GitHub-Ziel bestätigt: `SamDavid93/SDOYCC`, Public. Vorgesehene Pages-Adresse `https://samdavid93.github.io/SDOYCC/`; Produktionsbuild mit exakt diesem Groß-/Kleinschreibungspfad erfolgreich.
- [x] GitHub-Geräteanmeldung als `SamDavid93` abgeschlossen; Quellcode hochgeladen und Pages mit GitHub Actions sowie HTTPS aktiviert. Website-Bereitstellung benötigt weiterhin `VITE_API_BASE_URL`.
- [x] GitHub-Prüflauf `37152987100` erfolgreich: 138 Backend-Tests einschließlich sechs Konfigurationstests sowie Frontend-Build. Deployment `37152987041` wegen fehlender API-Adresse gestoppt.
- [x] Betreiberwahl „ohne Domain“ umgesetzt: Cloudflare Quick Tunnel eingerichtet, lokale Konfiguration mit Sicherung auf Produktionsmodus umgestellt, Demo deaktiviert und Pages veröffentlicht.
- [x] `start-public-test.bat` und `stop-public-test.bat` für den Betrieb ergänzt. Erststart und Wiederverwendung desselben Tunnels erfolgreich, Health und CORS geprüft; lokaler Schlüssel und Bestände nicht verändert.
- [x] Betreiber bestätigt am 03.10.2026 den echten Ablauf: Kanalpunkte einlösen, Gutschrift, Packs erwerben, öffnen und Karten gutgeschrieben bekommen.
- [ ] Genauen Guthabenunterschied und automatischen Reward-Queue-Abschluss gesondert bestätigen; Neuregistrierung mit zweitem Konto, Handel und erneuten Login öffentlich abnehmen; erste Saison bewusst konfigurieren. Der Tunnel bleibt ein vorübergehender Testzugang.

- [x] Atomare Käufe/Öffnungen, Buchungsjournal, Schutz vor doppelten Buchungen.
- [x] Echte Sammlung/Kontodaten, Katalogsuche und Import mit stabilen IDs.
- [x] Passwort-Login/Logout, sichere Passwort-Hashes, Sitzungen und Anmeldelimits.
- [x] Authentifizierte Streamer.bot-Brücke mit Zuordnung über die tatsächliche Twitch-ID.
- [x] Wechsel von Whispers auf öffentlichen Registrierungslink mit !confirm-Bestätigung.
- [x] Browser erstellt getrennten geheimen Schlüssel und Chat-Code; Passwortsetzung erst nach Bestätigung durch dasselbe Twitch-Konto.
- [x] Fremde Twitch-Konten, fremde Browser, abgelaufene Codes, Wiederverwendung und alte private Links werden abgewiesen.
- [x] Registrierung für das Streamer-Konto selbst möglich; kein separater Bot-Absender erforderlich.
- [x] Streamer.bot-Code verwendet ausschließlich öffentliche Chat-Antworten über den Broadcaster; kein SendWhisper-Aufruf.
- [x] Setup-Code und Anleitung aktualisiert; !register und !confirm verwenden dieselbe Registrierungsaktion.
- [x] Frontend mit Codeanzeige, automatischer Bestätigungsprüfung und Wiederaufnahme nach Neuladen.
- [x] Neue Tabelle nach Datenbanksicherung angelegt, lokale API neu gestartet; registration_mode=chat_confirmation bestätigt.

## Früherer Schritt: Streamer.bot-Code übernehmen und live testen

- [x] Gutschrift auf initiale Einlösung umgestellt: 100 Tradingpoints sofort, auch bei Status unfulfilled.
- [x] C# erfüllt den Twitch-Queue-Eintrag erst nach erfolgreicher Backend-Buchung; Updated-Ereignisse und Wiederholungen buchen nicht doppelt.
- [x] 33 Backend-Tests und 8 C#-Ablauftests erfolgreich. Fehler zwischen Buchung und Twitch-Abschluss werden getrennt gemeldet.
- [ ] Neuen Code in die Kanalpunkte-C#-Subaktion übernehmen und automatischen Abschluss live prüfen. Streamer.bot benötigt dafür eine selbst erstellte Belohnung; alternativ Warteschlange überspringen in Twitch aktivieren.

- [ ] Aktuellen TradingHub.cs-Code in TCG Register einsetzen und Save and Compile ausführen; bei bereits vorhandener Reward-Aktion auch dort ersetzen.
- [ ] !confirm unter Commands anlegen: Starts With, Twitch Message; zweiter Command-Triggered-Trigger an TCG Register.
- [ ] Chat-Trigger von TCG Setup entfernen; Setup nur manuell ausführen. Bestehender Verbindungsschlüssel bleibt gültig.
- [ ] !register → öffentlicher Link → Code erstellen → !confirm CODE → Passwort setzen → abmelden/anmelden live testen.
- [x] Reward-ID 49f31d1c-3709-43a7-9ccf-1248b126b05b in der lokalen .env konfiguriert. Backend neu gestartet; authentifizierte Statusabfrage bestätigt reward_configured=true, 1.000 Kanalpunkte = 100 Tradingpoints.
- [ ] Kanalpunkte-Aktion mit beiden Reward-Triggern einrichten und auf diese Belohnung begrenzen.
- Diagnose der fehlenden Gutschrift: gespeicherte Streamer.bot-Konfiguration enthält nur TCG Setup und TCG Register, keinen Trigger für die Reward-ID. Backend hat noch keine TwitchRedemption-Buchung. Belohnung 100 TCG DIAMONDS kostet laut lokaler Streamer.bot-Konfiguration korrekt 1.000 Kanalpunkte. Rückmeldungen für Gutschrift und offene Erfüllung im C#-Code ergänzt.
- [ ] Echte Einlösung → genau 100 Tradingpoints → Kauf → kostenlose Öffnung prüfen.

## Später: Zugriff für Zuschauer

- [ ] GitHub Pages und öffentliche HTTPS-Adresse für das lokale Backend einrichten.
- [ ] FRONTEND_URL, CORS_ORIGINS und VITE_API_BASE_URL konfigurieren.
- [ ] Produktionsmodus aktivieren und von einem anderen Gerät testen.

Localhost-Links funktionieren derzeit nur auf dem Server-PC. Ein öffentlicher Chat-Link macht den lokalen Server noch nicht von außen erreichbar. Domain, Tunnel und GitHub-Pages-Adresse fehlen weiterhin.

## Prüfstand der öffentlichen Registrierung

- 31 Backend-Tests erfolgreich am 29.09.2026: unter anderem falsches Twitch-Konto, falscher Kanal, fehlender Bridge-Schlüssel, Browserbindung, Ablauf, Einmaligkeit, parallele Registrierung, gesperrtes Konto, Bestands-/Guthabenerhalt und Registrierung des Streamer-Kontos.
- TypeScript-/Vite-Produktionsbuild erfolgreich.
- Browserdurchlauf erfolgreich: öffentlicher Link, Codeanzeige, Neuladen, simulierte Chat-Bestätigung, Passwortsetzung, Login/Logout, 100 Tradingpoints, Kauf, kostenlose Öffnung und Sammlung. Keine JavaScript-Fehler.
- TradingHub.cs und SetupTradingHub.cs gegen die lokale Streamer.bot-1.0.7-Schnittstelle kompiliert.
- Sicherung vor neuer Tabelle: artifacts/db-backups/cardcluster-20260929T111821487314Z.db.
- Vorher-/Nachher-Vergleich: Kontostände, Inventar und Booster-Bestände unverändert; SQLite-Integrität und Fremdschlüssel geprüft.
- Backend läuft mit neuem Ablauf. Keine echten Chat-Nachrichten durch den Assistenten gesendet; Streamer.bot enthält bis zum manuellen Einfügen weiterhin seine eigene Codekopie. PostgreSQL nicht live geprüft.

## Entscheidungen und Grenzen

- Keine eigene Twitch-Developer-App. Streamer.bot übernimmt die Twitch-Verbindung.
- Öffentliche Links enthalten keine geheimen Tokens. Nur selbst im Browser angeforderte Codes bestätigen.
- Bestätigung gilt standardmäßig 30 Minuten; bestehende Passwörter können damit nicht zurückgesetzt werden.
- Browser-Schlüssel und Code sind in der Datenbank nur als Hash gespeichert. Alte Invite-Tabelle bleibt ohne aktive Nutzung erhalten.
- Das Bot-Konto hat keine Telefonnummer; der Whisper-Ansatz wurde auf Wunsch ersetzt. Die früheren 401-/Abmeldefehler betrafen den Whisper-Aufruf.
- Neue Konten starten bei 0. credits/diamonds/Tradingpoints bezeichnen dasselbe Guthaben.
- Passwort-Wiederherstellung, verpasste Reward-Ereignisse nachladen, Handel und Battle Pass bleiben Folgeaufgaben.


## Kartenkatalog und Booster – 29.09.2026

- [x] Gemeinsame Navigation: Karte suchen → passende Booster → enthaltener Kartenpool.
- [x] Kartendetails zeigen ausschließlich aktive Booster, deren tatsächlicher Pool die Karte enthält; Set-Ausgaben verlinken auf ihre Sets.
- [x] Booster-Shop als Cover-Kacheln mit Preis, Bestand, Kauf und kostenloser Öffnung; Suche nach Name/Set/Kürzel und Bestandsfilter.
- [x] Startseite zeigt drei Booster mit bevorzugt vorhandenem Cover. Fehlende/defekte Cover werden ausdrücklich gekennzeichnet.
- [x] Booster-Details mit Cover, durchsuchbarem und paginiertem Pool, Ziehungswahrscheinlichkeit und Links zu Karten/Set.
- [x] Einheitlicher Preis von 100 Tradingpoints zentral im Backend abgesichert, auch für alte abweichende Produktpreise.
- [x] 35 Backend-Tests und Produktionsbuild erfolgreich. Browserprüfung mit isolierter Datenbank: Navigation, Cover/Fehlerfall, Bestandsfilter, Kauf, Öffnung, Registrierung und Login; keine JavaScript-Fehler.
- [x] Lokale Darstellung mit echten Cover-URLs zusätzlich auf Desktop und 390px geprüft; kein horizontaler Überlauf. Screenshots in artifacts/booster-*.png und artifacts/overview-booster-covers.png.

Bilddaten: 899 der 1.021 Booster haben eine hinterlegte Cover-URL; für 122 fehlt ein Bild in den vorhandenen Katalogdaten. Es wird kein fremdes Booster-Cover als Ersatz verwendet. Bilder bleiben externe URLs. Tests tätigen Käufe ausschließlich in isolierten Testdatenbanken.


## Sichtbare Kaufbestätigung – 29.09.2026

- [x] Gemeinsame, dauerhaft sichtbare Kaufbestätigung für Shop, Booster- und Setdetails: Booster-Name, bezahlte Punkte, bestätigter Kontostand und Pack-Bestand.
- [x] Kaufbutton zeigt während der Anfrage „Wird gekauft …“. Bestätigung erst nach erfolgreicher Backend-Antwort; manuell schließbar.
- [x] Aus Shop/Boosterdetails direkt kostenlos öffnen; Setdetails verlinken zum gekauften Booster. Gezogene Karten werden in den sichtbaren Bereich gescrollt.
- [x] Produktionsbuild und Browserdurchlauf erfolgreich: Kaufbestätigung, abgelehnter Kauf ohne Erfolgsmeldung, Handyansicht, Öffnen aus Bestätigung und Schließen auf Detailseite. Keine JavaScript-Fehler, keine Käufe in der echten Datenbank.


## Pack-Tresor und Opening-Show – 30.09.2026

- [x] Eigene Seite `/my-packs`: sichtbare Booster-Stapel, Stückzahlen, Suchfunktion, Mengenübersicht und direktes Öffnen.
- [x] Durchgängige Navigation Shop → Meine Packs → Sammlung, Bestandsanzeige in Kopfzeile/Seitenleiste und Zugang aus Kaufbestätigung.
- [x] Neu gestaltete Startseite mit Cover-Inszenierung, hervorgehobenem Pack-Tresor und drei klaren Einstiegsmöglichkeiten.
- [x] Gemeinsame Opening-Show für Shop, Kaufbestätigung, Boosterdetails und Pack-Tresor: Energieaufbau, Siegel-Aufriss, Partikel, Karten-Flip, Seltenheitsfarben und Spotlight.
- [x] Optional synthetisierte Soundeffekte, native Dialog-Fokusführung, Tastaturbedienung, Escape, Überspringen und reduzierte Bewegung.
- [x] Serverseitige Ziehung nur einmal; Präsentation ändert weder Ziehung noch Guthaben. Schließen erhält die bereits gespeicherten Karten.
- [x] Produktionsbuild und erweiterter Browserdurchlauf erfolgreich: Kauf, Pack-Tresor, Leerzustand, animierte Enthüllung, Seltenheits-Spotlight, Fehlerfall ohne Bestandsverlust, Überspringen, reduzierte Bewegung und Erhalt der Karten nach Schließen/Neuladen. Keine JavaScript-Fehler.
- [x] 20 zusätzliche Ansichten mit bestehenden lokalen Daten bei 320, 390, 768 und 1440 Pixeln überprüft: kein horizontaler Überlauf. Testkäufe und Öffnungen ausschließlich in isolierter Datenbank.

Screenshots: `artifacts/hub-experience-desktop.png`, `artifacts/hub-experience-mobile.png`, `artifacts/pack-vault-desktop.png`, `artifacts/pack-vault-mobile.png`, `artifacts/opening-reveal-desktop.png`, `artifacts/opening-reveal-mobile.png`. Opening-/Tresor-Screenshots stammen aus Testdaten; lokale Kontostände und Sammlungen wurden nicht für die Präsentation verändert.


## Deutsche Sammlung und Ladeverhalten – 30.09.2026

- [x] Animierte Kartenrückseite während des Bildabrufs, weiches Einblenden, eindeutiger Fehlerzustand und reduzierte Bewegung.
- [x] Sammlung mit sechs Desktop-Spalten, responsiver Darstellung, Mengenübersicht, 36 Karten pro Seite und kombinierbaren Eigenschaftsfiltern.
- [x] Deutsche Oberflächentexte, Seltenheits- und Eigenschaftsbezeichnungen; Guthabenanzeige als Sammelpunkte.
- [x] Additiver Import deutscher Namen/Texte für 11.774 bestehende Karten; Benutzer, Inventar, Booster-Bestand und Buchungen erhalten.
- [x] Deutsche offizielle Vorschauen mit unverändertem Wasserzeichen, lokalem Bildcache und begrenzten gleichzeitigen Quellabrufen.
- [x] Farbige Seltenheitsabzeichen am oberen rechten Bildrand; Öffnungshistorie verwendet die tatsächlich gezogene Seltenheit.
- [x] Sitzungsgetrennter kurzer API-Cache mit Anfragebündelung und Invalidierung nach Aktionen; Gzip, Datenbankindizes und Suchverzögerung.
- [x] 41 Backend-Tests und Browserdurchlauf: sechs Spalten, kombinierte Filter, deutsche Namen, Lade-Rückseite, Bildübergang sowie bestehende Kauf-/Registrierungs-/Öffnungsabläufe.

Quelleinschränkung: 2.816 Karten fehlen im deutschen Feed. Set-/Kartengruppennamen bleiben in Quellschreibweise. Offizielle deutsche Vorschauen sind klein und mit SAMPLE markiert; nicht mit hochauflösenden Vollscans gleichzusetzen. Fehlende Bilder werden klar gekennzeichnet. Vollständige deutsche Daten- und Bildabdeckung bleibt offen.

Abschlussprüfung: Produktionsbuild und erweiterter Browserdurchlauf erfolgreich, einschließlich Anfragebündelung, sechs Spalten, Filterkombination und Ladeübergang. Nach der abschließenden Optimierung der Katalogabfrage zusätzlich alle neun Katalog-/Sammlungstests erfolgreich. Backend neu gestartet und API geprüft. Vergleich mit SQLite-Sicherung: Konten, Inventar, Booster-Bestand und Buchungsjournal unverändert.

Lokale Messung: Booster-JSON 281.603 Byte → 27.909 Byte mit Gzip (90,1 % weniger Übertragung). Sammlung ca. 9,5 ms, zwischengespeichertes Bild ca. 10,7 ms, Katalogseite ca. 105 ms (Mediane wiederholter lokaler HTTP-Anfragen; kein Versprechen für öffentliches Hosting). Details: `artifacts/german-collection-check.json`. Ansichten: `artifacts/collection-german-desktop.png`, `artifacts/collection-loading-desktop.png`, `artifacts/inventory-mobile.png`.


## Verfügbare Bilder und englische Ersatzdaten – 30.09.2026

- [x] Fehlerhafte Ersatzanzeige „Karte <Nummer>“ entfernt. Fehlende/leere deutsche Namen und Platzhalter „Karte 123“/„Karte [123]“ fallen auf den vorhandenen Originalnamen zurück.
- [x] YGOResources als zusätzliche deutsche Bildquelle anhand des offiziellen Projekt-Manifests eingebunden. 13.841 unserer Karten haben einen deutschen Indexeintrag; zwölf neue Abrufe erfolgreich getestet. Kein vollständiger Bilderdownload.
- [x] 2.362 deutsche Namen aus dem zusätzlichen Namensindex ergänzt: insgesamt 14.136. Bestehende deutsche Texte erhalten (11.774).
- [x] Englische Originaltexte für alle 14.590 Karten ergänzt; additive Schema-Erweiterung `description_en`. Fehlender oder aus Platzhaltern bestehender deutscher Text fällt auf Englisch zurück und wird in den Details entsprechend gekennzeichnet.
- [x] Automatischer Bildwechsel: deutsche CDN-Quelle → offizielle deutsche Vorschau → lokal zwischengespeichertes YGOPRODeck-Original. Englisches Ersatzbild sichtbar als „Originalbild“ gekennzeichnet; bei komplettem Ausfall eindeutige Rückseite, keine Wiederholungsschleife.
- [x] Deutsche Bildsuche vom Vorhandensein eines deutschen Namens entkoppelt. Bildquellen auf erlaubte Hosts begrenzt; Originalbilder nur anhand gespeicherter Anbieter-URLs.
- [x] 49 Backend-Tests, Produktionsbuild und Browserdurchlauf erfolgreich, einschließlich Wechsel auf Originalbilder und Ausfall beider Bildquellen. Keine JavaScript-Fehler.
- [x] Backend neu gestartet; deutsche und englische Bildendpunkte live geprüft. Originalbild visuell als englische Karte bestätigt. Keine Platzhalternamen mehr in der effektiven Anzeige des aktuellen Katalogs.
- [x] Gegen Sicherung geprüft: Benutzer, Kartenbesitz, Booster-Bestand und Guthabenbuchungen unverändert.

Deutsche Vorschauen behalten ihre Quellauflösung und SAMPLE-Kennzeichnung. Indexabdeckung bedeutet keine Garantie, dass jede Quelle jederzeit erreichbar ist. Bericht: `artifacts/image-fallback-check.json`; Import-/Aktualisierungsbefehl siehe README.


## SDOYCC, kleine Booster und dokumentierte Ausbaustufen – 30.09.2026

Vom Nutzer ausdrücklich geklärt: Booster-Begrenzung und Umbenennung jetzt umsetzen; Admin-Bereich, Handel und Saisonpass ausschließlich planen.

- [x] Gemeinsame Regel: effektive Kartenanzahl = Minimum aus konfigurierter Anzahl und unterschiedlichen ziehbaren Karten-IDs. Positive Gewichte erforderlich; Nullgewichte und zusätzliche Raritäten derselben Identität vergrößern die Grenze nicht.
- [x] Anzeige in Shop/Details/Pack-Tresor und tatsächliche Öffnung nutzen dieselbe Grenze. Ungültige Pools werden vor Kauf/Bestandsverbrauch abgewiesen. Gewichtete Duplikate bleiben möglich; kein Wechsel zu einer Ziehung ohne Zurücklegen.
- [x] 480 bestehende Booster mit weniger als fünf Kartenarten profitieren von der Begrenzung. Beispiel: „2020 Tin of Lost Memories Booster“ zeigt und liefert höchstens drei Karten.
- [x] Marke: SDOYCC – SamDavidOfficial's Yu-Gi-Oh Card Collector. Navigation, Anmeldung, Browser-/API-Titel, Opening-Show, Kartenrückseite, Startdateien, Paketnamen und Dokumentation angepasst.
- [x] Standard-Booster heißt SDOYCC Origins. Wiederholbare Namensmigration erhält Pack-ID, Kartenpool und Besitz. Externer Anbieteradapter behält seinen tatsächlichen Drittanbieternamen; historische Sicherungspfade bleiben korrekt.
- [x] Lokale SQLite-Datei mit gestopptem Backend und vorheriger Sicherung auf sdoycc.db umbenannt, .env/Beispiele/Standardkonfiguration angepasst, Backend erfolgreich neu gestartet.
- [x] Vorher-/Nachher-Vergleich: Nutzer, Inventar, Booster-Bestand, Guthabenjournal, Karten und Öffnungshistorie unverändert.
- [x] Backend-Gesamtlauf mit 53 Tests erfolgreich; danach ergänzter Namensmigrationstest plus bestehender Migrationstest ebenfalls erfolgreich (54 unterschiedliche Tests). Produktionsbuild und Browserdurchlauf erfolgreich, einschließlich SDOYCC-Titeln und Öffnung eines Drei-Karten-Pools. Keine JavaScript-Fehler. Eine zuerst im Test verbliebene SQLite-Verbindung wurde explizit geschlossen; wiederholter Browserdurchlauf beendet auch die Testbereinigung fehlerfrei.
- [x] Vollständige, verlinkte Planung erstellt: docs/plans/00-ROADMAP.md, 01-ADMIN.md, 02-HANDEL.md, 03-SAISONPASS.md.

**Nächster geplanter Ausbau:** Admin-Rechte/Leseansichten und anschließend Variantenbestand/Vergabedienst. Noch keine Implementierungsfreigabe für die drei geplanten Bereiche. Der bestehende Handels- und Saisonpass-Prototyp wurde nicht ausgebaut. Sicherung der Umbenennung ist in artifacts/rename-backup-path.txt referenziert.


## Structure Decks und Original-Bildmarke – 30.09.2026

Nutzerentscheidungen: 600 Punkte je Structure Deck, maximal drei Käufe je Deck und Konto, echte Decklisten einschließlich Mehrfachexemplaren. Logo und Banner aus den bereitgestellten PNG-Dateien einbauen.

- [x] Serverseitige Produktklassifizierung, feste Preise und dauerhafte Kaufzähler. Mengen- und Parallelkäufe geprüft; idempotente Wiederholungen bleiben ohne erneute Abbuchung möglich.
- [x] Separates Datenmodell für feste Decklisten. Öffnung vergibt sämtliche Stückzahlen ohne Zufallsziehung; Bestand und Historie erfassen alle Exemplare.
- [x] Lokales, versioniertes Manifest für 57 Decks, ergänzt um zehn bislang fehlende Token-Karten. Import wiederholbar, Quellen dokumentiert; bestehende Definitionen werden bei Abweichungen nicht automatisch überschrieben.
- [x] Shop, Setdetails, Deckdetails und Kaufbestätigung zeigen 600 Punkte, Stückzahlen, verbleibende Käufe und erreichtes Limit. Vorhandene Decks lassen sich nach dem dritten Kauf weiterhin öffnen.
- [x] Blue-Eyes White Destiny und Spirit Charmers: Bonuskarten ergänzt; Fortsetzung und Darstellungsgrenzen siehe unten.
- [x] Original-Logo in Navigation, Anmeldung und Registrierung; Original-Banner auf der Übersicht, proportional und ohne Beschnitt. Bilddateien lokal eingebunden.
- [x] Übersicht zeigt höchstens sechs Karten der letzten Öffnung und verlinkt das vollständige Ergebnis; ein 42-Karten-Deck verlängert damit nicht die komplette Startseite.
- [x] 62 Backend-Tests erfolgreich; Produktionsbuild erfolgreich. Browserdurchlauf mit Kaufgrenze, 42-Karten-Öffnung, Bildern und Mobilansicht erfolgreich; keine JavaScript-Fehler.
- [x] SQLite-Sicherung vor Migration; Backend wieder auf Port 8002 erreichbar. Vorher-/Nachher-Vergleich bestätigt unveränderte Konten, Guthabenjournal, Kartenbesitz, Pack-Bestände und Öffnungshistorie. Keine Testkäufe in der echten Datenbank.

Berichte: `artifacts/structure-release-check.json`, `structure-import.json`, `structure-migration.json`; Ansichten: `artifacts/sdoycc-banner-desktop.png`, `sdoycc-banner-mobile.png`, `sdoycc-login-brand.png`, `structure-deck-limit.png`. Admin, Handel und Saisonpass bleiben ausschließlich geplant.


## Fortsetzung: Bonuskarten – 30.09.2026

- [x] Nach „fahre weiter fort“ zufällige Bonusauswahl als Annahme übernommen und kommuniziert. Admin, Handel und Saisonpass bleiben weiterhin nur geplant.
- [x] Eigenes Modell für Bonusplätze und Kandidaten. 50 + 1 Karten bei Blue-Eyes; 41 + 1 Spielmarke + 1 Bonus bei Spirit Charmers. Die drei Blue-Eyes-Exemplare bleiben erhalten.
- [x] Gleichverteilte Hub-Chancen sichtbar als solche ausgewiesen. Garantierter Inhalt und Bonusauswahl getrennt. Bonuskarten werden auch über die Kartensuche gefunden.
- [x] Kein erneutes Auswürfeln bei Wiederholung derselben Öffnungsanfrage. Leere Bonusplätze sperren Kauf und Öffnung, ohne Guthaben oder Bestand zu verändern.
- [x] 40 reine Inhaltsziehungen und Importprüfung an einer isolierten Kopie des echten Katalogs erfolgreich; Wiederholungsimport erkennt alle 59 Definitionen unverändert.
- [x] Browserprüfung: mobile Bonusauswahl, garantierter Inhalt, genau eine Bonuskarte unter 43 ausgegebenen Karten und bestehende Kauf-/Registrierungsabläufe. Keine JavaScript-Fehler.
- [x] Alle 66 Backend-Tests, Produktionsbuild und Browserprüfung erfolgreich. Übernahme nach Sicherung, Backend neu gestartet; laufende API zeigt 51 beziehungsweise 43 Karten. Konten, Guthaben, Inventar, Pack-Bestände und Öffnungen unverändert; alle 57 bisherigen Deckdefinitionen ebenfalls unverändert. Bericht: `artifacts/bonus-release-check.json`.

Bewusst sichtbare Grenzen: keine erfundene Quarter-Century-Upgradequote; alternative Bilder und Spielmarken-Motive werden weiterhin je Kartenidentität zusammengefasst. Details in `docs/STRUCTURE_DECKS.md`. Die beiden Produkte sind mengenmäßig vollständig; die physische Motiv-/Foil-Verteilung wird nicht vollständig simuliert.


## Fortsetzung: Admin A1 – 30.09.2026

Die Anweisung „fahre mit dem geplanten ausbau weiter fort“ setzt die Umsetzung der dokumentierten Ausbaureihenfolge fort. Der frühere Status „nur planen“ ist damit für den fortgesetzten Ausbau überholt.

- [x] Zentrale serverseitige Rechteprüfung für lesende Admin-Endpunkte. Normale/gesperrte Konten und öffentliche Demo-Sitzungen bleiben ausgeschlossen; Rollen werden je Anfrage geprüft.
- [x] Lokale Ersteinrichtung über die numerische Twitch-ID eines aktiven, registrierten Kontos. Vorschau mit Rollback; dauerhafte Rollenänderung und Auditbeleg in einer Transaktion. Parallelaufrufe und erneute Einrichtung abgesichert.
- [x] Community-Übersicht, Kontosuche, Rollen-/Statusfilter und stabile Kontodetails. Guthabenjournal, Kartenmengen und ungeöffnete Packs separat paginiert. Keine Passwörter, Sitzungsschlüssel oder internen Buchungsreferenzen in Antworten.
- [x] Deutsche Verwaltungsoberfläche, Navigation nur für berechtigte Rollen, mobile Darstellung und Tastaturfokus. Bestandsgrenze nach Kartenidentität ausdrücklich sichtbar.
- [x] 72 Backend-Tests erfolgreich; Produktionsbuild erfolgreich. Browserprüfung mit normalem Konto, echtem Testsitzungstoken, Admin-Suche, Beständen, Entzug der Rolle und mobilen Ansichten erfolgreich. Keine JavaScript-Fehler. Alle Testbuchungen ausschließlich in isolierten Datenbanken.
- [x] Nutzer hat „samdavidofficial als Hauptadministrator einrichten“ bestätigt. Nach SQLite-Sicherung und geprüfter Vorschau Konto 2 / Twitch-ID 547965507 zum Hauptadministrator gemacht; ein lokaler Auditbeleg gespeichert.
- [x] Backend neu gestartet. Live-Prüfung: erreichbar; anonyme und Demo-Admin-Anfragen abgewiesen. Guthabenjournal, Karten, Packs, Deckdefinitionen, Kaufzähler und Öffnungen unverändert. Kontodaten abgesehen von der ausdrücklich freigegebenen Rollenänderung unverändert.
- [x] Bedienung und Einrichtung in `docs/ADMIN.md`; Roadmap und Admin-Plan aktualisiert.

Berichte: `artifacts/admin-release-check.json`, `admin-migration.json`, `admin-tests.log`, `admin-browser.log`. Ansichten: `artifacts/admin-overview-desktop.png`, `admin-overview-mobile.png`, `admin-account-mobile.png`.

Nächster Abschnitt A2: allgemeines Audit, Sitzungswiderruf und Kontoaktionen mit erneuter Passwortbestätigung und Schutz des letzten Hauptadministrators. A3–A5 führen danach Variantenbestand und Vergaben ein; Handel und Saisonpass bleiben die nachgelagerten Phasen.


## Fortsetzung: Admin A2 und Anmelde-Zurücksetzung – 30.09.2026

Nutzerentscheidung: „Nur Anmeldung: Passwort löschen und erneute Twitch-Bestätigung verlangen“. Keine Spielstand-Zurücksetzung implementieren.

- [x] Sichtbarer Sidebar-Einstieg **Admin-Menü** für Verwaltungsrollen; normale Konten sehen ihn nicht. Direkter Zugriff bleibt serverseitig geschützt. Mobile Navigation im Browser geprüft.
- [x] Kontoaktionen im Panel: Anmeldung zurücksetzen, alle Sitzungen beenden, Konto sperren/entsperren. Hauptadministratoren dürfen zusätzlich Rollen verwalten.
- [x] Bestätigungsdialog mit Folgen, exaktem Zielbenutzernamen, Begründung und eigenem Administrator-Passwort. Support bleibt lesend; normale Admins bearbeiten ausschließlich normale Twitch-Nutzer.
- [x] Passwort-Reset widerruft Sitzungen und bisherige Registrierungsbestätigungen. Neuer Browser-Schlüssel und erneute Twitch-Chat-Bestätigung erforderlich. Punkte, Karten, Packs, Kaufzähler, Historie, Twitch-ID und Rolle bleiben erhalten.
- [x] Auditbeleg und Änderung atomar. Pflicht-Aktionskennung samt Nutzdaten-Fingerabdruck verhindert doppelte Ausführung; abweichende Wiederverwendung liefert 409. Ein verspätet wiederholter Reset löscht kein inzwischen neu gesetztes Passwort.
- [x] Gemeinsame Sperre serialisiert konkurrierende Admin-Aktionen. Rechte werden unter Sperre erneut geprüft; kein Selbstaufstieg, kein Zurücksetzen/Sperren des eigenen Verwaltungskontos, kein Entfernen des letzten nutzbaren Hauptadministrators.
- [x] Login und Bestandsaktionen prüfen nach dem Kontoschreiblock erneut Passwortstand beziehungsweise Sitzung. Eine gleichzeitig wartende Anmeldung oder Kaufanfrage kann einen Reset nicht umgehen.
- [x] Änderungsprotokoll auf der Admin-Übersicht und je Konto: Akteur, Ziel, Grund, Zeit und Zustandsvergleich; filterbar und paginiert. Keine Passwort- oder Sitzungsgeheimnisse im Audit.
- [x] 82 Backend-Tests erfolgreich. Zusätzliche Prüfungen für parallele Resets, parallele Sperren zweier Hauptadministratoren, vollständigen Rollback, Wiederherstellung per Twitch und Bestandswahrung. Produktionsbuild erfolgreich.
- [x] Isolierter Browserdurchlauf einschließlich Reset-Dialog, Abbruch, erfolgreicher Zurücksetzung, Sperren/Entsperren, Audit, Sidebar und Mobilansicht erfolgreich. Keine JavaScript-Fehler.
- [x] Vor Übernahme SQLite gesichert, additive Tabelle für Admin-Serialisierung angelegt, Backend neu gestartet. Live-Konten, Passwörter, Sitzungen, Registrierungscodes, Guthaben, Karten, Packs und Historie unverändert. Kein echtes Konto zurückgesetzt; anonyme und Demo-Schreibzugriffe abgewiesen.
- [x] README, Admin-Anleitung und Roadmap aktualisiert.

Berichte: `artifacts/admin-a2-tests.log`, `admin-a2-browser.log`, `admin-a2-migration.json`, `admin-a2-release-check.json`. Ansichten: `artifacts/admin-reset-confirmation-mobile.png`, `admin-audit-desktop.png`.

Grenzen dieser Stufe: Sitzungswiderruf für alle Sitzungen eines Kontos; Kontosperren bleiben bis zur manuellen Entsperrung bestehen. Einzelne Sitzungen und automatische Sperrabläufe sind spätere Ergänzungen. Nächste geplante Grundlage ist A3: Variantenbestand und Inventarjournal; danach gemeinsame Vergaben und Vergabeoberfläche (A4/A5), anschließend Handel und Saisonpass.


## Fortsetzung: Variantenbestand und Inventarjournal (A3) – 30.09.2026

- [x] Stabile Kartenvarianten nach Kartenidentität, Herkunftspack und normalisierter Seltenheit; ungeklärter Altbestand getrennt. Optionale Druckausgaben-ID vorbereitet, ohne beliebige physische Ausgabe zu erfinden.
- [x] Mengen je Konto/Variante/Bindungsstatus, reservierte Menge mit Datenbankgrenzen. Kompatible Kartensumme bleibt parallel bestehen.
- [x] Gemeinsame Kartenbuchung mit Journal, eindeutiger Bewegungsreferenz, Wiederholungs-/Konfliktprüfung und Schutz reservierter beziehungsweise nicht vorhandener Exemplare. Abweichungen zwischen Karten- und Variantensumme werden abgewiesen.
- [x] Normale Booster und Structure Decks buchen alle Exemplare einschließlich Duplikaten und Bonuskarten atomar in Gesamtbestand, Varianten und Journal. Gleiche Öffnungskennung erzeugt keine zweite Bewegung.
- [x] Konservative Übernahme: Nur bei exakter Übereinstimmung von Bestand und vollständiger Öffnungshistorie nach Pack/Seltenheit rekonstruieren. Sonst gesamte betreffende Altmenge als unbekannte Ausgabe erhalten. Keine pauschale Zuordnung zur höchsten Seltenheit.
- [x] Sammlung zeigt aufklappbare Varianten mit Mengen und Herkunft; Seltenheitsfilter verwenden den Variantenbesitz. Ungeklärte Ausgaben sind mit Fragezeichen und eigenem Filter erkennbar. Sechs Desktop-Spalten bleiben erhalten.
- [x] Persönliches Kartenjournal sowie Varianten und Kartenjournal in den Admin-Kontodetails; paginiert und serverseitig zugriffsgeschützt. Sammlungsabfragen lesen keine vollständige Öffnungshistorie mehr.
- [x] Prüfung einer isolierten Kopie der echten Datenbank: 70 rekonstruierte und 37 ungeklärte Exemplare, alle 107 erhalten. Jede Konto-/Kartenmenge und alle Journalsummen stimmen überein. Zweiter Lauf ohne neue Buchungen; vorhandene Besitz-, Konto- und Guthabendaten unverändert.
- [x] 88 Backend-Tests erfolgreich, einschließlich Reservierungsschutz, Mengenabweichungen, Wiederholung, Rollback und konservativer Migration. Produktionsbuild erfolgreich. Browserprüfung für Varianten, Journal, Admin-Ansichten, Mobilansicht und bestehende Abläufe erfolgreich; keine JavaScript-Fehler.
- [x] Frische SQLite-Sicherung, Vorschau, Übernahme und Backend-Neustart abgeschlossen. Live-Prüfung bestätigt unveränderte Konten, Sitzungen, Guthaben, Karten, Packs, Kaufzähler und Öffnungen. Neue Varianten summieren sich exakt auf bisherigen Besitz.
- [x] Dokumentation in `docs/INVENTORY.md`, Admin-Anleitung, README, Structure-Deck-Hinweisen und Roadmap aktualisiert.

Berichte: `artifacts/variants-rehearsal.json`, `variants-tests.log`, `variants-browser.log`, `variants-migration.json`, `variants-import.json`, `variants-release-check.json`. Ansichten: `artifacts/collection-variants-desktop.png`, `collection-variants-mobile.png`.

Grenzen: Variante bezeichnet derzeit Hub-Herkunft und Seltenheit, nicht vollständig bestimmte physische Druckausgabe, Motiv oder Folierung. Das Reservierungsfeld ist Grundlage für den späteren Handel, noch keine aktive Handelsreservierung. Kartenset-Filter ist weiterhin ein Katalogfilter. A4/A5 folgen als gemeinsame Vergabelogik und Admin-Vergabeoberfläche; Handel und Saisonpass bleiben nachgelagert.


## Fortsetzung: Gemeinsame Vergaben und Admin-Oberfläche (A4/A5) – 02.10.2026

- [x] Gemeinsamer Vergabedienst für positive Punktegutschriften, konkrete Kartenvarianten und ungeöffnete Packs. Gemischte Vergaben erfolgen in einer Transaktion einschließlich Bestand, Journal, Auditbeleg und Benachrichtigung.
- [x] Geschützte Oberfläche unter **Admin-Menü → Konto → Vergabe vorbereiten**: Katalogsuche, Kartenbild, gültige Herkunft/Seltenheit, optional kontogebundene Karten, Packauswahl, Mengen und Begründung.
- [x] Vorschau mit Vorher-/Nachher-Werten; Abschluss erfordert Zielbenutzernamen und eigenes Administrator-Passwort. Geänderte Bestände oder Rechte werden erneut geprüft. Wiederholungen derselben Anfrage erzeugen keine zweite Gutschrift.
- [x] Normale Admins vergeben ausschließlich an normale Twitch-Konten; Support bleibt lesend. Hauptadministratoren dürfen auch Verwaltungskonten berücksichtigen. Aktive, noch nicht registrierte Twitch-Konten können bereits bedacht werden.
- [x] Normale Standardgrenzen je Vergabe: 10.000 Punkte, 30 Kartenexemplare, 10 Packs; über Konfiguration anpassbar. Hauptadministrator: maximal 1.000.000 Punkte, 1.000 Kartenexemplare und 100 Packs je Vergabe. Höchstens 20 unterschiedliche Positionen.
- [x] Structure-Deck-Geschenke zählen zum bestehenden Limit von drei Bezügen je Produkt/Konto. Kostenlose Vergaben umgehen dieses Limit nicht und ziehen keine Punkte ab.
- [x] Gespeicherte Vergabebelege im Admin-Audit; persönliche Benachrichtigungsglocke mit ungelesener Anzahl, lesbarer Begründung und Positionen. Empfänger können nur eigene Benachrichtigungen lesen und markieren.
- [x] 101 Backend-Tests erfolgreich, darunter parallele Wiederholungen, Konkurrenz mit Käufen, vollständiger Rollback, Rechtewechsel, Limits, ungültige Varianten, Kontobindung und Empfängerzugriff. Abschließende Eingabevalidierung zusätzlich mit allen 13 Vergabe-Tests geprüft.
- [x] Produktionsbuild und isolierter Browserdurchlauf erfolgreich: gemischte Vergabe, Vorschau, Kartenbild, gespeicherter Beleg, Empfängerbenachrichtigung und Mobilansicht. Keine JavaScript-Fehler. Keine Testvergaben an echten Konten.
- [x] Datenbank gesichert und Schema geprüft, lokales Backend neu gestartet. Read-only-Vergleich aller geschützten Bestands-, Konto-, Sitzungs- und Journaltabellen mit der Sicherung ohne Änderungen. Varianten- und Journalsummen stimmen; Integrität und Fremdschlüssel geprüft. Anonyme und Demo-Vergaben abgewiesen.
- [x] README, Admin-Anleitung, Roadmap, Konfigurationsbeispiel und `docs/GRANTS.md` aktualisiert.

Berichte: `artifacts/grants-tests.log`, `grants-validation-tests.log`, `grants-browser.log`, `grants-migration.json`, `grants-release-check.json`. Ansichten: `artifacts/grant-preview-mobile.png`, `grant-receipt-mobile.png`, `grant-notification-mobile.png`.

Sicherung vor Übernahme: `artifacts/db-backups/sdoycc-20261002T211926005520Z.db`.

Grenzen: Vergaben sind derzeit ausschließlich positiv und verwenden vorhandene gültige Kartenvarianten und Packs. Eigene Sonderkarten, Bestandskorrekturen und Sammelaktionen bleiben A6/A7. Grenzen gelten je Vergabe, nicht als Tageskontingent. Die Benachrichtigung erfolgt innerhalb der Website; es werden dabei keine Twitch-Nachrichten versendet. Öffentliches Hosting und ein externer HTTPS-Zugang sind weiterhin offen.


## Finale Ausbaurunde – 03.10.2026

Auf ausdrücklichen Wunsch wurden **alle geplanten Bereiche der ersten Version** umgesetzt. Rückmeldung zur öffentlichen Bereitstellung: Repository-/Pages-Adresse und HTTPS-Backend-Adresse sind „noch nicht vorhanden“.

- [x] A6: Community-Sonderkarten getrennt vom offiziellen Katalog, geprüfter und neu kodierter Bild-Upload, Entwurf/Veröffentlichung/Archiv, feste Identität, Edition/Seltenheit, Handelbarkeit und lebenslange Auflagenbegrenzung.
- [x] A6: Nachvollziehbare Korrekturen für Punkte, Karten und geschenkte ungeöffnete Packs mit Originalreferenz, Vorschau, Zielbestätigung, Passwort, Gegenbuchung und Beleg. Keine Rücknahme reservierter Karten oder automatisch bei einem späteren Besitzer; Structure-Deck-Zähler bleiben erhalten.
- [x] A7: Feste, deduplizierte Empfängerliste; Vorschau, Vergabe je Empfänger in eigener Transaktion, Wiederaufnahme und Ergebnishistorie. Normale Admin-Grenzen und Rechte werden je Empfänger erneut geprüft. Support bleibt lesend.
- [x] A7: Betriebsansicht prüft Bestände je Karte, Journale je Variante/Bindungsstatus, Reservierungen und Saison-XP. Übersicht offener Vorgänge und nachzuverarbeitender Ereignisse. Gefilterter CSV-Kontenexport für Hauptadministratoren.
- [x] T1–T4: Anzeigen/Pakete, Veröffentlichung mit Reservierung, verbindliche Vorschläge, Gegenbedingungen mit gespeicherter Versionshistorie, Status-/Ablaufprüfung, atomare beidseitige Übertragung, unveränderliche Abschlussbelege und Mitteilungen.
- [x] T5: Karten-/Set-/Seltenheitsfilter, erfüllbare Gesuche, Set-Assistent mit serverseitiger Vollständigkeitsprüfung und festgehaltener Setdefinition, eigene Anzeigen/Angebote/Historie, Meldungen, Blockierungen und befristete Handelssperren.
- [x] T6: Gleichzeitige Veröffentlichungen/Annahmen und Annahme gegen Stornierung geprüft. Acht parallele Veröffentlichungen können denselben Bestand nicht überreservieren. Mengen, Journal und Reservierungen bleiben konsistent. Lokale Freigabe; öffentliche Bereitstellung bleibt extern offen.
- [x] S1/S2: Admin-Entwurf mit echten Zeitfenstern, streng steigenden XP-Schwellen, konkreten Belohnungen, Budget je Konto und Beispielverläufen; Veröffentlichung prüft überlappende Saisons und fixiert Regeln.
- [x] S3: Gespeicherte Öffnungen erzeugen XP genau einmal. Tages-/Wochenboni haben eindeutige UTC-Perioden und wiederholbare Ereignisbelege. Keine XP durch Admin-Vergaben, bloße Klicks oder Hin-und-Her-Tausche.
- [x] S4/S5: Fortschritt, Aufgaben, Belohnungsleiste, einzelne atomare Abholung über gemeinsamen Vergabedienst, Belege, Archiv und versionierte Verlängerung der Abholfrist. Keine Übernahme alter Demo-XP.
- [x] S6: Probesaison ausschließlich in isolierter Browser-Datenbank angelegt/veröffentlicht; echte API-Öffnung, XP, Freischaltung und Belohnungsabholung geprüft. Auf der echten Datenbank keine Saison veröffentlicht.
- [x] Hintergrunddienst beim Start und alle 60 Sekunden: Reservierungsablauf und Nachverarbeitung fehlender Öffnungs-XP. Verbindliche Aktionen prüfen Fristen zusätzlich innerhalb ihrer Transaktion.
- [x] Alte unreservierte Handels-Prototyprouten und Demo-Saisonroute entfernt; deren Tabellen unverändert aufbewahrt. Neue Anzeigen verwenden ausschließlich das reservierte Paketmodell.
- [x] Deutsches UI, mobile Dialoge, Karten-/Belohnungsvorschau und navigierbare Belege. Im Browser gefundener Rücksprung aus den Anzeigendetails behoben; Bereichsauswahl ist in der URL verankert.
- [x] 132 Backend-Tests erfolgreich. Produktionsbuild erfolgreich. Vollständiger Browserdurchlauf mit 57 benannten Prüfpunkten einschließlich alter Kernabläufe und aller neuen Hauptabläufe erfolgreich; keine JavaScript-Fehler, keine horizontale Überbreite auf Mobilgeräten.
- [x] Kopie der tatsächlichen SQLite-Datenbank migriert: alle 36 bisherigen Tabellen in der Probe unverändert, 17 neue Tabellen additiv angelegt, kein weiterer Variantenumbau erforderlich; Integrität und Fremdschlüssel geprüft.
- [x] Frische Sicherung `artifacts/db-backups/sdoycc-20261003T200542291717Z.db`; anschließende Übernahme und Neustart. 35 fachliche Tabellen unverändert; lediglich der interne Serialisierungszähler wird vom neuen Bereinigungsdienst weitergeführt. Alle 17 neuen Tabellen leer: keine Tests auf echten Konten.
- [x] Lokale API und Frontend erreichbar. Neue geschützte Bereiche weisen anonyme Zugriffe ab. Systemprüfung lokal erfolgreich; öffentliche Prüfung meldet erwartungsgemäß fehlenden Produktionsmodus und öffentliche Adressen.
- [x] `check-system.bat` und `backend/scripts/release_check.py` ergänzt. Pages-Build verhindert fehlende/platzhalterhafte oder lokale Backend-Adresse. README, Admin-/Inventar-/Vergabeanleitung, Roadmap und Einzelpläne aktualisiert. Maßgebliche Betriebs-/Bedienübersicht in `docs/FINAL_STATUS.md`.

Nachweise: `artifacts/final-tests.log`, `final-browser.log`, `final-rehearsal.json`, `final-migration.json`, `final-local-readiness.json`, `final-public-readiness.json`, `final-release-check.json`. Neue Screenshots: `final-special-card-mobile.png`, `final-batch-mobile.png`, `final-trade-listing-mobile.png`, `final-trade-confirmation-mobile.png`, `final-trade-receipt-mobile.png`, `final-season-mobile.png`, `final-season-reward-mobile.png`.

Noch erforderlich für Zuschauer: GitHub Pages und öffentliche HTTPS-Adresse einrichten, Produktionswerte setzen, echten Twitch-Ablauf einschließlich Reward-Queue-Abschluss und Zugriff von einem anderen Gerät prüfen. Erste Live-Saison mit eigenen Zeiten/Belohnungen veröffentlichen. PostgreSQL wurde in dieser Runde nicht live geprüft. Erweiterungen außerhalb der festgelegten ersten Version sind im Abschlussstand ausdrücklich benannt.
