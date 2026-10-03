# SDOYCC – Arbeitsplan

Stand: 03.10.2026. Zielname: **SDOYCC – SamDavidOfficial's Yu-Gi-Oh Card Collector**.

Admin A1–A7, Handel T1–T6 und Saisonpass S1–S6 sind lokal umgesetzt. Die Produktregeln der ersten Version, Bedienwege und noch fehlende öffentliche Einrichtung stehen im [Abschlussstand](../FINAL_STATUS.md). Eine echte Saison wird vom Betreiber bewusst veröffentlicht; es werden keine Demo-Fortschritte übernommen. Die folgenden Ausgangsangaben dokumentieren die frühere Planungsgrundlage, nicht den aktuellen Funktionsstand.

## Reihenfolge und Abhängigkeiten

| Phase | Ergebnis | Voraussetzung | Detailplan |
| --- | --- | --- | --- |
| 0 | Booster-Mengenregel und Umbenennung – umgesetzt | Vom Nutzer zur Umsetzung freigegeben | Dieses Dokument |
| 1 | Kontoverwaltung, Rollen, nachvollziehbare Vergaben | Gemeinsame Bestands- und Buchungsgrundlage | [Admin-Bereich](01-ADMIN.md) |
| 2 | Anzeigen und verbindlicher Kartentausch | Variantenbestand, Reservierungen, Audit aus Phase 1 | [Handel](02-HANDEL.md) |
| 3 | Saisonfortschritt, Aufgaben und Belohnungen | Gemeinsamer Vergabedienst, stabile Ereignisse | [Saisonpass](03-SAISONPASS.md) |

Jedes Arbeitspaket wird nach seiner Umsetzung anhand der unten verlinkten Kriterien geprüft und dokumentiert. Es gibt bewusst noch keine Zeitversprechen.

## Verifizierter Ausgangszustand

- React/TypeScript mit Hash-Routen, FastAPI/SQLAlchemy, lokale SQLite-Datenbank; PostgreSQL ist konfigurierbar.
- GitHub Pages soll später das Frontend ausliefern. Das Backend läuft lokal; öffentliches HTTPS-Hosting ist noch nicht eingerichtet.
- Twitch-Zuordnung über Streamer.bot: `!register`, Browser-Bestätigung, `!confirm CODE`, danach Benutzername/Passwort. Keine eigene Twitch-Developer-Anwendung.
- Einlösung von 1.000 Kanalpunkten ergibt 100 Sammelpunkte. Booster kosten 100 Sammelpunkte; Öffnungen sind kostenlos.
- Konten besitzen `role`, `is_active`, Twitch-ID und Passwort-Hash. Sitzungen werden serverseitig verwaltet.
- Guthabenjournal und Aktionsbelege existieren. Ein wiederholter Kauf-/Öffnungsaufruf mit gleicher Aktionskennung wird nicht erneut ausgeführt.
- `InventoryItem` zählt pro Benutzer/Karten-ID. Der ergänzte Variantenbestand zählt belegte Seltenheiten/Herkunft getrennt und gleicht sich mit dieser Summe ab. Ungeklärter Altbestand bleibt gesondert erhalten; Bestandsdetails zeigen die Mengen je Variante.
- Bestehende Handels-Endpunkte sind ein Prototyp für eine einzelne Karte ohne Reservierung oder Abschluss. Nicht als fertiger Tauschdienst ausbauen, ohne zuerst die Bestandsgrundlage zu ergänzen.
- `BattlePassProgress` und `/battle-pass/me` sind ein Demo-Prototyp mit festem Saisonnamen, Resttagen und XP-Schwelle.
- Namen/Texte bevorzugen Deutsch und fallen auf Englisch zurück. Bilder verwenden deutsche Quellen mit gekennzeichnetem Originalbild als Ersatz.

## Phase 0: Booster-Begrenzung

Umgesetzte Regel: `effektive Kartenanzahl = min(konfigurierte Kartenanzahl, Anzahl unterschiedlicher ziehbarer Karten-IDs)`.

Beispiele: fünf konfigurierte Karten und drei Kartenarten im Pool ergeben drei Karten; fünf und zwölf ergeben fünf; eine Kartenart ergibt eine Karte. Mehrere Seltenheitseinträge derselben Karte erhöhen die Anzahl der Kartenarten nicht. Einträge mit Gewicht null zählen nicht als ziehbar. Negative/nicht endliche Gewichte, ein vollständig leerer Pool oder eine konfigurierte Anzahl unter eins machen den Booster ungültig.

Diese Mengenregel ändert für sich genommen nicht die bisherige gewichtete Ziehung mit möglichen Duplikaten. Eine Garantie unterschiedlicher Karten innerhalb einer Öffnung wäre eine zusätzliche Produktregel; sie ist nicht stillschweigend Teil dieser Begrenzung. Der Preis bleibt 100 Sammelpunkte.

- [x] Gemeinsame Funktion für gültigen Pool, eindeutige Kartenarten und effektive Anzahl erstellen.
- [x] Dieselbe Berechnung für Shop, Kartendetails/Set-Booster, Booster-Detail und Pack-Tresor verwenden.
- [x] Öffnungsroutine anhand der effektiven Anzahl ausführen; keine Auffüllung auf fünf Karten bei kleinen Pools.
- [x] Kauf und Öffnen eines ungültigen Pools ohne Guthaben-/Bestandsänderung ablehnen.
- [x] Anzeigen dürfen nicht fünf Karten versprechen, wenn die tatsächliche Öffnung drei ausgibt.
- [x] Historische Öffnungen und vorhandene Karten nicht nachträglich ändern.
- [x] Tests für Poolgrößen 0/1/3/5/6, Mehrfachraritäten, Gewicht null, ungültige Gewichte, wiederholte Anfragen und Bestands-/Guthabenerhalt.
- [x] Browserprüfung für kleinen Booster: Anzeige, Kauf, Öffnung, Ergebnis und Pack-Tresor stimmen überein.

