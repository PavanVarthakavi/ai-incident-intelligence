#!/usr/bin/env bash
# Installs index templates. Idempotent: safe to run on every `docker compose up`.
set -euo pipefail

for template in /init/templates/*.json; do
  name=$(basename "$template" .json)
  echo "installing index template: $name"
  curl -sf -X PUT "$OPENSEARCH_URL/_index_template/$name" \
    -H 'Content-Type: application/json' --data-binary "@$template"
  echo
done
