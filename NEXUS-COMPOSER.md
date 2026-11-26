# Drupal und Packagist über Nexus Repository 3.96.3-01

Für die manuelle Einrichtung mit einer einzigen Composer-URL steht inzwischen eine geprüfte Variante ausschließlich mit eingebauten Nexus-Repositories zur Verfügung. Die Anleitung enthält die Reihenfolge der Repositories, die Leserechte und die Abnahme. [Anleitung für Nexus-Administratoren](NEXUS-ADMIN-DE.md)

## Getestete Lösung mit einer Gruppen-URL

Eine lokale Nexus Repository **Community Edition 3.96.3-01** hat mit **Composer 2.10.2** die Installation aller vier Repository-Quellen über eine einzige Composer-Gruppe bestanden. Der interaktive `composer require` installierte unter anderem `drupal/nbsp:3.1.3`, `drupal/core:11.4.14`, `psr/log:3.0.2` und je ein Paket aus den beiden Hosted-Repositories. Das Lockfile enthielt 68 Archiv-URLs, die sämtlich auf dieselbe Nexus-Gruppe zeigten. Plugins und Skripte waren beim Test deaktiviert. Auf der privaten Zielinstanz steht die Abnahme noch aus.

1. Im Drupal-Proxy **Remote Storage** auf `https://packages.drupal.org/files/packages/8/` setzen. Dort liegen Index und `p2`-Metadaten unter derselben Basis. [Alternativer Drupal-Index](https://packages.drupal.org/files/packages/8/packages.json)
2. Eine Routing-Regel im Modus **BLOCK** mit den drei folgenden Matchern anlegen und dem **Drupal-Proxy** zuweisen. Der erste Matcher schränkt die Drupal-Quelle auf Releases ein. Die anderen beiden leiten die Auswahl von `drupal/core` samt Archiv an den Packagist-Proxy weiter. [Sonatype Routing Rules](https://help.sonatype.com/en/routing-rules.html)

   ```text
   ^/p2/drupal/[^/?]+~dev\.json(?:\?.*)?$
   ^/p2/drupal/core\.json(?:\?.*)?$
   ^/drupal/core/.*$
   ```

3. Den Packagist-Metadatendienst starten und dessen Basis-URL als **Remote Storage** des Packagist-Proxys eintragen. Auf demselben Host und im selben Netzwerk-Namespace ist das `http://127.0.0.1:18097/`. Bei getrennter Ausführung die aus Nexus erreichbare interne Adresse verwenden. Der Dienst expandiert verkürzte `p2`-Datensätze der offiziellen Packagist-Quelle. Nexus lädt die Archive weiter von den jeweiligen `dist.url`-Zielen. [Packagist-Metadatendienst](packagist_metadata_proxy.py)

   ```bash
   python3 packagist_metadata_proxy.py --host 127.0.0.1 --port 18097
   ```

   Wenn Nexus die interne Adresse bei der Repository-Erstellung mit HTTP 400 wegen SSRF-Schutz ablehnt, in `GET` und `PUT /service/rest/v1/security/ssrf-protection` den konkreten Endpunkt ergänzen. Im Labortest reichte der zusätzliche Eintrag `127.0.0.1` in `allowedIPs` bei `enabled: true`. Vorhandene Einträge beim Update übernehmen. [Nexus-API 3.96.3-01](https://sonatype.github.io/sonatype-documentation/api/nexus-repository/3.96.3-01/nexus-repository-api.json)
4. Beide Hosted-Repositories und die beiden Proxy-Repositories in `composer-group` aufnehmen. Wenn die Konfiguration einer vorhandenen Gruppe umgestellt wird, die Proxy- und Gruppen-Caches invalidieren. Im Projekt-Root die [Composer-Konfiguration für die Gruppe](#composer-konfiguration-für-die-gruppe) eintragen.

Im Vergleichstest lieferte die ungefilterte Gruppe für `drupal/nbsp~dev` ein unvollständiges `dist`-Objekt. Anschließend konnten Drupal-Core-Metadaten und das Core-Archiv mit HTTP 500 abbrechen, solange der Drupal-Proxy die reine Advisory-Antwort von `drupal/core` verarbeitete. Der Packagist-Proxy mit direktem Upstream erzeugte für `drupal/core-composer-scaffold:11.4.14` eine Gruppen-`dist.url` mit Archivversion `11.4.9`. Die zwei Core-Matcher und die expandierten Packagist-Metadaten beheben diese Fälle in der getesteten Konfiguration. [Drupal-Core-Advisories](https://packages.drupal.org/files/packages/8/p2/drupal/core.json) · [Packagist-P2-Metadaten für Scaffold](https://repo.packagist.org/p2/drupal/core-composer-scaffold.json)

Für Dev-Branches aus Drupal.org und die Prüfung von Sicherheitsmeldungen eigene Bezugs- und Advisory-Quellen vorsehen. Der Installationsnachweis gilt für die geprüften stabilen Releases. [Drupal-Advisory-API](https://git.drupalcode.org/project/project_composer/-/work_items/3399877)

## Demo-Projekt mit zwei require-Aufrufen

Im Demo-Projekt lief zuerst `composer require psr/log`, danach `composer require drupal/nbsp`. Beide Befehle liefen interaktiv mit Composer 2.10.2 gegen `http://127.0.0.1:18096/repository/composer-test-expanded/`. Installiert wurden `psr/log:3.0.2`, `drupal/nbsp:3.1.3` und ihre Abhängigkeiten einschließlich `drupal/core:11.4.14`. Alle 66 Archiv-URLs im Lockfile zeigen auf dieselbe Gruppe. Das Demo-Projekt nutzt für die lokale HTTP-Adresse `secure-http: false` und deaktiviert Composer-Plugins. [Demo-Konfiguration](composer-nexus-demo/composer.json) · [Demo-Lockfile](composer-nexus-demo/composer.lock)

Zum erneuten Installieren bei laufender Testinstanz im Verzeichnis `composer-nexus-demo` `composer install` ausführen. Für eine andere Nexus-Instanz die Gruppen-URL anpassen und das Lockfile über diese Gruppe aktualisieren. Unter HTTPS kann `secure-http: false` aus der Demo-Konfiguration entfernt werden.

## Warum der Drupal-Proxy anders reagiert

| Quelle | Abruf des Index | `metadata-url` im Index |
| --- | --- | --- |
| Packagist | `https://repo.packagist.org/packages.json` | `https://repo.packagist.org/p2/%package%.json` |
| Drupal.org | `https://packages.drupal.org/8/packages.json` | `/files/packages/8/p2/%package%.json` |

Bei Drupal beginnt die Vorlage mit `/`. Composer 2 löst sie gegen Schema und Host auf und ruft für Token `https://packages.drupal.org/files/packages/8/p2/drupal/token.json` ab. Die Composer-Dokumentation verwendet selbst eine Vorlage mit führendem `/`. Der Packagist-Endpunkt hat `/p2/` direkt unter seiner Repository-Basis. [Composer-Protokoll](https://getcomposer.org/doc/05-repositories.md#metadata-url-available-packages-and-available-package-patterns) · [URL-Auflösung in Composer 2.10.3](https://github.com/composer/composer/blob/2.10.3/src/Composer/Repository/ComposerRepository.php#L1580-L1596) · [Packagist-Index](https://repo.packagist.org/packages.json) · [Drupal-Index](https://packages.drupal.org/8/packages.json)

Im nativen Composer-Modul des offiziellen Nexus-Builds **3.96.3-01** erzeugt `ComposerJsonUtils.generatePackagesJson` die clientseitige Vorlage `<Nexus-Repository>/p2/%package%.json`. `ComposerProxyFacet` reicht die Paketpfade ohne führenden Slash an `ProxyFacetSupport` weiter, der sie gegen die konfigurierte Remote-URL auflöst. Auch beim Nachschlagen der ursprünglichen `dist.url` für den Archivabruf verwendet das Composer-Modul `<Remote>/p2/...`. Die versionsgenaue Proxy-API hat ein Feld `proxy.remoteUrl` für die Basis. [Nexus-Quellcode 3.96.3-01](https://github.com/sonatype/nexus-public/blob/release-3.96.3-01/public/common/components/nexus-repository-services/src/main/java/org/sonatype/nexus/repository/proxy/ProxyFacetSupport.java#L799-L837) · [Nexus-API 3.96.3-01](https://sonatype.github.io/sonatype-documentation/api/nexus-repository/3.96.3-01/nexus-repository-api.json)

| Öffentlicher Drupal-Abruf | Ergebnis am 26.11.2026 |
| --- | --- |
| `/8/packages.json` | 200 |
| `/8/p2/drupal/token.json` | 404 nach Redirect |
| `/files/packages/8/packages.json` | 200, bytegleich mit `/8/packages.json` |
| `/files/packages/8/p2/drupal/token.json` | 200, stabile Versionen mit ZIP-URL |
| `/files/packages/8/p2/drupal/token~dev.json` | 200, aktuell `dev-1.x` mit Git-Quelle |

Der alternative Remote korrigiert damit den aus der Nexus-Implementierung ableitbaren Pfad für Index und `p2`. Der Drupal-Quellcode erzeugt den statischen Index im Metadatenverzeichnis. Die öffentliche Drupal-Anleitung nennt `/8` als Einstieg für Clients. Der Community-Entwurf schlägt einen `/8/p2/`-Endpunkt vor, der dieselben Metadaten ausliefert. [Englischer Drupal-Entwurf](DRUPAL-COMMUNITY.md) · [Drupal-Indexgenerator](https://git.drupalcode.org/project/project_composer/-/blob/b94a69c833f36d5032af7786c9113e3998adbdfb/project_composer.module#L126-132)

## Bekannte Fälle und vorhandene Lösungen

- Ein Drupal-Bericht von 2019 zu einem Nexus-Proxy wurde 2020 als nicht reproduzierbar geschlossen. Ein weiterer Drupal-Bericht beschreibt eine ähnliche Pfadauflösung bei Toran und Composer 1. Beim früheren Nexus-Community-Plugin wurde ein Packagist-spezifischer Listener als Fehlerquelle gemeldet. [Drupal #3026454](https://git.drupalcode.org/project/project_composer/-/work_items/3026454) · [Drupal #2715453](https://git.drupalcode.org/project/project_composer/-/work_items/2715453) · [Nexus-Community-Plugin #13](https://github.com/sonatype-nexus-community/nexus-repository-composer/issues/13)
- Drupal-Maintainer Mixologic hat das aktuelle `p2`-Layout und die Idee eines bedarfsbasierten Mirrors beschrieben. Private Packagist und JFrog dokumentieren Drupal als Spiegelquelle beziehungsweise Remote-Repository. Für den konkreten Drupal-Pfad in der nativen Nexus-Funktion fand ich in den Release Notes bis 3.98.3 keinen ausgewiesenen Fix. [Drupal-Mirror-Diskussion](https://www.drupal.org/project/lost_and_found_issues/issues/3091061#comment-13859663) · [Private Packagist](https://packagist.com/docs/mirrored-repositories) · [JFrog](https://docs.jfrog.com/artifactory/docs/php-composer-repositories) · [Nexus-Release-Notes](https://help.sonatype.com/en/nexus-repository-2026-release-notes.html)

## Konfiguration in Nexus

In **Settings → Repository → Repositories → Create repository** die nativen Rezepte `composer (proxy)`, `composer (hosted)` und `composer (group)` auswählen. Der Formatartikel von Sonatype nennt Cloud und self-hosted Pro, die Formatübersicht führt Composer für alle Distributionen. Der lokale Test lief auf Community Edition `3.96.3-01`. Bei einem älteren Community-Plugin dokumentiert Sonatype keine unterstützte Migration auf das native Format. [Composer-Formatartikel](https://help.sonatype.com/en/composer-repositories.html) · [Formatübersicht](https://help.sonatype.com/en/formats.html) · [Rezepte und Gruppenreihenfolge](https://help.sonatype.com/en/create-a-composer-repository.html)

| Repository | Rezept | Einstellung |
| --- | --- | --- |
| `composer-packagist` | `composer (proxy)` | Remote Storage ist die interne URL des Packagist-Metadatendiensts |
| `composer-drupal` | `composer (proxy)` | Remote Storage `https://packages.drupal.org/files/packages/8/` und die drei BLOCK-Matcher |
| `composer-hosted-1` | `composer (hosted)` | Eigenes Paket, z. B. `meinefirma/drupal-modul`. Deployment Policy **Disable redeploy** für versionierte Releases |
| `composer-hosted-2` | `composer (hosted)` | Eigenes Paket, z. B. `meinefirma/php-bibliothek`. Deployment Policy **Disable redeploy** für versionierte Releases |
| `composer-group` | `composer (group)` | Mitglieder `composer-hosted-1`, `composer-hosted-2`, `composer-drupal`, `composer-packagist` in dieser Reihenfolge |

Die Namen und die Aufteilung sind Beispiele. Beide internen Pakete können im selben Hosted-Repository liegen, wenn ihr dieselben Berechtigungen und Aufbewahrungsregeln wollt. Der Blob Store kann `default` sein, sofern ihr keinen eigenen verwendet. Uploads gehen an das jeweilige Hosted-Repository. Composer-Clients bekommen Leserechte für die konsumierten Endpunkte. Verwende für interne Pakete einen eigenen Vendor-Namespace. Gruppenreihenfolge entscheidet bei derselben Paketversion. Packagist muss auch Namen unter `drupal/*` beantworten können. Bei der Live-Abfrage lieferte Drupal für `drupal/core` ausschließlich Advisories und für `drupal/core-recommended` einen 404. Die Versionen kamen bei beiden Namen von Packagist. [Gruppenregeln](https://help.sonatype.com/en/create-a-composer-repository.html) · [Drupal-Core-Advisories](https://packages.drupal.org/files/packages/8/p2/drupal/core.json) · [Packagist-Core](https://repo.packagist.org/p2/drupal/core.json) · [Packagist-Core-Recommended](https://repo.packagist.org/p2/drupal/core-recommended.json)

Für jedes Hosted-Paket ein ZIP mit gültiger `composer.json` im Archiv erstellen. Das Beispiel setzt die Paketversion in dieser Datei. Wenn die Version dort fehlt, die Version per `?version=1.0.0` angeben. `curl --user "$NEXUS_USER"` fragt das Passwort interaktiv ab. Für CI die Zugangsdaten als Secret bereitstellen. [Sonatype CLI-Anleitung für Composer](https://help.sonatype.com/en/composer-cli-usage.html#upload-with-http-put)

```bash
NEXUS_URL=https://nexus.example.org
NEXUS_USER=mein-publish-benutzer

curl --fail-with-body --user "$NEXUS_USER" --request PUT \
  --header 'Content-Type: application/zip' \
  --data-binary @drupal-modul-1.0.0.zip \
  "$NEXUS_URL/repository/composer-hosted-1/"

curl --fail-with-body --user "$NEXUS_USER" --request PUT \
  --header 'Content-Type: application/zip' \
  --data-binary @php-bibliothek-1.0.0.zip \
  "$NEXUS_URL/repository/composer-hosted-2/"
```

In 3.96.3-01 können Hosted-Metadaten das Feld `extra` verlieren. Wenn eines eurer Pakete `extra` für die Installation braucht, gehört dieses Feld in die Abnahme. Für diesen Fehler nennt der Maintainer 3.98 als erwartete Fix-Version. [Sonatype #1074](https://github.com/sonatype/nexus-public/issues/1074)

## Composer-Konfiguration für die Gruppe

Nach bestandener Abnahme die Gruppen-URL im `repositories`-Abschnitt des Projekt-Roots eintragen und den bisherigen direkten Drupal-Eintrag ersetzen. Projektspezifische Quellen bei Bedarf weiter aufführen. `packagist.org: false` deaktiviert das implizite öffentliche Packagist, sobald der Nexus-Proxy im Projekt vollständig getestet ist. `nexus.example.org` steht stellvertretend für eure HTTPS-Adresse. [Composer-Repository-Konfiguration](https://getcomposer.org/doc/05-repositories.md#disabling-packagist-org) · [Nexus-Client-Konfiguration](https://help.sonatype.com/en/configure-composer-with-nexus.html)

```json
{
  "repositories": [
    { "type": "composer", "url": "https://nexus.example.org/repository/composer-group/" },
    { "packagist.org": false }
  ]
}
```

## Ursache des ursprünglichen Require-Abbruchs

Der Test auf der Nexus-Gruppe zeigt HTTP 200 für `p2/drupal/nbsp.json` und `p2/drupal/nbsp~dev.json`. Beim interaktiven `composer --no-cache require drupal/nbsp -vvv` bricht Composer 2.10.2 trotzdem ab. Die Gruppe liefert für `dev-1.x` ein `dist` mit einer Nexus-URL und ohne `type`. Drupal liefert für diese Version eine Git-Quelle ohne `dist`. Der Fehler tritt beim Einlesen der Metadaten auf, vor dem ZIP-Download. Die dauerhafte Korrektur gehört zu Sonatype. Nexus sollte die `dist.url` nur für vorhandene, gültige Archive umschreiben und die Git-Quelle bei reinen Git-Versionen erhalten. [Drupal-Dev-Metadaten](https://packages.drupal.org/files/packages/8/p2/drupal/nbsp~dev.json) · [Composer ArrayLoader 2.10.2](https://github.com/composer/composer/blob/2.10.2/src/Composer/Package/Loader/ArrayLoader.php#L200-L212)

Falls die Gruppen-Konfiguration kurzfristig nicht umgestellt werden kann, lässt sich für die stabile Version dieser Aufruf testen. Ein separater Test mit Composer 2.10.2 und nachgebildeter fehlerhafter Gruppen-Antwort bestätigte die Kombination aus exakter Version und `--no-interaction`. Bei Erfolg kannst du `--dry-run` für die Installation entfernen. [Interaktive Paketprüfung in Composer 2.10.2](https://github.com/composer/composer/blob/2.10.2/src/Composer/Command/RequireCommand.php#L229-L247)

```bash
composer --no-cache --no-interaction require 'drupal/nbsp:3.1.3' --dry-run -vvv
```

Falls der reguläre interaktive Aufruf gebraucht wird und der Client auf Drupal.org zugreifen darf, das einzelne Paket direkt bei Drupal beziehen und es in jedem betroffenen Nexus-Repository-Eintrag ausfiltern. Das funktionierte im interaktiven Test mit der nachgebildeten Gruppen-Antwort. Die anderen Pakete einschließlich `drupal/core` laufen weiter über die Gruppe. `nexus.example.org` und den Gruppenpfad durch die Werte deiner Instanz ersetzen. [Composer-Repository-Filter](https://getcomposer.org/doc/articles/repository-priorities.md#filtering-packages)

```json
{
  "repositories": [
    {
      "type": "composer",
      "url": "https://packages.drupal.org/8",
      "only": ["drupal/nbsp"]
    },
    {
      "type": "composer",
      "url": "https://nexus.example.org/repository/composer-group/",
      "exclude": ["drupal/nbsp"]
    },
    { "packagist.org": false }
  ]
}
```

## Abnahme für Proxy, Gruppe und vorhandenes Lockfile

Der vollständige Labortest umfasste einen leeren Composer-Cache und neue Repositories. Nexus nahm beide Hosted-Uploads mit HTTP 201 an und Composer installierte `example-lab/fixture-1:1.0.0` sowie `example-lab/fixture-2:1.0.0` aus der Gruppe. Die folgenden Schritte übertragen die Abnahme auf die Zielinstanz.

1. `composer-drupal` einzeln testen. `packages.json` abrufen und die darin ausgegebene `metadata-url` prüfen. `p2/drupal/nbsp.json` muss `packages["drupal/nbsp"]` mit der erwarteten Version liefern. `p2/drupal/nbsp~dev.json` ergibt durch die BLOCK-Regel am Drupal-Proxy HTTP 403. In der Gruppe ergibt der Pfad HTTP 404, sofern kein anderes Mitglied ihn liefert. [Nexus-Caches](https://help.sonatype.com/en/repository-management.html) · [Gruppierung der Metadaten in Nexus 3.96.3-01](https://github.com/sonatype/nexus-public/blob/release-3.96.3-01/public/common/components/nexus-repository-services/src/main/java/org/sonatype/nexus/repository/group/MergingGroupHandlerSupport.java#L106-L132)
2. Dieselben Requests durch `composer-group` ausführen. Zusätzlich `p2/drupal/core-recommended.json`, `p2/drupal/core.json`, `p2/psr/log.json` und die beiden Hosted-Paketnamen auf tatsächlich vorhandene Versionen prüfen. Das trennt Fehler im Proxy von Fehlern beim Zusammenführen der Mitglieder.
3. Die `dist.url` aus den Metadaten einer konkreten Version per **GET** herunterladen. Für `drupal/token:1.18.0` kommt upstream ein ZIP von `ftp.drupal.org`. Dessen SHA-1 entspricht `7db67f644c83136cac78c7c5dbaef29599e7a7d7` aus den Drupal-Metadaten. Bei gewünschten Downloads allein über Nexus müssen die Gruppen-URL sowie Ziel und Redirects des Downloads zum Netzwerkmodell passen. Ein Dev-Eintrag mit ausschließlich `source` braucht Git oder einen dafür vorgesehenen internen Mirror. Der untersuchte Nexus-Proxy-Code entfernt `source` beim Umschreiben der Paketmetadaten. Ein erfolgreicher `~dev.json`-Abruf reicht damit für solche Versionen nicht aus. [Token-Metadaten](https://packages.drupal.org/files/packages/8/p2/drupal/token.json) · [Separater Nexus-Bericht zu Dev-Archiven in Gruppen](https://community.sonatype.com/t/title-composer-group-generates-incorrect-dist-url-for-dev-master-package-in-nexus-repository-3-96-0-09/16795)
4. Advisory-Abdeckung eigenständig prüfen. Die Implementierung in 3.96.3-01 erzeugt den Proxy- und Gruppenindex ohne die Advisory-API-Deklaration der Upstreams. Der Gruppen-Merge überspringt reine Advisory-Antworten ohne Versionen, wie Drupal sie für `drupal/core` ausliefert. `drupal/mollie` eignet sich zum Vergleich eines Datensatzes mit Versionen und Advisories. Wenn eure Gruppe die benötigten Advisories nicht an Composer liefert, Drupal und Packagist über die vorgesehenen Advisory-Quellen im Sicherheitscheck abdecken. [Drupal-Advisory-API](https://git.drupalcode.org/project/project_composer/-/work_items/3399877) · [Drupal-Metadaten für Mollie](https://packages.drupal.org/files/packages/8/p2/drupal/mollie.json)
5. In einem Test-Checkout `composer --no-cache update --lock --no-install -vvv` ausführen und den Diff des Lockfiles auf Paketversionen und `dist.url`/`source.url` prüfen. Danach mit leerem Installationsverzeichnis `composer --no-cache install --prefer-dist -vvv` ausführen und die aufgerufenen Hosts inklusive Git-Zugriffen prüfen. Führe anschließend `composer audit --locked` mit den vorgesehenen Advisory-Quellen aus. Bestehende Lockfiles können externe Archiv-URLs enthalten. [Composer-CLI](https://getcomposer.org/doc/03-cli.md#update-u-upgrade)

Beispiel für die Metadaten- und Archivprüfung. Für eine geschützte Instanz bei `curl` eure Leseauthentifizierung verwenden. Die Beispiele setzen voraus, dass der ausgewählte Eintrag seine `dist`-Daten explizit enthält, wie bei Token 1.18.0.

```bash
repo=https://nexus.example.org/repository/composer-group

curl -fsS "$repo/packages.json" | jq -er '."metadata-url"'
dist_url=$(curl -fsS "$repo/p2/drupal/token.json" | jq -er '
  .packages["drupal/token"][] | select(.version == "1.18.0") | .dist.url
')
printf '%s\n' "$dist_url"

# Nur nach Prüfung der URL auf den erwarteten Host abrufen.
curl -fsS -o token-1.18.0.zip -w 'HTTP %{http_code} · Redirect %{redirect_url}\n' "$dist_url"
unzip -t token-1.18.0.zip
shasum -a 1 token-1.18.0.zip
```

Bei funktionierendem `p2` und einem Fehler erst am Archiv auch dessen Inhalt prüfen. Im öffentlichen Archiv für `drupal/admin_toolbar:1.0.0` fehlt beispielsweise eine `composer.json`. Für solche Archive gibt es einen separaten Nexus-Fehlerbericht. [Sonatype #1072](https://github.com/sonatype/nexus-public/issues/1072)

## Ausweichkonfiguration mit direktem Drupal-Repository

Wenn direkter Drupal-Zugriff möglich ist, `composer-group` aus den beiden Hosted-Repositories und dem Packagist-Proxy bilden. Drupal in Composer davor eintragen. `only` beschränkt diesen Eintrag auf Drupal-Paketnamen. Die darunter stehende Nexus-Gruppe liefert die Versionen für Core und die Core-Begleitpakete, falls Drupal dafür keine Paketversionen anbietet. Ein isolierter Test mit Composer 2.10.3 hat diese Auflösung und die Drupal-Advisory-API mit direktem Packagist als Kontrollquelle bestätigt. Die Gruppe ist auf deiner Instanz als Packagist-Ersatz zu prüfen. [Composer-Repository-Prioritäten](https://getcomposer.org/doc/articles/repository-priorities.md) · [Drupal-Referenzprojekt](https://github.com/drupal/drupal/blob/11.x/composer/Template/RecommendedProject/composer.json)

```json
{
  "repositories": [
    {
      "type": "composer",
      "url": "https://packages.drupal.org/8",
      "only": ["drupal/*"]
    },
    { "type": "composer", "url": "https://nexus.example.org/repository/composer-group/" },
    { "packagist.org": false }
  ]
}
```

Diese Variante setzt Client-Zugriff auf `packages.drupal.org`, für stabile Drupal-Archive auf `ftp.drupal.org` und für Drupal-Git-Installationen auf `git.drupalcode.org` voraus. Falls ausschließlich Nexus erreichbar sein darf und der statische Drupal-Pfad künftig entfällt, kann ein interner Reverse Proxy als Nexus-Upstream einen eigenen `/packages.json` mit der Vorlage `/p2/%package%.json` ausliefern und `/p2/drupal/` auf Drupals `/files/packages/8/p2/drupal/` abbilden. Solch ein Adapter löst die Pfadzuordnung. Archivverarbeitung, Git und Advisory-Abdeckung hängen weiterhin von Nexus beziehungsweise den dafür vorgesehenen Diensten ab.
