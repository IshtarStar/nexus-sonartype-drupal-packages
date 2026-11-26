#!/usr/bin/env python3
"""Serve Packagist metadata with expanded Composer 2 package versions."""

import argparse
import http.client
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PACKAGIST_HOST = "repo.packagist.org"
PACKAGE_PATH = re.compile(r"/p2/[a-z0-9][a-z0-9_.-]*/[a-z0-9][a-z0-9_.-]*(?:~dev)?\.json")


def expand_versions(versions):
    expanded = []
    previous = {}
    for delta in versions:
        current = previous.copy() if previous else delta.copy()
        if previous:
            for key, value in delta.items():
                if value == "__unset":
                    current.pop(key, None)
                else:
                    current[key] = value
        expanded.append(current)
        previous = current
    return expanded


def expand_package_metadata(body):
    metadata = json.loads(body)
    packages = metadata.get("packages")
    if metadata.get("minified") != "composer/2.0" or not packages or not any(packages.values()):
        return body

    metadata["packages"] = {name: expand_versions(versions) for name, versions in packages.items()}
    del metadata["minified"]
    return json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def fetch_metadata(path):
    connection = http.client.HTTPSConnection(PACKAGIST_HOST, timeout=20)
    try:
        connection.request("GET", path, headers={"Accept-Encoding": "identity"})
        response = connection.getresponse()
        return response.status, response.headers, response.read()
    finally:
        connection.close()


class PackagistMetadataHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.serve_metadata(include_body=True)

    def do_HEAD(self):
        self.serve_metadata(include_body=False)

    def serve_metadata(self, *, include_body):
        path = "/" + self.path.partition("?")[0].lstrip("/")
        is_package = PACKAGE_PATH.fullmatch(path) is not None
        if path != "/packages.json" and not is_package:
            self.send_error(404)
            return

        try:
            status, headers, body = fetch_metadata(path)
        except (OSError, http.client.HTTPException) as error:
            self.log_error("Packagist request failed: %s", error)
            self.send_error(502, "Packagist request failed")
            return

        if status == 200 and is_package:
            try:
                body = expand_package_metadata(body)
            except (ValueError, TypeError, AttributeError) as error:
                self.log_error("Invalid Packagist metadata: %s", error)
                self.send_error(502, "Invalid Packagist metadata")
                return

        self.send_response(status)
        self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
        self.send_header("Content-Length", str(len(body)))
        if headers.get("Last-Modified"):
            self.send_header("Last-Modified", headers["Last-Modified"])
        self.end_headers()
        if include_body:
            self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=18097, type=int)
    args = parser.parse_args()
    with ThreadingHTTPServer((args.host, args.port), PackagistMetadataHandler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
