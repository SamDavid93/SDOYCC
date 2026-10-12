# Online-Alpha

Stand: 12.10.2026. Ziel: bestehendes Repository SamDavid93/SDOYCC, GitHub Pages und Windows-Backend auf dem Betreiber-PC.

## Betrieb

`APP_ENV=production` sperrt den Demo-Login. `ENABLE_DUEL_ALPHA=true` schaltet den nativen Worker ausdrücklich für den Alpha-Betrieb ein; die Entwicklungsfreigabe allein reicht nicht. Ein einzelner Uvicorn-Prozess betreibt den Supervisor. Kein `--reload` und keine mehreren Uvicorn-Worker verwenden. Die fünf parallelen Matches laufen in separaten Windows-AppContainern.

Der bestehende Starter `start-public-test.bat` startet Backend und HTTPS-Tunnel, prüft Health/CORS und stößt den Pages-Build des veröffentlichten Repository-Stands an. Lokale Änderungen müssen vorher geprüft und veröffentlicht sein. Der PC und Tunnel müssen eingeschaltet bleiben. Ein Quick Tunnel ist vorübergehend; ein Neustart kann eine neue API-Adresse und einen erneuten Pages-Build erfordern.

## Duellfreigabe

Das importierte Profil `TCG-EU 2026-05-18` ist ein festgeschriebener Alpha-Regelstand, keine Behauptung einer aktuellen Turnierliste. Die Regelverwaltung verlangt das Passwort des angemeldeten Eigentümers. Im Adminbereich unter Duell-Regelprofile den Paketabgleich, den offiziellen Listenimport und die Testnachweise prüfen; danach Engine und Region für genau dieses Profil freigeben. Als Nachweis können die vollständige Backend-Suite, die native Mechanik-, Sandbox-, Match- und Browserprüfung aus dem Statusdokument angegeben werden. Diese Änderung wird versioniert und auditiert. Keine direkte SQL-Freigabe verwenden.

```powershell
$env:PYTHONPATH='backend'
& '.\.venv\Scripts\python.exe' backend/scripts/release_check.py --public --duels
```

Erst wenn auch `approved_duel_profile` und `duel_worker_enabled` wahr sind, ist der Duellstart freigegeben. Vorhandene Decks benötigen dieses Profil, gültige Karten und den echten Bestand. Beide Spieler bestätigen Deck und Teilnahme.

## Abnahme und Rücknahme

Mit zwei echten Konten über zwei Netze, etwa WLAN und Mobilfunk, anmelden; private Lobby, Deckauswahl, Beschwörung, Reaktion, Browser-Neuladen, Aufgabe und Bestandsfreigabe prüfen. Die automatisierten lokalen Browserkontexte ersetzen diese Netzabnahme nicht. Reale Kanalpunktebuchungen nur mit dem Betreiber prüfen.

Bei Problemen im Adminbereich neue Duellstarts pausieren; laufende Spiele bleiben erhalten. Vor einem Serverneustart laufende Matches beenden oder den dokumentierten neutralen Abbruch verwenden. `ENABLE_DUEL_ALPHA=false` und Serverneustart deaktivieren den Worker. Keine Bestände oder Reservierungen per Hand löschen. Datenbank- und Konfigurationssicherungen liegen lokal unter `artifacts/`; sie dürfen nicht ins öffentliche Repository.

Die bisherigen offenen Nutzungs-/Weitergabenachweise für Kartenmaterial und die Software-Quellbereitstellung bleiben separat im [DuelZone-Status](DECKS_DUELZONE_STATUS.md) und im [Quellenverzeichnis](../integrations/duel/SOURCES.md) dokumentiert. Ein technischer Alpha-Start bestätigt diese Nachweise nicht.
