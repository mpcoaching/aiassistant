#!/bin/sh
# Entrypoint for the Portkey AI Gateway (ADR-009).
#
# Portkey reads /app/conf.json at startup. Docker Compose does NOT expand
# ${VAR} placeholders inside mounted files, so provider credentials written as
# ${GROQ_API_KEY} etc. in the config template would reach Portkey literally.
# We resolve them from the container environment (sourced from ../.env) here,
# before Portkey starts. Node is used for the substitution so we have no
# dependency on gettext/envsubst being present in the Alpine base image.
set -e

TEMPLATE="/app/conf.template.json"
OUT="/app/conf.json"

if [ -f "$TEMPLATE" ]; then
  node -e '
    const fs = require("fs");
    const tpl = fs.readFileSync(process.argv[1], "utf8");
    const resolved = tpl.replace(/\$\{([A-Za-z0-9_]+)\}/g, (_, k) =>
      process.env[k] !== undefined ? process.env[k] : ""
    );
    fs.writeFileSync(process.argv[2], resolved);
  ' "$TEMPLATE" "$OUT"
fi

exec node build/start-server.js --port=4000
