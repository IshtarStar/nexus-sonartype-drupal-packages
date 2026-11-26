# Packagist und Drupal in Sonatype Nexus einrichten

**Die Lösung läuft vollständig in Nexus Repository Community Edition 3.96.3-01.** Entwicklung und CI erhalten eine einzige Composer-URL für Packagist-Pakete, stabile Drupal-Module und Pakete aus zwei eigenen Hosted-Repositories. Du richtest dafür auf der bestehenden Instanz die eingebauten Repository-Typen **Composer** und **Raw** ein.

## 1. Routing-Regel für Drupal anlegen

Öffne **Settings → Repository → Routing Rules → Create routing rule**. Vergib den Namen `composer-drupal-stable` und wähle als **Mode** den Wert **BLOCK**. Füge jede der folgenden Zeilen als **eigenen Matcher** hinzu und speichere die Regel.

```text
^/p2/drupal/[^/?]+~dev\.json(?:\?.*)?$
^/p2/drupal/core\.json(?:\?.*)?$
^/drupal/core/.*$
```

Die Regel gehört ausschließlich an den Drupal-Proxy. Sie filtert Drupal-Dev-Branches aus und sorgt dafür, dass Nexus sowohl die Versionsliste als auch die Archive für `drupal/core` von Packagist bezieht. Stabile Module wie `drupal/nbsp` kommen weiterhin von Drupal.org.

## 2. Paketquellen und eigene Repositories einrichten

Öffne **Settings → Repository → Repositories → Create repository**. In der Nexus-One-Oberfläche lautet der Pfad **Settings → Repositories → Create Repository**. Verwende vorhandene passende Repositories weiter. Wenn ihre Namen abweichen, übernimm eure Namen auch in den Gruppen und URLs der nächsten Schritte.

| Name | Rezept | Was du einträgst |
| --- | --- | --- |
| `composer-hosted-1` | `composer (hosted)` | Wähle den Blob Store für eure eigenen Pakete. Für unveränderliche Releases wähle **Deployment policy → Disable redeploy**. |
| `composer-hosted-2` | `composer (hosted)` | Richte das zweite interne Repository ebenso ein. |
| `composer-drupal` | `composer (proxy)` | **Remote storage** auf `https://packages.drupal.org/files/packages/8/` setzen. Unter **Routing rule** die Regel `composer-drupal-stable` auswählen. |
| `composer-packagist` | `composer (proxy)` | **Remote storage** auf `https://repo.packagist.org/` setzen. **Routing rule** leer lassen. |
| `composer-drupal-intern` | `composer (group)` | Unter **Member repositories** in dieser Reihenfolge `composer-hosted-1`, `composer-hosted-2`, `composer-drupal` auswählen. |

Die Drupal-URL mit **`/files/packages/8/`** ist wichtig. Nexus hängt `p2/` an die eingetragene Adresse an. Unter diesem Pfad liegen die von Drupal veröffentlichten Paketdaten. Packagist bleibt ein eigenständiger Proxy, weil Nexus 3.96.3-01 beim Zusammenführen seiner Versionslisten in einer Composer-Gruppe falsche Archivpfade erzeugen kann.

Eigene Pakete kannst du unter **Upload** in das jeweilige Hosted-Repository laden. Wähle das ZIP mit der `composer.json` des Pakets und gib die Version an, falls sie im Archiv fehlt.

## 3. Eine einzige URL für alle Pakete bereitstellen

Lege diese vier Repositories in der angegebenen Reihenfolge an. **`127.0.0.1:8081` bezeichnet Nexus aus Sicht des Nexus-Prozesses.** Passe Schema, Host, Port und gegebenenfalls Kontextpfad an eure Installation an. Verwende dieselbe interne Basisadresse für alle drei Remote-URLs.

| Name | Rezept | Remote Storage oder Gruppenmitglieder |
| --- | --- | --- |
| `raw-drupal-intern` | `raw (proxy)` | `http://127.0.0.1:8081/repository/composer-drupal-intern/` |
| `raw-packagist` | `raw (proxy)` | `http://127.0.0.1:8081/repository/composer-packagist/` |
| `raw-composer-quellen` | `raw (group)` | Erst `raw-drupal-intern`, dann `raw-packagist`. |
| **`composer-php`** | **`composer (proxy)`** | `http://127.0.0.1:8081/repository/raw-composer-quellen/` |

