"""Configure the Composer repositories and sample packages in the local Nexus stack."""

import base64
import io
import ipaddress
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import zipfile


NEXUS = os.environ.get("NEXUS_URL", "http://nexus:8081").rstrip("/")
API = "/service/rest/v1/"
PACKAGIST = os.environ.get("PACKAGIST_REMOTE_URL", "http://127.0.0.1:18097/")
HOSTED = ["composer-hosted-1", "composer-hosted-2"]
RULE = "composer-drupal-stable"
STORAGE = {"blobStoreName": "default", "strictContentTypeValidation": True}


def wait_for_nexus():
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            with urlopen(NEXUS + API + "status", timeout=4):
                return
        except (URLError, TimeoutError):
            time.sleep(2)
    raise RuntimeError(f"Nexus antwortet seit 5 Minuten nicht unter {NEXUS}.")


class Nexus:
    def __init__(self, password):
        credentials = base64.b64encode(f"admin:{password}".encode()).decode()
        self.authorization = "Basic " + credentials

    def request(self, method, path, data=None, *, optional=False):
        headers = {"Authorization": self.authorization}
        if isinstance(data, bytes):
            headers["Content-Type"] = "application/zip"
        elif data is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(data).encode()
        request = Request(NEXUS + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=60) as response:
                if method == "GET":
                    return json.load(response)
        except HTTPError as error:
            if error.code == 404 and optional:
                return None
            detail = error.read(1200).decode(errors="replace").strip()
            raise RuntimeError(f"{method} {path}: HTTP {error.code} {detail}") from error

    def configure(self, collection, desired):
        path = API + collection
        item = path + "/" + desired["name"]
        current = self.request("GET", item, optional=True)
        if current is not None and contains_settings(current, desired):
            return
        if current is None:
            self.request("POST", path, desired)
        else:
            self.request("PUT", item, desired)
        print(f"Konfiguriert: {desired['name']}", flush=True)


def contains_settings(current, desired):
    if isinstance(desired, dict):
        return isinstance(current, dict) and all(
            contains_settings(current.get(key), value) for key, value in desired.items()
        )
    return current == desired


def configure_access(nexus):
    eula = nexus.request("GET", API + "system/eula")
    if not eula["accepted"]:
        if os.environ.get("NEXUS_ACCEPT_EULA", "").lower() != "true":
            raise RuntimeError(
                "Die Nexus Community-EULA ist noch offen. Lies "
                "https://links.sonatype.com/products/nxrm/ce-eula und setze bei Zustimmung "
                "NEXUS_ACCEPT_EULA=true für den Compose-Start."
            )
        nexus.request("POST", API + "system/eula", {**eula, "accepted": True})
    anonymous = nexus.request("GET", API + "security/anonymous")
    if not anonymous["enabled"]:
        nexus.request("PUT", API + "security/anonymous", {**anonymous, "enabled": True})

    host = urlsplit(PACKAGIST).hostname
    if not host:
        raise ValueError("PACKAGIST_REMOTE_URL muss eine absolute URL mit Host sein.")
    try:
        ipaddress.ip_address(host)
        key = "allowedIPs"
    except ValueError:
        key = "allowedDomains"
    ssrf = nexus.request("GET", API + "security/ssrf-protection")
    allowed = ssrf.get(key) or []
    if ssrf["enabled"] and host not in allowed:
        nexus.request("PUT", API + "security/ssrf-protection", {**ssrf, key: [*allowed, host]})


def configure_repositories(nexus):
    nexus.configure("routing-rules", {
        "name": RULE, "description": "Drupal-Releases; Core kommt von Packagist.", "mode": "BLOCK",
        "matchers": [
            r"^/p2/drupal/[^/?]+~dev\.json(?:\?.*)?$",
            r"^/p2/drupal/core\.json(?:\?.*)?$",
            r"^/drupal/core/.*$",
        ],
    })
    for name in HOSTED:
        nexus.configure("repositories/composer/hosted", {
            "name": name, "online": True, "storage": {**STORAGE, "writePolicy": "ALLOW_ONCE"},
        })
    for name, remote, rule in [
        ("composer-drupal", "https://packages.drupal.org/files/packages/8/", RULE),
        ("composer-packagist", PACKAGIST, None),
    ]:
        nexus.configure("repositories/composer/proxy", {
            "name": name, "online": True, "storage": STORAGE, "routingRuleName": rule,
            "proxy": {"remoteUrl": remote, "contentMaxAge": -1, "metadataMaxAge": 0},
            "negativeCache": {"enabled": False, "timeToLive": 1},
            "httpClient": {"blocked": False, "autoBlock": False},
        })
    nexus.configure("repositories/composer/group", {
        "name": "composer-group", "online": True, "storage": STORAGE,
        "group": {"memberNames": [*HOSTED, "composer-drupal", "composer-packagist"]},
    })


def seed_fixtures(nexus):
    for number, repository in enumerate(HOSTED, start=1):
        name = f"example-lab/fixture-{number}"
        base = f"/repository/{repository}/"
        metadata = nexus.request("GET", base + f"p2/{name}.json", optional=True) or {}
        versions = metadata.get("packages", {}).get(name, [])
        if any(version.get("version") == "1.0.0" for version in versions):
            continue
        manifest = {"name": name, "version": "1.0.0", "type": "library",
                    "description": "Testpaket für die lokale Nexus-Composer-Gruppe"}
        body = io.BytesIO()
        with zipfile.ZipFile(body, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("composer.json", json.dumps(manifest))
        nexus.request("PUT", base, body.getvalue())
        print(f"Hochgeladen: {name} 1.0.0 nach {repository}", flush=True)


def main():
    wait_for_nexus()
    password_file = Path(os.environ.get("NEXUS_ADMIN_PASSWORD_FILE", "/nexus-data/admin.password"))
    if not password_file.is_file():
        raise RuntimeError(
            f"Admin-Passwortdatei {password_file} fehlt. Bei geändertem Passwort die aktuelle "
            "Passwortdatei in den Initialisierungscontainer einbinden und "
            "NEXUS_ADMIN_PASSWORD_FILE auf deren Pfad setzen."
        )
    nexus = Nexus(password_file.read_text().strip())
    configure_access(nexus)
    configure_repositories(nexus)
    seed_fixtures(nexus)
    print("Composer-Gruppe und beide Hosted-Testpakete sind bereit.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        sys.exit(str(error))
