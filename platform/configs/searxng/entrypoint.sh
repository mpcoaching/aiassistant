#!/bin/sh
# Entrypoint wrapper for the SearXNG container (platform stack).
#
# SearXNG reads /etc/searxng/settings.yml at startup and the official image
# substitutes only ${SEARXNG_PORT}; every other value has to come from that
# file. Docker Compose does NOT expand ${VAR} placeholders inside a mounted
# file, so a template committed with __SEARXNG_SECRET__ / __SEARXNG_BASE_URL__
# would reach SearXNG literally. We resolve them here from the container
# environment (sourced from ../.env), which keeps the instance secret out of
# Git — the same mechanism platform/configs/portkey/entrypoint.sh uses for
# conf.json.
#
# The rendered file is written to /etc/searxng/settings.yml inside the
# container's own layer (a normal, writable container directory), so nothing is
# written to the host and the mounted template stays read-only.
set -eu

TEMPLATE=/etc/searxng/platform-settings.template.yml
OUT=/etc/searxng/settings.yml

if [ ! -f "$TEMPLATE" ]; then
  echo "ERROR: $TEMPLATE is missing; SearXNG cannot be configured." >&2
  exit 1
fi

# The instance secret signs SearXNG's cookies and limiter tokens. It must be
# present and must stay substitution-safe, because it is injected with sed
# below — enforce that here rather than silently rendering a broken config.
if [ -z "${SEARXNG_SECRET:-}" ]; then
  echo "ERROR: SEARXNG_SECRET is not set; add it to .env." >&2
  exit 1
fi
case "$SEARXNG_SECRET" in
  *[!A-Za-z0-9]*)
    echo "ERROR: SEARXNG_SECRET must be alphanumeric." >&2
    exit 1
    ;;
esac

sed -e "s|__SEARXNG_SECRET__|${SEARXNG_SECRET}|g" \
    -e "s|__SEARXNG_BASE_URL__|${SEARXNG_BASE_URL:-}|g" \
    "$TEMPLATE" > "$OUT"

if grep -q '__SEARXNG_' "$OUT"; then
  echo "ERROR: unresolved placeholders left in $OUT." >&2
  exit 1
fi

# Hand over to the image entrypoint: it verifies the config directory, runs the
# root-only setup and execs the SearXNG WSGI app on :8080.
exec /usr/local/searxng/entrypoint.sh