# SDOYCC: Admin-Bereich und Benutzerverwaltung

Status: **Lokal umgesetzt und geprüft (03.10.2026)**. Konkrete Regeln, Rollen, Grenzen und offene externe Freigabe: [Abschlussstand](../FINAL_STATUS.md). Dieses Dokument hält auch frühere Produktannahmen und ausdrücklich spätere Erweiterungen fest.

## Ziel und typische Abläufe

Der Betreiber findet ein Konto anhand des Twitch-Namens oder der Twitch-ID, sieht dessen Registrierung, Guthaben, Sammlung und Booster und kann begründete, nachvollziehbare Verwaltungsaktionen ausführen.

Beispiel Punktevergabe: Konto suchen → 100 Sammelpunkte und Grund eingeben → Zielkonto, Änderung und resultierenden Kontostand prüfen → Vergabe ausführen → Buchungsnummer und aktualisierten Kontostand sehen. Bei einer Wiederholung derselben Anfrage entsteht keine zweite Gutschrift.

Beispiel besondere Karte: Karte suchen → konkrete Ausgabe/Seltenheit auswählen → Menge und gegebenenfalls Handelbarkeit festlegen → Vorschau des Empfängers/der Karte prüfen → vergeben → Herkunft „Admin-Vergabe“ im Inventarjournal und eine Mitteilung beim Empfänger.

## Navigation und Ansichten

| Bereich | Inhalt und Aktionen |
| --- | --- |
| Übersicht | Aktive/gesperrte Konten, offene Meldungen, letzte Vergaben, Integrationsfehler; Links zu den betroffenen Datensätzen |
| Benutzer | Paginierte Suche, Twitch-ID, Rolle, Registrierung, Status, Filter, letzte Aktivität soweit vorhanden |
| Kontodetails | Profil, Sitzungen, Guthabenjournal, Karten/Varianten, reservierte Bestände, Booster, Vergaben und Audit |
| Vergaben | Einzel- und später Sammelvergabe für Punkte, Karten oder Booster; Vorschau, Ergebnis und Historie |
| Karten und Sonderkarten | Vorhandene Karte/Ausgabe auswählen, eigene Sonderkarte als Entwurf verwalten, Veröffentlichung getrennt von Vergabe |
| Booster | Status, tatsächlicher Pool, konfigurierte/effektive Kartenanzahl und Bilder prüfen; Pooländerungen versionieren |
| Moderation | Benutzerberichte und später Handelsanzeigen, Maßnahmen mit Grund und Dauer |
| Protokoll | Filterbare Änderungen nach Akteur, Ziel, Typ, Zeitraum und Vorgangsnummer |
| Einstellungen | Rollen, Vergabelimits, Funktionsfreigaben, öffentliche Texte; keine Anzeige von Backend-/Twitch-Geheimnissen |

Ein Nutzerkonto bekommt eine stabile interne URL nach Benutzer-ID. Ein Twitch-Namenswechsel darf kein neues Guthabenkonto erzeugen. Twitch-ID und Registrierungsnachweis bleiben maßgeblich; freie Umbenennung durch Administratoren ersetzt keinen Twitch-Nachweis.

## Rollen und Rechte

Vorhandene Rollen `user`, `support_admin`, `admin`, `super_admin` weiterverwenden, aber auf klar benannte Rechte abbilden.

| Aktion | Benutzer | Support | Admin | Betreiber/Super-Admin |
| --- | --- | --- | --- | --- |
| Eigenes Konto und eigene Bestände lesen | Ja | Ja | Ja | Ja |
| Fremde Konten für Support lesen | Nein | Ja, eingeschränkt | Ja | Ja |
| Normale Nutzer sperren/entsperren, Sitzungen beenden | Nein | Nur beauftragte Support-Rechte | Ja | Ja |
| Punkte/Karten/Booster vergeben | Nein | Nein | Innerhalb konfigurierter Limits | Ja |
| Korrekturbuchung/Bestandskorrektur | Nein | Nein | Gesondertes Recht | Ja |
| Sonderkarten veröffentlichen | Nein | Nein | Gesondertes Recht | Ja |
| Rollen vergeben, Limits ändern | Nein | Nein | Nein | Ja |
| Andere Admins verwalten | Nein | Nein | Nein | Ja |

- Ersten Betreiber nur über einen lokalen, protokollierten Einrichtungsbefehl einer bestehenden verifizierten Twitch-ID zuordnen. Niemals automatisch über Anzeigenamen oder den Demo-Login.
- Niemand darf durch Ändern einer Anfrage eigene Rechte erweitern. Der letzte aktive Super-Admin darf nicht gesperrt oder herabgestuft werden.
- Rechte für jede Schreibaktion neu aus der Datenbank lesen. Kritische Aktionen verlangen eine frische Passwortbestätigung; kein Passwort in Audit oder Aktionsbeleg speichern.
- Globale Kontosperre und spätere reine Handelssperre unterscheiden. Eine globale Sperre beendet Sitzungen und stoppt weitere Kontoaktionen; offene Reservierungen nach Handelsregeln auflösen.