Betroffene Stellen: `backend/app/api.py` (`boosters`, `booster_payload`, `purchase_booster`, `open_booster`), `backend/app/modules/card_data/boosters.py`, `frontend/src/components/BoosterDisplay.tsx`, `frontend/src/pages/MyPacksPage.tsx`, `frontend/src/pages/WorkspacePages.tsx`, Economy-/Katalogtests.

## Phase 0: Umbenennung

- [x] Kurzname überall **SDOYCC**; ausgeschriebener Name **SamDavidOfficial's Yu-Gi-Oh Card Collector** auf Anmeldung, Markenbereich/Infotext und Browser-Metadaten.
- [x] Seitenleiste, Opening-Show, Kartenrückseite einschließlich `CC`-Kürzel und Fenstertitel der Startdateien anpassen.
- [x] Standard-Booster auf „SDOYCC Origins“ umbenennen, ohne seine ID, Pool-Einträge oder vorhandenen Besitz zu ersetzen.
- [x] README, Paketnamen/Lockdatei, API-Titel und übrige eigene Markenreferenzen vereinheitlichen.
- [x] Technische Datenbankpfade separat behandeln: eine bloße Änderung von `DATABASE_URL` darf keine neue leere Datenbank aktivieren. Die Datei wurde mit Sicherung, gestopptem Backend, aktualisierter Konfiguration und anschließendem Datenvergleich nach `sdoycc.db` umbenannt.
- [x] Tatsächliche Drittanbieter-Bezeichnungen nicht mit der Produktmarke verwechseln: `providers/cardcluster.py` beschreibt einen externen Anbieter. Der vorhandene Anbieteradapter behält seinen sachlichen Namen; er ist keine frühere Produktmarke im UI.
- [x] Historische Sicherungsdateien nicht umbenennen oder ihre dokumentierten Pfade verfälschen.
- [x] Abschließende Textsuche nach alter Marke; verbleibende Treffer begründen. Build, Desktop/Mobilansicht, Anmeldung und Öffnung prüfen.

## Gemeinsame Grundlage vor Admin-Vergaben und Handel

1. **Rechte:** Berechtigungen serverseitig prüfen; unsichtbare Schaltflächen sind kein Zugriffsschutz.
2. **Bestand:** Pro Ausgabe/Seltenheit differenzierbarer Besitz und ein Journal für Kartenbewegungen ergänzen. Besessen, reserviert und verfügbar getrennt anzeigen.
3. **Vergaben:** Ein zentraler Dienst für Punkte, Karten und Booster. Admin und Saisonpass verwenden denselben Dienst und dieselben Buchungsregeln.
4. **Atomare Änderungen:** Guthaben, Inventar, Aktionsbeleg und Audit-Eintrag in einer Transaktion. Keine Teilvergaben.
5. **Wiederholungen:** Stabile Aktionskennung und normalisierter Nutzdaten-Hash. Gleiche Kennung mit anderem Ziel/Menge/Inhalt muss einen Konflikt liefern.
6. **Benachrichtigungen:** Zuerst ausschließlich innerhalb der Website. Ereignisse nach Commit erzeugen; kein automatischer Versand über Twitch, E-Mail oder andere Dienste im Rahmen dieser Planung.
7. **Migration:** Sicherung, Migration in Kopie, Summenvergleich je Benutzer, Wiederholbarkeit und Rückfallweg. Kein Erfinden historischer Seltenheitsverteilungen.
8. **Betrieb:** Geplante Bereinigung für abgelaufene Reservierungen und Saisonfristen. Nach Serverausfall nachholen; die verbindliche Zustandsprüfung erfolgt trotzdem in jeder Aktion.

## Einheitliche Abschlussprüfung je späterer Phase

- [ ] Erlaubte Rollen und verweigerte Zugriffe automatisiert geprüft.
- [ ] Parallele Requests, doppelte Klicks, erneute Requests nach Zeitüberschreitung und veraltete Ansichten geprüft.
- [ ] Echte Nutzerbestände ausschließlich durch ausdrücklich ausgeführte Produktaktionen verändert; Tests verwenden isolierte Datenbanken.
- [ ] Deutsches UI mit verständlicher Bestätigung, Leer-/Lade-/Fehlerzuständen, Tastaturbedienung und mobiler Ansicht.
- [ ] Serverseitige Suche/Paginierung, sinnvolle Indizes und keine unbeschränkte Übertragung kompletter Bestände.
- [ ] README, API-Verträge, Migrations- und Betriebsanweisungen aktualisiert.
- [ ] Funktionsschalter/Startfreigabe und Rückfallplan dokumentiert; keine Veröffentlichung allein aufgrund bestandener Tests.

## Fortsetzung für eine spätere Arbeitssitzung

Zuerst den tatsächlichen Umsetzungsstatus in `WORK_PLAN.md` prüfen. Danach nur das nächste freigegebene Arbeitspaket öffnen. Die nachfolgenden Pläne enthalten Produktannahmen; sie sind bei widersprechenden Nutzerwünschen anzupassen, bevor daraus Code entsteht. Kontostände, Variantenbestand und Tauschreservierungen dürfen nie für eine Designvorschau manipuliert werden.
