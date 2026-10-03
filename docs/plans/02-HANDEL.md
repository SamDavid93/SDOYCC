# SDOYCC: Anzeigen und Kartentausch

Status: **Lokal umgesetzt und geprüft (03.10.2026)**. Konkrete Regeln, Rollen, Grenzen und offene externe Freigabe: [Abschlussstand](../FINAL_STATUS.md). Dieses Dokument hält auch frühere Produktannahmen und ausdrücklich spätere Erweiterungen fest.

## Produktumfang

Nutzer schalten Anzeigen: „Ich biete diese Karten oder dieses Kartenpaket und suche dafür diese Karten, ein Set oder passende Angebote.“ Ein Tausch überträgt Karten beider Seiten in einer gemeinsamen Buchung.

Die erste Version handelt ausschließlich virtuelle Karten im Hub. Punktepreise, Auktionen, externe Zahlungen, Boosterhandel und automatisches Matching sind Erweiterungen, keine stillschweigende Voraussetzung. Ein geschlossenes Set wird als Paket konkreter Karten definiert, nicht als Besitz an einem abstrakten Set-Datensatz.

## Navigation und Ablauf

| Ansicht | Inhalt |
| --- | --- |
| Anzeigen entdecken | Suche, Karten-/Setfilter, Seltenheit, angebotene/gesuchte Seite, Datum, nur erfüllbare Gesuche |
| Anzeigendetails | Anbieter, konkrete angebotene Mengen/Varianten, Gesuch, Status, Ablauf, angebotene Tauschbedingungen |
| Anzeige erstellen | Eigene verfügbare Karten auswählen, Set/Bündel zusammenstellen, Gesuch und Beschreibung, Vorschau |
| Meine Anzeigen | Entwürfe, aktive, pausierte/abgelaufene, abgeschlossene; Eingänge je Anzeige |
| Meine Angebote | Eingehende/ausgehende Vorschläge, Gegenangebote, reservierte Karten und Fristen |
| Abschluss und Historie | Beide Seiten, Mengen, Varianten, Zeitpunkt, Buchungs-ID; unveränderlicher Beleg |
| Meldungen | Anzeige melden, Blockieren, Status der eigenen Meldung |

Beispiel: Nutzer A reserviert zweimal Karte X und einmal Karte Y für seine Anzeige. Nutzer B wählt eigene verfügbare Karten und sendet einen verbindlichen Vorschlag. A prüft die genaue Gegenleistung und nimmt an. Ein atomarer Abschluss überträgt beide Pakete, schließt die Anzeige und löst alle übrigen Vorschläge/Reservierungen dazu auf.

## Was ein Kartenpaket oder Kartenset bedeutet

- Manuelles Bündel: konkrete Varianten und Mengen, ausdrücklich als Paket bezeichnet.
- Set-Assistent: Set auswählen, Kartenliste anzeigen, gewünschte Vollständigkeit festlegen, fehlende Karten und alternative Ausgaben sichtbar machen.
- „Vollständiges Set“ verlangt eine präzise Definition: je eine Kartenidentität oder jede bestimmte Ausgabe/Seltenheit. Erste Version verwendet standardmäßig eine Kartenidentität je Set-Karte; abweichende Ausgaben müssen ausdrücklich erlaubt sein.
- Beim Veröffentlichen eine feste Liste mit Mengen und Varianten speichern. Spätere Katalogimporte verändern bestehende Anzeigen nicht.
- Benutzer darf nicht „komplett“ anbieten, wenn der reservierbare Bestand unvollständig ist. Ein unvollständiges Bündel muss entsprechend bezeichnet werden.
- Altbestand ohne nachgewiesene Ausgabe darf nicht als seltene oder spezielle Variante beworben werden. Anzeigen mit solchen Karten zeigen die unbekannte Variante ausdrücklich oder bleiben bis zur Klärung ausgeschlossen.

## Bestandsregeln

`verfügbar = Besitz − aktive Reservierungen`. Karten im Angebot bleiben sichtbar im Besitz, sind aber während der Reservierung für andere Anzeigen/Vorschläge gesperrt.

