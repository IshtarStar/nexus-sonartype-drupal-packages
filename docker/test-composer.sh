#!/bin/sh
set -eu

NEXUS_GROUP_URL=${NEXUS_GROUP_URL:-http://nexus:8081/repository/composer-group/}
export NEXUS_GROUP_URL="${NEXUS_GROUP_URL%/}/"

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
export COMPOSER_HOME="$workdir/composer-home"
mkdir "$workdir/project"
cd "$workdir/project"

php > composer.json <<'PHP'
<?php
$group = getenv('NEXUS_GROUP_URL');
echo json_encode([
    'name' => 'example/nexus-smoke-test',
    'repositories' => [
        ['type' => 'composer', 'url' => $group],
        ['packagist.org' => false],
    ],
    'config' => [
        'allow-plugins' => false,
        'secure-http' => !str_starts_with($group, 'http://'),
        'source-fallback' => false,
    ],
], JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), "\n";
PHP

require_packages() {
    composer --no-cache --no-plugins --no-scripts require --prefer-dist --no-progress "$@"
}

require_packages psr/log
require_packages drupal/nbsp
require_packages example-lab/fixture-1:1.0.0 example-lab/fixture-2:1.0.0

php <<'PHP'
<?php
$group = getenv('NEXUS_GROUP_URL');
$lock = json_decode(file_get_contents('composer.lock'), true, 512, JSON_THROW_ON_ERROR);
$packages = array_column(array_merge($lock['packages'], $lock['packages-dev']), null, 'name');
$manifest = json_decode(file_get_contents('vendor/composer/installed.json'), true, 512, JSON_THROW_ON_ERROR);
$installed = array_column($manifest['packages'], null, 'name');
foreach ($packages as $name => $package) {
    $url = $package['dist']['url'] ?? '';
    if (!str_starts_with($url, $group)) {
        throw new RuntimeException("Unerwartete Archiv-URL für $name: $url");
    }
    if (($installed[$name]['installation-source'] ?? null) !== 'dist') {
        throw new RuntimeException("$name wurde nicht aus einem Archiv installiert.");
    }
}

foreach (['psr/log', 'drupal/nbsp', 'drupal/core', 'drupal/core-composer-scaffold',
          'example-lab/fixture-1', 'example-lab/fixture-2'] as $name) {
    if (!isset($packages[$name])) {
        throw new RuntimeException("$name fehlt im Lockfile.");
    }
    echo "$name ", $packages[$name]['version'], "\n";
}

foreach (['drupal/core', 'drupal/core-composer-scaffold'] as $name) {
    $version = $packages[$name]['version'];
    $url = $packages[$name]['dist']['url'];
    if (!str_starts_with($url, "$group$name/$version/")) {
        throw new RuntimeException("Archivpfad passt nicht zu $name $version: $url");
    }
}

echo count($packages), " Pakete aus Archiven installiert, alle Lockfile-URLs unter $group\n";
PHP
