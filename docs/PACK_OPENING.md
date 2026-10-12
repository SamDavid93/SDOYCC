# Mehrere Packs direkt nacheinander öffnen

Nach dem Aufdecken oder Überspringen einer Öffnung bietet die Ergebnisansicht „Nächstes Pack öffnen“ an. Sie öffnet genau ein weiteres bereits gekauftes Pack derselben Edition, ohne die Ansicht zu verlassen. Die verbleibende Menge stammt aus der Serverantwort; bei null Packs ist die Schaltfläche gesperrt. Jeder Pack erhält eine eigene Öffnungshistorie und Kartenvergabe. Es erfolgt kein Kauf.

Die bestehende Öffnungsansicht bleibt erhalten. Aufdeckzustand, Kartenvergrößerung, Seltenheitseffekt und Animationsphase beginnen beim neuen Ergebnis von vorne. Tonpräferenz und Dialog bleiben erhalten. Während der Anfrage sind weitere Öffnungen, Schließen und die Navigation im Ergebnis gesperrt. Eine sofort gesetzte Anfragesperre verhindert doppelte Buchungen bei schnellen Mehrfachklicks. Der vorhandene Idempotenzmechanismus schützt Wiederholungen nach unklaren Netzwerkantworten.

Schlägt die nächste Öffnung fehl, bleiben die zuvor gezogenen Karten und das Ergebnis sichtbar. Eine Meldung erklärt den Fehler; derselbe Knopf erlaubt einen erneuten Versuch. Bestand und Sammlung werden nach erfolgreichen Aktionen über die bestehenden Hub-Aktualisierungen neu geladen.

Geprüft mit temporärer Datenbank und isolierten Konten: fortlaufende Öffnungen, Zurücksetzen der Karten, Fehler mit anschließender Wiederholung, synchroner Doppelklick mit genau einem verbrauchten Pack, vollständiges Leeren des Stapels, gesperrte Fortsetzung und Handyansicht. Nachweise: `artifacts/pack-next-build.log`, `artifacts/pack-next-browser.log` und `artifacts/pack-next-mobile.png`.
