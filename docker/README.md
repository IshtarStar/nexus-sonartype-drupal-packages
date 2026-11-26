# Drupal und Packagist über Sonatype Nexus mit Docker Compose

Der Docker-Stack demonstriert die Variante mit Python-Adapter. Die manuelle Einrichtung einer bestehenden Nexus-Instanz mit ausschließlich eingebauten Repository-Typen steht in der Projekt-README. [Anleitung für die Nexus-Administration](../README.md)

Mit diesem Projekt kannst du `composer require psr/log` und `composer require drupal/nbsp` über **dieselbe Nexus-Gruppe** ausführen. Die Gruppe enthält einen Packagist-Proxy, einen Drupal-Proxy und zwei Hosted-Repositories für eigene Pakete. Der Test verwendet Nexus Repository Community Edition **3.96.3-01** und Composer **2.10.2**. [Docker-Compose-Datei](../docker-compose.yml)

## Stack starten und Installation testen

Du brauchst Docker mit Compose und Internetzugriff für den ersten Image-Build und die Paketdownloads. PHP und Composer sind im Testcontainer enthalten. Führe die Befehle im Projektstamm aus, in dem die `docker-compose.yml` liegt. Mit der ersten Zeile stimmst du für diese lokale Nexus-Instanz den Lizenzbedingungen der Community Edition zu. [Sonatype-Lizenzbedingungen](https://links.sonatype.com/products/nxrm/ce-eula)

```bash
export NEXUS_ACCEPT_EULA=true
docker compose up -d
docker compose run --rm --build composer-test
```

Der erste Start kann einige Minuten dauern. Der Dienst `bootstrap` richtet die Repositories ein, lädt je ein Testpaket in die beiden Hosted-Repositories und beendet sich mit Exit-Code 0. Der Composer-Test wartet auf die abgeschlossene Einrichtung. Den Status siehst du mit `docker compose ps -a`, das Einrichtungsprotokoll mit `docker compose logs bootstrap`.

| Zugriff vom Host | Adresse |
| --- | --- |
| Nexus-Oberfläche | `http://127.0.0.1:8081/` |
| Composer-Gruppe | `http://127.0.0.1:8081/repository/composer-group/` |

Die Gruppe erlaubt im lokalen Test anonymes Lesen. Für die Verwaltung meldest du dich als `admin` an. Das generierte Startpasswort kannst du mit `docker compose exec nexus cat /nexus-data/admin.password` anzeigen. Ist Port 8081 belegt, setze vor dem Start zum Beispiel `export NEXUS_PORT=18081` und verwende diesen Port in den Host-Adressen.

Änderst du das Admin-Passwort in der Oberfläche, braucht `bootstrap` beim nächsten Lauf das neue Passwort. Binde dafür eine Datei mit dem neuen Passwort über eine lokale `docker-compose.override.yml` schreibgeschützt in den Dienst `bootstrap` ein und setze dort `NEXUS_ADMIN_PASSWORD_FILE` auf ihren Pfad im Container.

## Was der Test prüft

Der Test beginnt bei jedem Aufruf in einem neuen Composer-Projekt mit deaktiviertem öffentlichem Packagist und leerem Composer-Cache. Er installiert zuerst `psr/log`, danach `drupal/nbsp` einschließlich Drupal Core. Ein dritter Aufruf installiert `example-lab/fixture-1:1.0.0` und `example-lab/fixture-2:1.0.0` aus den beiden Hosted-Repositories.

Der Test prüft für jedes installierte Paket, ob es aus einem Archiv kam und ob seine `dist.url` im Lockfile auf die Nexus-Gruppe zeigt. Bei `drupal/core` und `drupal/core-composer-scaffold` muss außerdem die Version im Archivpfad zur aufgelösten Version passen. Plugins und Projektskripte sind für diesen Installationstest deaktiviert. [Testskript](test-composer.sh)

Im Docker-Test auf ARM64 am 26. November 2026 kamen **alle 68 Archive** über die Gruppe. Installiert wurden `psr/log 3.0.2`, `drupal/nbsp 3.1.3`, Drupal Core und Scaffold jeweils in Version `11.4.14` sowie beide Hosted-Pakete in Version `1.0.0`. Die beiden öffentlichen Paketnamen werden bei jedem Test neu aufgelöst. Die Versionen und die Paketanzahl können sich bei späteren Läufen ändern.

## So löst die Konfiguration das Drupal-Problem

Drupal veröffentlicht in `packages.json` die gültige Composer-2-Vorlage `/files/packages/8/p2/%package%.json`. Nexus 3.96.3-01 hängt beim Abruf selbst `p2/` an die konfigurierte Remote-URL an. Mit Drupals dokumentiertem Einstieg `/8/` führt das für `drupal/nbsp` zu einem HTTP 404. Für die Installation müssen außerdem gültige Versionsdaten und die passenden Archive durch die Gruppe kommen. [Drupal-Index](https://packages.drupal.org/8/packages.json) · [Composer-Repository-Protokoll](https://getcomposer.org/doc/05-repositories.md#metadata-url-available-packages-and-available-package-patterns)

| Einstellung in Nexus | Wert und Wirkung |
| --- | --- |
| Remote Storage von `composer-drupal` | `https://packages.drupal.org/files/packages/8/` stellt Index und Paketmetadaten unter der von Nexus erwarteten Basis bereit. |
| BLOCK-Routingregel am Drupal-Proxy | Filtert Drupal-`~dev.json`, für die Nexus unvollständige Archivangaben erzeugen kann. Sie sperrt auch die Metadaten und Archivpfade für `drupal/core` an diesem Proxy. Dadurch bezieht die Gruppe Core von Packagist, während Drupal.org die stabilen Contrib-Releases wie NBSP liefert. |
| Remote Storage von `composer-packagist` | `http://127.0.0.1:18097/` erreicht den Python-Adapter im Netzwerk-Namespace von Nexus. Er expandiert verkürzte Packagist-Metadaten, damit Nexus pro Version die richtige Archiv-URL erzeugt. Der SSRF-Schutz bleibt aktiv und erlaubt für den Adapter die Loopback-IP. |
| Mitglieder von `composer-group` | `composer-hosted-1`, `composer-hosted-2`, `composer-drupal`, `composer-packagist` in dieser Reihenfolge. |

Die Konfiguration ist für stabile Drupal-Releases ausgelegt. Drupal-Dev-Branches sind am Drupal-Proxy ausgefiltert. Die Abdeckung von Security Advisories durch `composer audit` ist separat zu prüfen. Die genauen Routing-Ausdrücke, die manuelle Einrichtung und die Ergebnisse der Vergleichstests stehen in der ausführlichen Anleitung. [Manuelle Konfiguration](../NEXUS-COMPOSER.md) · [Packagist-Adapter](../packagist_metadata_proxy.py)

## Ein eigenes Composer-Projekt anschließen

Ergänze im Projekt auf deinem Host die folgenden Abschnitte in der `composer.json`. Ersetze einen vorhandenen direkten Drupal-Eintrag durch die Gruppen-URL. Die Ausnahme `secure-http: false` gilt hier für das lokale HTTP-Testprojekt. Für eine per HTTPS erreichbare Nexus-Instanz genügt der Abschnitt `repositories`.

```json
{
  "repositories": [
    { "type": "composer", "url": "http://127.0.0.1:8081/repository/composer-group/" },
    { "packagist.org": false }
  ],
  "config": {
    "secure-http": false
  }
}
```

```bash
composer require psr/log
composer require drupal/nbsp
```

Container desselben Compose-Projekts erreichen die Gruppe intern unter `http://nexus:8081/repository/composer-group/`. Das vorhandene Demo-Projekt samt Lockfile verweist auf die frühere Testinstanz auf Port 18096. Der oben beschriebene Container-Test erzeugt sein Lockfile jeweils neu mit der Adresse des Compose-Stacks. [Demo-Projekt](../composer-nexus-demo/composer.json)

## Stack stoppen

```bash
docker compose down
```

Die Repositories, Testpakete und zwischengespeicherten Archive liegen im benannten Volume `nexus-data` und stehen beim nächsten Start wieder zur Verfügung.