## Kontoaktionen

A2 verfügbar: Anmelde-Zurücksetzung (ausdrücklich kein Spielstand-Reset), globale Sperre/Entsperrung, alle Sitzungen widerrufen, Rollenverwaltung und Auditansicht. Einzelne Sitzungen und automatische Sperrabläufe bleiben Erweiterungen. Bedienung: [Kontoverwaltung](../ADMIN.md).

- Profil und Twitch-Zuordnung lesen; Guthaben nicht als frei überschreibbares Profilfeld behandeln.
- Sperren/Entsperren mit Begründung, optionalem Ablauf und klarer Anzeige für den Betroffenen.
- Einzelne oder alle Sitzungen widerrufen, ohne Zugriff auf Sitzungstokens im Admin-UI.
- Passwortwiederherstellung als eigenen Prozess planen: privater Browser-Schlüssel + erneut bestätigter Twitch-Chat-Code; danach neues Passwort und Widerruf alter Sitzungen. Bestehende Registrierung darf nicht einfach ein zweites Passwort setzen.
- Noch unregistrierte Konten als solche anzeigen. Punkte können weiterhin derselben Twitch-ID gutgeschrieben sein; Vergaben ändern den Registrierungsstatus nicht.
- Konto-Löschung/Anonymisierung separat entwickeln: offene Tausche/Reservierungen schließen und Buchungsreferenzen erhalten. Keine endgültige Löschung in der ersten Admin-Version.

## Punkte, Karten und Booster vergeben

A4/A5 umgesetzt: [Vergabeoberfläche, Rechte, Limits und Buchungsregeln](../GRANTS.md). Positive Einzelvergaben mit mehreren Positionen; Korrekturen und Sammelvergaben bleiben offen.

Alle Vergaben verwenden einen gemeinsamen `GrantService` mit Empfänger, Belohnungspositionen, Akteur, Grund, Herkunft, Aktionskennung und Nutzdaten-Hash.

**Punkte:** positive ganze Menge, serverseitiges Maximum, bestehendes `DiamondTransaction`-Journal. Korrekturen erzeugen Gegenbuchungen mit Bezug zum Original, statt dessen Zeile zu ändern. Abzüge dürfen Guthaben nicht unter null bringen. Änderungen zeigen im Benutzerkonto „Admin-Gutschrift“ bzw. „Admin-Korrektur“.

**Karten:** konkrete Karten-/Varianten-ID, Menge, Herkunft und Handelbarkeit. Eine Sonderkartenvergabe darf nicht zufällig eine beliebige Ausgabe der Kartenidentität liefern. Auswahl zeigt Motiv, Namen, Seltenheit, Set/Edition und Sprachersatz. Ein bereits getauschtes Exemplar wird bei einer Rücknahme nicht heimlich vom jetzigen Besitzer entfernt; der Vorgang braucht eine sichtbare Klärung.

**Booster:** existierende aktive Booster-ID und Menge; Bestand erhöhen, keine automatische Öffnung und kein Kaufpreisabzug. Ungültiger/leerer Ziehungspool blockiert eine Vergabe, die sonst unbrauchbare Packs erzeugen würde.

**Sammelvergaben, zweite Ausbaustufe:** Empfängerliste vor Ausführung festhalten, Duplikate entfernen, jede Zeile validieren. Pro Empfänger atomar ausführen; Job kann mit derselben Kennung fortgesetzt werden. Ergebnis unterscheidet ausgeführt, bereits ausgeführt, abgelehnt und noch offen. Keine erneute Vergabe an bereits abgeschlossene Empfänger bei einem Job-Neustart.

## Variantenbestand als Voraussetzung

A3 umgesetzt: [Bestandsregeln, Mengenrekonstruktion und Betrieb](../INVENTORY.md). Ungeklärte Mengen bleiben ausdrücklich Altbestand; physische Druckausgaben und Motivvarianten werden nicht erfunden.

- Neues Variantenmodell mit Karten-ID, optionaler Ausgabe-ID, Seltenheit und stabiler Variantenkennung. Bildsprache ist keine eigene Besitzvariante, wenn es sich nur um die UI-Darstellung handelt.
- Besitz je Benutzer/Variante und gegebenenfalls Bindungsstatus; Menge und reservierte Menge getrennt. Quelle/Veränderung über ein Inventarjournal nachvollziehen.
- Öffnungen, Admin-Vergaben und später Saisonbelohnungen schreiben diesen Bestand über dieselbe Dienstschicht.
- Bestehende `InventoryItem`-Summen erhalten. Historische Öffnungen nur soweit eindeutig zuordnen, wie sie durch vorhandene Bestände und Ereignisse belegt sind. Ungeklärter Rest bleibt als „Altbestand – Ausgabe nicht bestimmt“ erhalten.
- Keine pauschale Umwandlung aller vorhandenen Kopien in die höchste jemals gezogene Seltenheit. Vor Aktivierung des Variantenhandels müssen Bestände und Reservierungen zusammenpassen.
- Migration in Kopie prüfen: Summe der Varianten pro Benutzer/Karte muss der alten Gesamtmenge entsprechen. Alte API kann diese Summen weiterhin liefern, bis alle Ansichten umgestellt sind.

