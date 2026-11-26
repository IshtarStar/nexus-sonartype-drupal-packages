Ich möchte die Anbindung eines Drupal-/PHP-Projekts an Sonatype Nexus Repository klären und einen weiterhin ungelösten Fehler untersuchen.

## Mein Anliegen und bekannter Stand

Meine ursprüngliche Frage:
„Was ist Best Practice für die Anbindung eines Drupal-PHP-Repositorys an einen Sonatype Nexus?“

Danach habe ich die eingesetzte Version angegeben:

**Nexus Repository: 3.96.3-01**

Der Fehler ist weiterhin ungelöst. In der bisherigen Unterhaltung wurden jedoch weder die konkrete Fehlermeldung noch die tatsächliche Konfiguration übermittelt. Bitte behandle die bisherigen Empfehlungen daher als Vorschläge und nicht als bereits umgesetzte oder erfolgreich getestete Konfiguration.

## Was bisher nicht bekannt ist

- Nexus-Edition und Lizenz: Pro oder Community, bisher unbeantwortet.
- Drupal-, PHP- und Composer-Version.
- Konkrete Fehlermeldung und auslösender Befehl.
- Tatsächliche Nexus-Adresse und Repository-Namen.
- Vorhandene Nexus-Repository-Typen und deren Einstellungen.
- Inhalt von `composer.json` und relevante Einträge aus `composer.lock`.
- Authentifizierung und Berechtigungen.
- Lokale Entwicklungsumgebung und CI-System.
- Netzwerk, Reverse Proxy, TLS-Zertifikate und Internetzugriff.
- Ob Composer-Pakete bezogen, eigene Pakete veröffentlicht oder fertige Drupal-Releases abgelegt werden sollen.
- Ob bereits ein Community-Composer-Plugin verwendet wird.

Es wurden keine Dateien untersucht, keine Systeme verändert und keine Installationstests durchgeführt.

## Bisher empfohlene Architektur

Der Quellcode bleibt in Git. Composer bezieht Abhängigkeiten über Nexus. Die CI baut anschließend ein versioniertes Release-Archiv oder Container-Image.

Vorgeschlagene Struktur:

Drupal-Projekt / CI
→ Nexus Composer Group
→ Composer Proxy für Packagist
→ Composer Proxy für Drupal.org
→ optional Composer Hosted für eigene Pakete

Vorgeschlagene Repository-Namen und Quellen:

| Name | Typ | Zweck / Quelle |
|---|---|---|
| composer-packagist | Composer Proxy | https://repo.packagist.org/ |
| composer-drupal | Composer Proxy | https://packages.drupal.org/8 |
| composer-internal | Composer Hosted | Eigene wiederverwendbare PHP-Pakete und Drupal-Module |
| composer-group | Composer Group | Gemeinsamer Zugang für Entwicklung und CI |

Die Namen sind Beispiele. Es ist nicht bestätigt, dass diese Repositories tatsächlich existieren.

Projektspezifische Drupal-Custom-Module können direkt im Projekt-Git verbleiben. Ein Hosted-Repository ist nur erforderlich, wenn eigene Composer-Pakete verteilt werden sollen.

## Dokumentierte Nexus-Unterstützung laut bisheriger Recherche

Die vorherige KI hat die offizielle Sonatype-Dokumentation gelesen und daraus folgende Angaben übernommen:

- Native Composer-Proxy-Unterstützung ab Nexus 3.75.0.
- Native Composer-Hosted- und Group-Unterstützung ab Nexus 3.95.0.
- Composer-Unterstützung laut Dokumentation für Sonatype Cloud und selbst gehostetes Nexus Pro.
- Unterstützt wird das Composer-v2-Protokoll.
- Keine unterstützte Migration vom Community-Composer-Plugin zur nativen Composer-Unterstützung.

Daraus wurde geschlossen: Version 3.96.3-01 erfüllt die Versionsvoraussetzung für Proxy, Hosted und Group; die Edition/Lizenz muss zusätzlich geprüft werden.

Quelle:
https://help.sonatype.com/en/composer-repositories.html

Bitte prüfe die Voraussetzungen für unsere konkrete Installation, statt allein aus der Versionsnummer auf verfügbare Funktionen zu schließen.

## Vorgeschlagene Composer-Konfiguration

Folgendes Beispiel sollte in die vorhandene `composer.json` integriert werden. Es ist keine vollständige Projektdatei und wurde nicht an unserem Projekt getestet:

```json
{
  "repositories": [
    {
      "type": "composer",
      "url": "https://nexus.example.org/repository/composer-group/"
    },
    {
      "packagist.org": false
    }
  ]
}
```

`nexus.example.org` ist ausschließlich ein Platzhalter.