Die Raw-Gruppe liefert jede angefragte Versionsliste aus der ersten Quelle, die sie hat. Der äußere Composer-Proxy `composer-php` erzeugt daraus die Download-URLs. **An die Teams gibst du ausschließlich die externe HTTPS-Adresse von `composer-php` weiter.**

- Setze für die Abnahme auf **beiden Raw-Proxys** die Felder **Maximum component age** und **Maximum metadata age** auf **0 Minuten**. Für Raw zählt eine Versionsliste wie `p2/drupal/nbsp.json` als normale Datei. Auf den Composer-Proxys verwendete der Test **Maximum component age = -1** und **Maximum metadata age = 0**. Die strikte Inhaltsprüfung blieb eingeschaltet.
- Falls Nexus die **interne Adresse** wegen des SSRF-Schutzes ablehnt, öffne **Settings → System → API** (in Nexus One **API**). Lies `/service/rest/v1/security/ssrf-protection` mit `GET`, ergänze für das gezeigte Beispiel `127.0.0.1` in `allowedIPs` und sende das vollständige Objekt mit `PUT` zurück. Behalte die vorhandenen Einträge und den aktiven Schutz bei. Diese Ausnahme gilt instanzweit. Falls sie bei euch ausgeschlossen ist, ist der getestete Aufbau mit zwei Nexus-URLs eine Alternative. [Variante mit zwei URLs](NEXUS-ADMIN-DE.md#einfachere-variante-mit-zwei-nexus-urls)

## 4. Leserechte vergeben

Wenn anonymes Lesen deaktiviert ist, lege unter **Security → Roles / Users** ein technisches Lesekonto an. Gib ihm **browse** und **read** auf die acht inneren Repositories. Trage es bei `raw-drupal-intern`, `raw-packagist` und `composer-php` jeweils unter **HTTP Authentication → Username / Password** ein. Die öffentlichen Remote-URLs von Drupal und Packagist benötigen keine Zugangsdaten.

Entwicklung und CI brauchen mit ihrem eigenen Konto nur **browse** und **read** auf `composer-php`. Die zugehörigen Privilegien heißen `nx-repository-view-composer-composer-php-browse` und `nx-repository-view-composer-composer-php-read`.

## 5. Projektteam anschließen und Installation prüfen

Gib dem Team diesen Abschnitt für die Projekt-`composer.json` und ersetze `nexus.example.org` durch euren Nexus-Host. Vorhandene direkte Drupal- und Packagist-Einträge werden dabei durch den Nexus-Eintrag ersetzt. `packagist.org: false` deaktiviert Composers automatischen Zugriff auf das öffentliche Packagist.

```json
{
  "repositories": [
    { "type": "composer", "url": "https://nexus.example.org/repository/composer-php/" },
    { "packagist.org": false }
  ]
}
```

Führe für die Abnahme in einem frischen Testprojekt mit dieser Konfiguration die Befehle nacheinander aus. Ersetze in der dritten Zeile die Beispielnamen und Versionen durch eure beiden Hosted-Pakete.

```bash
composer --no-cache --no-plugins --no-scripts require --prefer-dist psr/log
composer --no-cache --no-plugins --no-scripts require --prefer-dist drupal/nbsp
composer --no-cache --no-plugins --no-scripts require --prefer-dist meinefirma/paket-eins:1.0.0 meinefirma/paket-zwei:1.0.0
```

Prüfe in der `composer.lock`, dass alle `dist.url` der installierten Archive mit eurer URL für `/repository/composer-php/` beginnen. Im lokalen Test mit **Composer 2.10.2** kamen **alle 68 Archive** über diesen Endpunkt, einschließlich `psr/log 3.0.2`, `drupal/nbsp 3.1.3`, Drupal Core `11.4.14` und beider Hosted-Pakete. Die Abdeckung von Drupal-Sicherheitsmeldungen durch `composer audit` ist gesondert zu prüfen. [Prüfbefehle und Testergebnisse](NEXUS-ADMIN-DE.md#6-installation-abnehmen)

Die separate Docker-Testumgebung führt die frühere Variante mit Python-Adapter vor. [Docker-Testumgebung starten](docker/README.md)