## Sonderkarten und Katalogpflege

Eigene Community-Karten getrennt vom importierten Yu-Gi-Oh!-Katalog führen: eigener Anbieter/Namensraum, Entwurf/aktiv/archiviert, Motiv, Anzeigename, Text, Seltenheit, Edition, optionale Vergabegrenze und Handelbarkeit.

Dateiuploads auf unterstützte Bildtypen, tatsächliches Dateiformat, Pixelmaße und Größe prüfen. Dateinamen serverseitig erzeugen, kein ausführbarer Upload und kein ungeprüfter Abruf beliebiger URL-Ziele. Keine künstlich erzeugte offizielle Karten-ID vergeben. Katalogimporte dürfen eigene Karten oder vergebene Varianten nicht überschreiben.

Veröffentlichte Identität einer bereits vergebenen Karte nicht nachträglich in eine andere Karte umwandeln. Neue Version/Edition statt solcher Änderungen; reine Fehlerkorrekturen protokollieren. Archivierung verhindert künftige Vergaben, löscht aber vorhandenen Besitz nicht.

## Geplante Daten und Schnittstellen

| Daten | Zweck |
| --- | --- |
| `AdminAuditEvent` | Akteur, Aktion, Ziel, Grund, Zeitpunkt, relevante Vorher-/Nachherwerte und Vorgangs-ID; keine Geheimnisse |
| `Grant` / `GrantItem` | Belohnungspaket, Empfänger, Herkunft, Aktionskennung, Nutzdaten-Hash, Ergebnis |
| `CardVariant` / Variantenbestand | Ausgabe/Seltenheit und tatsächlicher Besitz |
| `InventoryTransaction` | Kartenbewegung mit Menge, Besitzer, Variante, Referenz und Bestand danach |
| `AccountRestriction` | Sperrtyp, Grund, Zeitraum und ausführender Administrator |
| `Notification` / Ereignisausgang | Mitteilungen nach erfolgreichem Commit, eindeutig pro Ereignis |
| `GrantBatch` / Empfängerzeile | Wiederaufnehmbare Sammelvergabe mit Fortschritt |

Geplante Endpunkte: `GET /api/admin/users`, `GET /api/admin/users/{id}`, `GET .../inventory`, `GET .../wallet-history`, `POST .../restrictions`, `POST .../sessions/revoke`, `POST /api/admin/grants`, `GET /api/admin/grants/{id}`, `POST .../corrections`, `GET /api/admin/audit`, später Sonderkarten-/Sammelvergabe-Endpunkte. Schreibaktionen verwenden Pflicht-Aktionskennungen und prüfen Rechte auch dann, wenn das UI umgangen wird.

## Arbeitspakete und Abnahme

- [x] A1: Rechteprüfung, Betreiber-Einrichtung, Admin-Routen und reine Leseansichten.
- [x] A2: Audit, Sitzungssperren und Kontoaktionen; Tests gegen Selbsteskalation und Sperre des letzten Betreibers.
- [x] A3: Variantenmodell, Inventarjournal, bestandswahrende Migration und Anpassung von Öffnungen/Sammlung.
- [x] A4: Gemeinsamer Vergabedienst für Punkte/Karten/Booster; atomare Buchungen und wiederholbare Anfragen.
- [x] A5: Vergabeoberfläche mit Vorschau, Ergebnisbeleg und Benutzerbenachrichtigung.
- [x] A6: Sonderkarten-Verwaltung und nachvollziehbare Korrekturen.
- [x] A7: Sammelvergaben, Filter/Exporte und Betriebsansichten erst nach stabiler Einzelvergabe.

Abnahmefälle: unberechtigte Anfragen liefern 403; Wiederholung vergibt einmal; veränderte Nutzdaten mit gleicher Kennung liefern 409; Fehler bei einer Position lassen alle Positionen ungebucht; parallele Korrektur/Kauf führen zu keinem negativen Guthaben; reservierte Karten können nicht frei abgezogen werden; fehlendes Kartenbild blockiert keine gültige Kartenidentität; alle Änderungen sind über Vorgangsnummern nachvollziehbar. Migration und Wiederherstellung mit einer Datenbankkopie prüfen.