Die Empfehlung war:
- Repository-Konfiguration im Projekt hinterlegen, damit lokale Entwicklung und CI dieselben Quellen verwenden.
- Bestehende direkte Drupal-Repository-Einträge durch Nexus ersetzen, sofern Nexus diese Quelle korrekt abdeckt.
- Den direkten Packagist-Zugriff erst deaktivieren, wenn Nexus alle benötigten öffentlichen Quellen bereitstellt.

Quellen:
https://help.sonatype.com/en/configure-composer-with-nexus.html
https://getcomposer.org/doc/05-repositories.md
https://www.drupal.org/docs/develop/using-composer/manage-dependencies

## Authentifizierung und Berechtigungen

Bisher empfohlen:
- HTTPS verwenden.
- Zugangsdaten außerhalb von Git halten.
- In CI über `COMPOSER_AUTH` als Secret bereitstellen.
- Lokal eine nicht eingecheckte `auth.json` verwenden.
- Build-Jobs erhalten Leserechte.
- Nur Jobs zur Veröffentlichung eigener Pakete erhalten Schreibrechte.

Es wurden keine echten Zugangsdaten, Benutzerkonten oder Berechtigungen genannt.

Quelle:
https://help.sonatype.com/en/configure-composer-with-nexus.html

## Weitere bisherige Empfehlungen

1. `composer.json` und `composer.lock` einchecken.
2. In CI und Deployment `composer install` verwenden.
3. Abhängigkeitsupdates kontrolliert in einem Branch beziehungsweise Pull Request durchführen.
4. Drupal auf Basis von `drupal/core-recommended` verwalten, sofern passend zum bestehenden Projekt.
5. PHP- und Composer-Versionen für Entwicklung und CI festlegen.
6. Eigene Pakete eindeutig benennen, beispielsweise `meinefirma/drupal-modulname`.
7. Repository-Reihenfolge und Composer-Einstellungen wie `canonical`, `only` und `exclude` bewusst prüfen, um falsche Paketquellen zu vermeiden.
8. Bei Nexus-Gruppen die tatsächliche Paketauflösung zusätzlich prüfen.
9. Das Release einmal in CI bauen und dasselbe Artefakt durch Test und Produktion ausliefern.
10. Datenbank, Uploads und Umgebungs-Secrets außerhalb des Release-Artefakts halten.

Quelle für Composer-Prioritäten:
https://getcomposer.org/doc/articles/repository-priorities.md

## Noch ausstehende technische Verifikation

Die vorherige KI empfahl einen Installationstest mit leerem Composer-Cache und eine Prüfung der tatsächlichen Download-Adressen.

Wichtige offene Punkte:
- Lädt Composer die Metadaten erfolgreich über Nexus?
- Werden auch die Paketarchive über Nexus geladen?
- Enthält die bestehende `composer.lock` weiterhin externe Download-Adressen?
- Werden zusätzliche Repository- oder Git-Quellen angesprochen?
- Funktioniert ein sauberer Build ohne vorhandenen lokalen Cache?
- Welche externen Zugriffe sind für den gewünschten Betrieb tatsächlich noch erforderlich?

Keine dieser Prüfungen wurde in dieser Unterhaltung durchgeführt.

## Auftrag an die neue KI-Session

Bitte starte mit einer konkreten Fehleranalyse. Trenne bestätigte Fakten von Annahmen und prüfe zunächst Edition, Repository-Typen und den genauen Fehler.

Bitte fordere zuerst die genaue Fehlermeldung, den auslösenden Befehl sowie die relevanten, von Zugangsdaten bereinigten Composer- und Nexus-Konfigurationen an. Leite daraus gezielte Diagnoseschritte ab. Wiederhole nicht nur die allgemeine Zielarchitektur.

## Bisherige Fehler und Lösungsstand

Die Anbindung des Drupal-/PHP-Projekts an Sonatype Nexus Repository **3.96.3-01** funktioniert nach Aussage des Nutzers weiterhin nicht.

Im vorliegenden Chat wurden keine konkreten Fehlermeldungen, Logs, HTTP-Statuscodes oder fehlgeschlagenen Composer-Befehle übermittelt. Auch bisherige Lösungsversuche und deren Ergebnisse sind nicht dokumentiert.

Die vorgeschlagene Einrichtung von Composer-Proxys, Hosted- und Group-Repositories wurde nicht als umgesetzt bestätigt. Die Nexus-Edition beziehungsweise Lizenz ist weiterhin unbekannt.

Es gibt daher bislang keine belegte Fehlerursache und keine verifizierte Lösung. Die neue Session benötigt die ursprünglichen Fehlermeldungen und bisherigen Lösungsversuche zur weiteren Diagnose.