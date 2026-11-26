# Serve Composer 2 package metadata under `/8/p2/`

I’m using a Sonatype Nexus Repository group for Packagist, Drupal.org contrib and internally hosted packages. I would like repository admins to be able to use the documented `https://packages.drupal.org/8/` URL as their Drupal upstream. Nexus `3.96.3-01` expects `packages.json` and `p2/` under the same base URL. Drupal’s current path from the domain root is valid for Composer 2. Serving the existing package files under `/8/p2/` would make the documented base URL usable for proxies with this layout assumption. [Drupal Composer guide](https://www.drupal.org/docs/develop/using-composer/using-packagesdrupalorg) · [Composer repository protocol](https://getcomposer.org/doc/05-repositories.md#metadata-url-available-packages-and-available-package-patterns)

## Proposed change on Drupal.org

- Serve `/8/p2/drupal/<package>.json` and `/8/p2/drupal/<package>~dev.json` from the same generated files as `/files/packages/8/p2/`. Use an internal route at the Drupal.org edge so the client receives the metadata with HTTP 200 without needing to follow an external redirect.
- Use the same cache key for both paths or invalidate both when a package changes. The current generator purges the `/files/` path. Keep `ETag`, `Last-Modified`, conditional GETs, and HTTP 404 for unknown packages consistent across both paths. [Metadata generation and cache purge](https://git.drupalcode.org/project/project_composer/-/blob/b94a69c833f36d5032af7786c9113e3998adbdfb/project_composer.module#L1698-1716)
- After deploying the route, document `https://packages.drupal.org/8/` as a proxy upstream. The new route can also be advertised as `/8/p2/%package%.json` after verifying compatibility with existing Composer clients and mirrors. [Using packages.drupal.org](https://www.drupal.org/docs/develop/using-composer/using-packagesdrupalorg)

The Drupal change makes the official URL usable as an upstream for proxies expecting `p2/` under the base. End-to-end operation with a native Nexus group also depends on the Nexus changes below.

## What the two registries publish

`https://repo.packagist.org/packages.json` advertises `https://repo.packagist.org/p2/%package%.json`. `https://packages.drupal.org/8/packages.json` advertises `/files/packages/8/p2/%package%.json`. Composer 2 resolves the leading slash against the origin, which works with the documented Drupal URL. A repository manager that fetches `p2/drupal/token.json` relative to `https://packages.drupal.org/8/` reaches a path that returns HTTP 404. [Drupal index](https://packages.drupal.org/8/packages.json) · [Packagist index](https://repo.packagist.org/packages.json) · [Composer 2 repository protocol](https://getcomposer.org/doc/05-repositories.md#metadata-url-available-packages-and-available-package-patterns)

## Reproduction using public endpoints

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

On November 26, 2026, the requests in the loop returned `404`, `200`, `200`, and `200`, respectively. The two index bodies were identical. Composer 2.10.3 resolved `drupal/token:1.18.0` with either URL. A fresh test project using the alternate URL and Packagist also installed Token `1.18.0` from its release ZIP and Drupal Core `11.4.14`, with plugins and scripts disabled. The alternate URL places the package files where a registry proxy that appends `p2/` would look. The Drupal index generator writes `packages.json` alongside the package metadata. [Drupal index generator](https://git.drupalcode.org/project/project_composer/-/blob/b94a69c833f36d5032af7786c9113e3998adbdfb/project_composer.module#L126-132)

## Nexus proxy path resolution

In the native Composer module shipped with Nexus `3.96.3-01`, the proxy generates its own `metadata-url` under `/p2/` and resolves package metadata requests beneath the configured Remote Storage URL. Its archive lookup also reads upstream metadata under `/p2/`. The static Drupal URL fits both upstream paths. A general Nexus fix would resolve the upstream’s advertised `metadata-url` in both places, including URLs that start with `/`. [Nexus proxy URL resolution](https://github.com/sonatype/nexus-public/blob/release-3.96.3-01/public/common/components/nexus-repository-services/src/main/java/org/sonatype/nexus/repository/proxy/ProxyFacetSupport.java#L799-L837) · [Nexus API for 3.96.3-01](https://sonatype.github.io/sonatype-documentation/api/nexus-repository/3.96.3-01/nexus-repository-api.json)

I verified the difference with two native proxies on Nexus `3.96.3-01`. Both returned HTTP 200 for `packages.json`. The proxy pointed at `https://packages.drupal.org/8/` returned HTTP 404 for `p2/drupal/nbsp.json`. The proxy pointed at `https://packages.drupal.org/files/packages/8/` returned HTTP 200 for the same package metadata.

## Changes needed in Nexus

The first interactive `composer --no-cache require drupal/nbsp -vvv` run with Composer `2.10.2` and PHP `8.5.7` read the group’s `p2/drupal/nbsp~dev.json` with HTTP 200, then aborted in `ArrayLoader` before downloading an archive. Composer reported a `dist` object for `dev-1.x` that contained only the generated Nexus URL. Drupal’s upstream entry is source-only, with a Git URL and reference. An unfiltered local Nexus Community Edition `3.96.3-01` group reproduced the error. Composer requires `type` and `url` when a `dist` object is present. [Drupal NBSP dev metadata](https://packages.drupal.org/files/packages/8/p2/drupal/nbsp~dev.json) · [Composer 2.10.2 ArrayLoader](https://github.com/composer/composer/blob/2.10.2/src/Composer/Package/Loader/ArrayLoader.php#L200-L212)

- Resolve the upstream’s advertised `metadata-url` when obtaining package metadata and when looking up an archive. A leading `/` resolves against the origin. Add fixtures for both origin-relative and absolute templates.
- Preserve Git-only entries. Rewrite `dist.url` only when the upstream entry has a valid `dist`, and preserve the Git `source` for versions that publish only source metadata.
- Accept a metadata response with advisories and no `packages` list. It should contribute advisory data while the group gets the Core versions and archives from Packagist.
- Expand Composer 2 minified metadata before rewriting archive URLs. In the regression case, `drupal/core-composer-scaffold:11.4.14` must download the correct archive even when several versions inherit the same upstream `dist` record. [Related Sonatype issue #1046](https://github.com/sonatype/nexus-public/issues/1046) · [Composer metadata minifier](https://github.com/composer/metadata-minifier/blob/main/src/MetadataMinifier.php)

## Verified workaround for Nexus 3.96.3-01

- A routing rule on the Drupal proxy blocked Drupal `~dev.json` requests. The proxy returned HTTP 403 for the blocked request, and the group returned HTTP 404. Composer could continue with stable versions.
- The Drupal proxy also blocked `p2/drupal/core.json` and paths under `drupal/core/` so the group could take both Core metadata and archive lookups from Packagist. The Drupal endpoint lists security advisories exclusively. Nexus threw a `NullPointerException` with HTTP 500 when the Drupal proxy handled a Core archive lookup. [Drupal Core advisories](https://packages.drupal.org/files/packages/8/p2/drupal/core.json) · [Drupal advisory API issue](https://git.drupalcode.org/project/project_composer/-/work_items/3399877)
- A metadata adapter in front of Packagist expanded Composer 2 minified package records. This prevented the group from assigning the `11.4.9` download path to `drupal/core-composer-scaffold:11.4.14`. [Composer metadata minifier](https://github.com/composer/metadata-minifier/blob/main/src/MetadataMinifier.php)

With those changes to the test configuration, I ran `composer require psr/log` and `composer require drupal/nbsp` in sequence against the same Nexus group. Composer `2.10.2` installed `psr/log:3.0.2`, `drupal/nbsp:3.1.3` and `drupal/core:11.4.14`. All 66 archive URLs in the resulting lock file pointed to the group. A separate run with two hosted packages also succeeded. The NBSP ZIP from the group matched Drupal’s SHA-1 `18753c9a56daf92784db328dd5c1cb1a2434618c`. These runs exercised stable package installation with Composer plugins disabled. [Drupal NBSP release metadata](https://packages.drupal.org/files/packages/8/p2/drupal/nbsp.json)

The Drupal issue queue records earlier proxy issues involving Toran and Nexus. The Composer 2 mirror discussion describes the current `p2` paths and on-demand mirroring. [Toran report #2715453](https://git.drupalcode.org/project/project_composer/-/work_items/2715453) · [Nexus report #3026454](https://git.drupalcode.org/project/project_composer/-/work_items/3026454) · [Mirror discussion](https://www.drupal.org/project/lost_and_found_issues/issues/3091061#comment-13859663)

## Acceptance checks

1. Check `/8/packages.json`, `/8/p2/drupal/nbsp.json`, `/8/p2/drupal/nbsp~dev.json` and `/8/p2/drupal/core.json` on Drupal.org. Stable and dev NBSP data must match the existing paths, and the Core response must still contain the advisory data. An unknown package must give HTTP 404. Check conditional GETs and confirm that a metadata update is visible through both paths.
2. On a Nexus build with the fixes above, set the native Drupal proxy to `https://packages.drupal.org/8/` and the native Packagist proxy to `https://repo.packagist.org/`. Put both in one group. With only that group in the root Composer configuration and default Packagist disabled, run these two commands in an empty test project.

   ```bash
   composer --no-cache require psr/log -vvv
   composer --no-cache require drupal/nbsp -vvv
   ```

3. Verify that both commands complete, the archives download from the group, the NBSP archive matches the checksum published by Drupal, and the group provides valid metadata for the Git-only NBSP branch. Confirm advisory coverage separately with an affected package version. The acceptance run should use the plain upstream URLs without an adapter, routing filters, or a manual version pin.

Would the packages.drupal.org maintainers accept the `/8/p2/` route as a compatibility endpoint? I can help provide the HTTP checks and a small Composer test project. If the rewrite belongs in the edge configuration, I can open a linked infrastructure issue. [Drupal.org Infrastructure](https://www.drupal.org/project/infrastructure)