1. Entwurf reserviert noch nichts. Veröffentlichung prüft und reserviert das angebotene Paket in einer Transaktion.
2. Ein eingereichter Vorschlag reserviert das Paket des Interessenten. Vor dem Absenden erklärt das UI die Bindung und Frist; vorgeschlagener Startwert: 48 Stunden, konfigurierbar.
3. Höchstens begrenzt viele aktive Anzeigen/Vorschläge pro Konto; vorgeschlagene Startwerte 10 Anzeigen und 10 ausgehende Vorschläge. Serverseitige Limits, keine reine UI-Beschränkung.
4. Stornierung, Ablehnung, Ablauf, Moderation und Abschluss lösen zugehörige Reservierungen genau einmal auf.
5. Geänderte Tauschbedingungen erhalten eine neue Version. Alte Zustimmungen und Vorschläge werden nicht für eine andere Gegenleistung wiederverwendet.
6. Neue Boosterfunde können den verfügbaren Bestand erhöhen; bereits reservierte Mengen bleiben unverändert.
7. Admin-Korrekturen dürfen reservierte Mengen nicht still entziehen. Entweder Aktion ablehnen oder betroffene Anzeigen ausdrücklich stornieren und dies protokollieren.

Der Bereinigungsdienst läuft periodisch und beim Backend-Start. Jede verbindliche Aktion prüft selbst den Ablauf und Status, damit ein ausgefallener Zeitgeber keinen abgelaufenen Tausch mehr zulässt.

## Zustände und Bestätigungen

Anzeigen: `draft → open → completed`; von `open` außerdem `cancelled`, `expired`, `moderated`. Pausieren reserviert nach erster Produktregel weiter; die UI nennt das deutlich, andernfalls müssen Veröffentlichung und Reservierung beim Wiederöffnen neu geprüft werden.

Vorschläge: `pending → accepted/rejected/withdrawn/expired/invalidated`. Ein Gegenangebot ist eine neue Version mit vertauschten Zustimmungsanforderungen, kein stilles Ändern eines bereits akzeptierten Vorschlags.

- Ein Interessent bestätigt beim Absenden das genaue Paket und seine Bindung an diese Version.
- Der Anzeigeninhaber bestätigt beim Annehmen dasselbe Paket. Server prüft beide Zustimmungen und beide aktuellen Bestände.
- Die erste Version tauscht ein Paket vollständig. Teilannahmen erfordern neue Bedingungen und gehören nicht in den ersten Abschlussmechanismus.
- Selbsttausch, gesperrte Konten, nicht handelbare Karten, fremde Besitzpositionen und nicht offene Anzeigen ablehnen.
- Nach einem erfolgreichen Abschluss kein regulärer „Rückgängig“-Knopf. Eine spätere Korrektur ist ein neuer, nachvollziehbarer Vorgang; bereits weitergetauschte Karten verhindern einfache Rückabwicklung.

## Atomarer Tauschabschluss

1. Aktionskennung und normalisierten Nutzdaten-Hash prüfen; gespeicherten Erfolg bei Wiederholung zurückgeben.
2. Anzeige/Vorschlag mit Version laden und sperren. Beteiligte Benutzer und Variantenbestände in stabiler Reihenfolge nach ID sperren.
3. Status, Fristen, Rechte, Handelbarkeit, Paketliste und zugehörige Reservierungen erneut prüfen.
4. Beide Seiten in derselben Datenbanktransaktion abbuchen/gutschreiben. Inventarjournal enthält paarige Bewegungen mit gemeinsamer Tausch-ID.
5. Anzeige abschließen, angenommenen Vorschlag kennzeichnen, übrige Vorschläge invalidieren und deren Reservierungen lösen.
6. Abschlussbeleg, Audit und Benachrichtigungsereignisse speichern; erst danach committen.

SQLite benötigt eine tatsächliche Schreibsperre, da `FOR UPDATE` dort keine Zeilensperre ersetzt. Für PostgreSQL geordnete Zeilensperren verwenden. Vor Übertragung kein eigenes Commit einer Teilsumme. Derselbe Vertrag muss für beide Datenbanken gelten.

## Geplante Daten und API

