# Composer-2-Paketmetadaten unter `/8/p2/` bereitstellen

Ich nutze eine Nexus-Gruppe für Packagist, Drupal.org-Contrib und intern gehostete Pakete. Die dokumentierte URL `https://packages.drupal.org/8/` soll als Remote Storage für den Drupal-Proxy verwendbar sein. Nexus `3.96.3-01` erwartet `packages.json` und `p2/` unter derselben Basis-URL. Der von Drupal veröffentlichte Pfad ab der Domainwurzel ist für Composer 2 gültig. Ein `/8/p2/`-Endpunkt würde die dokumentierte URL auch für Proxys mit derselben Pfadannahme zugänglich machen. [Drupal Composer Guide](https://www.drupal.org/docs/develop/using-composer/using-packagesdrupalorg) · [Composer-Repository-Protokoll](https://getcomposer.org/doc/05-repositories.md#metadata-url-available-packages-and-available-package-patterns)

## Vorgeschlagene Änderung auf Drupal.org

- `/8/p2/drupal/<package>.json` und `/8/p2/drupal/<package>~dev.json` aus denselben bestehenden Dateien wie `/files/packages/8/p2/` ausliefern. Die Zuordnung kann am Drupal.org-Edge erfolgen und erfolgreiche Anfragen mit HTTP 200 beantworten.
- Für beide Pfade denselben Cache-Schlüssel verwenden oder bei einer Aktualisierung beide Pfade invalidieren. Der Generator invalidiert derzeit den `/files/`-Pfad. `ETag`, `Last-Modified`, bedingte GETs und HTTP 404 für unbekannte Pakete sollen für beide Pfade konsistent sein. [Metadaten-Generator und Cache-Invalidierung](https://git.drupalcode.org/project/project_composer/-/blob/b94a69c833f36d5032af7786c9113e3998adbdfb/project_composer.module#L1698-1716)
- Sobald der Pfad verfügbar ist, `/8/` als Proxy-Upstream dokumentieren. Drupal kann nach einem Kompatibilitätstest auch `/8/p2/%package%.json` als `metadata-url` ankündigen. [Using packages.drupal.org](https://www.drupal.org/docs/develop/using-composer/using-packagesdrupalorg)

Die Drupal-Änderung deckt die Pfadauflösung ab. Damit die native Nexus-Gruppe ohne lokale Anpassungen funktioniert, müssen auch die nachfolgenden Nexus-Fehler behoben werden.

## Metadaten bei Packagist und Drupal.org

`https://repo.packagist.org/packages.json` gibt `https://repo.packagist.org/p2/%package%.json` als Vorlage an. `https://packages.drupal.org/8/packages.json` gibt `/files/packages/8/p2/%package%.json` an. Composer 2 löst den führenden Slash relativ zum Host auf, sodass die dokumentierte Drupal-URL funktioniert. Ein Repository-Manager, der `p2/drupal/token.json` relativ zu `https://packages.drupal.org/8/` auflöst, erhält für den entstehenden Pfad HTTP 404. [Drupal-Index](https://packages.drupal.org/8/packages.json) · [Packagist-Index](https://repo.packagist.org/packages.json) · [Composer-2-Repository-Protokoll](https://getcomposer.org/doc/05-repositories.md#metadata-url-available-packages-and-available-package-patterns)

## Reproduktion mit den öffentlichen Endpunkten

```bash
curl -fsS https://packages.drupal.org/8/packages.json | jq -r '."metadata-url"'

for path in \
  /8/p2/drupal/token.json \
  /files/packages/8/packages.json \
  /files/packages/8/p2/drupal/token.json \
  /files/packages/8/p2/drupal/token~dev.json; do
  curl -sSL -o /dev/null -w '%{http_code} %{url_effective}\n' \
    "https://packages.drupal.org$path"
done

diff -u <(curl -fsS https://packages.drupal.org/8/packages.json) \
  <(curl -fsS https://packages.drupal.org/files/packages/8/packages.json)
```

Am 26. November 2026 lieferten die Abrufe in der Schleife nacheinander `404`, `200`, `200` und `200`. Beide Indexdateien waren bytegleich. Composer 2.10.3 konnte `drupal/token:1.18.0` mit beiden URLs auflösen. In einem frischen Testprojekt mit der alternativen URL und Packagist wurden außerdem Token `1.18.0` aus dem Release-ZIP und Drupal Core `11.4.14` installiert. Plugins und Skripte waren dabei deaktiviert. Die alternative URL legt die Paketmetadaten dort bereit, wo ein Proxy mit fest angehängtem `p2/` sie sucht. Drupal erzeugt `packages.json` im selben Verzeichnis wie die Paketmetadaten. [Drupal-Indexgenerator](https://git.drupalcode.org/project/project_composer/-/blob/b94a69c833f36d5032af7786c9113e3998adbdfb/project_composer.module#L126-132)

## Pfadauflösung im Nexus-Proxy

Im nativen Composer-Format von Nexus `3.96.3-01` erzeugt der Proxy eine eigene `metadata-url` unter `/p2/` und löst Paketmetadaten relativ zur konfigurierten Remote-Storage-URL auf. Bei der Suche nach einem Archiv liest Nexus ebenfalls Upstream-Metadaten unter `/p2/`. Die statische Drupal-URL passt zu beiden Abrufen. Eine allgemeine Korrektur in Nexus könnte in beiden Fällen die `metadata-url` des Upstreams auswerten und mit `/` beginnende Pfade relativ zum Host auflösen. [URL-Auflösung im Nexus-Proxy](https://github.com/sonatype/nexus-public/blob/release-3.96.3-01/public/common/components/nexus-repository-services/src/main/java/org/sonatype/nexus/repository/proxy/ProxyFacetSupport.java#L799-L837) · [Nexus-API für 3.96.3-01](https://sonatype.github.io/sonatype-documentation/api/nexus-repository/3.96.3-01/nexus-repository-api.json)

## Composer require scheitert an einem erzeugten dist-Eintrag

Der erste interaktive Aufruf `composer --no-cache require drupal/nbsp -vvv` mit Composer `2.10.2` und PHP `8.5.7` erhielt beim Abruf von `p2/drupal/nbsp~dev.json` aus der Gruppe HTTP 200. Composer brach danach im `ArrayLoader` ab, bevor es ein Archiv abrief. Für `dev-1.x` meldete Composer ein `dist`-Objekt, das nur eine von Nexus erzeugte URL enthielt. Der Drupal-Upstream liefert für diesen Branch ausschließlich eine Git-Quelle mit URL und Referenz. Eine lokale Gruppe in Nexus Community Edition `3.96.3-01` reproduzierte den Fehler ohne Filter. Sobald ein `dist`-Objekt enthalten ist, erwartet Composer darin mindestens `type` und `url`. [Drupal-Dev-Metadaten für NBSP](https://packages.drupal.org/files/packages/8/p2/drupal/nbsp~dev.json) · [ArrayLoader in Composer 2.10.2](https://github.com/composer/composer/blob/2.10.2/src/Composer/Package/Loader/ArrayLoader.php#L200-L212)

Nexus sollte beim Abruf der Paketmetadaten und beim Nachschlagen von Archiven die `metadata-url` des Upstreams auswerten. Nexus sollte `dist.url` nur für vorhandene Archive mit Typ und URL umschreiben und bei reinen Git-Versionen die nutzbare `source` erhalten. Antworten mit Advisories und ohne `packages` müssen ohne Fehler verarbeitet werden, damit Core-Versionen aus Packagist aufgelöst werden. Minifizierte Composer-2-Datensätze müssen vor dem Umschreiben der Archiv-URLs vollständig expandiert werden. [Verwandtes Sonatype-Issue #1046](https://github.com/sonatype/nexus-public/issues/1046)

## Getesteter Workaround für Nexus 3.96.3-01

- Eine Routing-Regel am Drupal-Proxy blockierte Anfragen auf Drupal-`~dev.json`. Der Proxy antwortete für blockierte Anfragen mit HTTP 403 und die Gruppe mit HTTP 404. Composer konnte mit den stabilen Versionen fortfahren.
- Der Drupal-Proxy blockierte außerdem `p2/drupal/core.json` und Pfade unter `drupal/core/`. Die Gruppe konnte dadurch sowohl die Core-Metadaten als auch das Archiv über Packagist beziehen. Der Drupal-Endpunkt liefert ausschließlich Security Advisories. Beim Versuch, das Core-Archiv über den Drupal-Proxy zu beziehen, antwortete Nexus mit HTTP 500 und einer `NullPointerException`. [Drupal-Core-Advisories](https://packages.drupal.org/files/packages/8/p2/drupal/core.json) · [Drupal-Issue zur Advisory-API](https://git.drupalcode.org/project/project_composer/-/work_items/3399877)
- Ein Metadaten-Adapter vor Packagist expandierte die minifizierten Composer-2-Paketdaten. Dadurch erhielt `drupal/core-composer-scaffold:11.4.14` in der Gruppe den korrekten Downloadpfad für `11.4.14`. Zuvor hatte die Gruppe dafür den Pfad für `11.4.9` geliefert. [Composer Metadata Minifier](https://github.com/composer/metadata-minifier/blob/main/src/MetadataMinifier.php)

Ein interaktiver Lauf mit Composer `2.10.2` über eine einzige Nexus-Gruppe installierte `drupal/nbsp:3.1.3`, `psr/log:3.0.2`, `drupal/core:11.4.14` und zwei Pakete, die in getrennte Hosted Repositories hochgeladen worden waren. Alle 68 Archiv-URLs im Lockfile führten zu dieser Gruppe. Das darüber geladene NBSP-ZIP hatte die von Drupal veröffentlichte SHA-1-Prüfsumme `18753c9a56daf92784db328dd5c1cb1a2434618c`. Damit ist die Installation stabiler Versionen für die getesteten Pakete bestätigt. Drupal-Dev-Branches und die Abdeckung der Advisory-Daten müssen separat geprüft werden. [Drupal-Metadaten für das NBSP-Release](https://packages.drupal.org/files/packages/8/p2/drupal/nbsp.json)

In der Drupal-Issue-Queue finden sich frühere Proxy-Probleme mit Toran und Nexus. Die Diskussion über Composer-2-Mirrors beschreibt die aktuellen `p2`-Pfade und das Spiegeln von Paketen bei Bedarf. [Toran-Bericht #2715453](https://git.drupalcode.org/project/project_composer/-/work_items/2715453) · [Nexus-Bericht #3026454](https://git.drupalcode.org/project/project_composer/-/work_items/3026454) · [Diskussion zu Drupal-Mirrors](https://www.drupal.org/project/lost_and_found_issues/issues/3091061#comment-13859663)

## Abnahmetests

1. Auf Drupal.org `/8/packages.json`, `/8/p2/drupal/nbsp.json`, `/8/p2/drupal/nbsp~dev.json` und `/8/p2/drupal/core.json` prüfen. Die Paketdaten und Core-Advisories müssen den bisherigen Pfaden entsprechen. Unbekannte Pakete sollen HTTP 404 liefern. Bedingte GETs und die Aktualisierung beider Pfade nach einer Metadatenänderung prüfen.
2. In einer korrigierten Nexus-Version zwei native Proxys mit `https://packages.drupal.org/8/` und `https://repo.packagist.org/` anlegen und in einer Gruppe zusammenfassen. In einem frischen Composer-Projekt mit ausschließlich dieser Gruppe und deaktiviertem impliziten Packagist nacheinander `composer --no-cache require psr/log -vvv` und `composer --no-cache require drupal/nbsp -vvv` ausführen.
3. Archivabrufe über die Gruppe, NBSP-Prüfsumme, Git-only-Metadaten und Advisory-Abdeckung prüfen. Für diese Abnahme die öffentlichen Upstreams direkt konfigurieren, ohne Filter, Adapter oder fest vorgegebene Paketversionen.

Können die Maintainer von packages.drupal.org `/8/p2/` als Kompatibilitäts-Endpunkt unterstützen? Ich kann die HTTP-Prüfungen und ein Composer-Testprojekt beisteuern. Falls die Zuordnung am Edge umgesetzt werden soll, kann ich ein verknüpftes Infrastruktur-Issue eröffnen. [Drupal.org Infrastructure](https://www.drupal.org/project/infrastructure)