| Tabelle/Modell | Wesentliche Daten |
| --- | --- |
| `TradeListing` v2 | Eigentümer, Text, Status, Version, Ablauf, Paketdefinition, Moderationsstatus |
| `TradeListingItem` | Angebotsvariante und Menge |
| `TradeWantedItem` | Gewünschte Karte/Variante/Set, Menge, erlaubte Alternativen |
| `TradeProposal` / Positionen | Interessent, angefragte Version, konkretes Gegenpaket, Status, Frist |
| `InventoryReservation` | Besitzer, Variante, Menge, Vorgang, Status und Ablauf |
| `TradeSettlement` / Positionen | Unveränderliche Übertragungsdaten und Bestätigungen |
| `TradeReport` / Blockierung | Grund, meldendes Konto, Ziel, Moderationsmaßnahme |

Geplant: `GET /api/trade/listings`, `GET /api/trade/listings/{id}`, `POST /api/trade/listings`, `POST .../{id}/publish`, `POST .../{id}/cancel`, `POST .../{id}/proposals`, `POST /api/trade/proposals/{id}/accept`, `.../reject`, `.../withdraw`, `GET /api/trade/me/history`, `POST .../{id}/reports`. Änderungen verlangen Eigentümerprüfung und Versionsnummer; Konflikte liefern 409 mit verständlichem Hinweis.

Die vorhandene `TradeListing`-Tabelle nicht ohne Prüfung als aktive Anzeige übernehmen: alte Zeilen haben keine Reservierungen. Migration übernimmt sie höchstens als zu bestätigende Entwürfe. Die alte ungesicherte Erstellung wird bei Aktivierung der neuen Funktion abgeschaltet oder auf den neuen Dienst umgeleitet.

## Darstellung und Moderation

- Kartenbilder mit bestehender Lade-/Sprachersatzlogik; Kartenname, Seltenheit, Ausgabe, Menge und Handelbarkeit stets als Text.
- Verfügbare und reservierte Mengen im Auswahlfenster und in der Sammlung anzeigen. Schaltfläche bei null verfügbar deaktivieren und Grund erklären.
- Vorschau „Du gibst / Du erhältst“, keine Bestätigung anhand abgeschnittener Kartennamen.
- Beschreibungen als Text behandeln, Längen begrenzen, keine HTML-Ausführung. Gesuchte Karten primär strukturiert erfassen, damit Filter funktionieren.
- Keine privaten Kontoangaben anzeigen: öffentlicher Twitch-Anzeigename, Handelsstatistik nur soweit verlässlich, keine E-Mail/IP/Sitzungsdaten.
- Meldungen und befristete Handelssperren über Admin-Bereich; Löschung einer Anzeige darf Belege eines abgeschlossenen Tauschs nicht entfernen.
- Erste Version kommuniziert über Angebote und Website-Mitteilungen. Freitextchat, automatische Twitch-Nachrichten oder externe Kontaktvermittlung sind nicht erforderlich.

## Arbeitspakete und Abnahme

- [x] T1: Anzeigen-/Paketmodell, Reservierungsdienst, Ablaufbereinigung und Migration alter Prototypdaten.
- [x] T2: Anzeigenübersicht, strukturierte Suche, Entwurf/Veröffentlichung und Auswahl aus verfügbarem Bestand.
- [x] T3: Verbindliche Vorschläge, Gegenangebotsversionen und Benachrichtigungen.
- [x] T4: Atomarer Abschluss, Belege, Inventaranzeige und Wiederholungsschutz.
- [x] T5: Set-Assistent, Moderation und mobile/tastaturbedienbare Abläufe.
- [x] T6: Last-/Parallelitätsprüfung und begrenzte Freigabe nach Abnahme.

Pflichttests: dieselbe Karte parallel in zwei Anzeigen; zwei zeitgleiche Annahmen einer Anzeige; Annahme gegen Stornierung/Ablauf/Sperre; veraltete Version nach Gegenangebot; Mengen größer als verfügbar; gefälschte Eigentümer-ID; Wiederholung nach verlorener Antwort; Fehler zwischen Abbuchung/Gutschrift; Wiederanlauf nach Backend-Ausfall; Set-Zusammensetzung nach Katalogimport unverändert. Nach jedem Fall müssen Gesamtkartenmenge und Reservierungssummen konsistent bleiben.
