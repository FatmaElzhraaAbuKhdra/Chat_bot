#!/usr/bin/env bash
# deploy_schema.sh — pull latest justclick_comments.sql into the running container
# Usage: bash scripts/deploy_schema.sh
set -e

UPSTREAM="https://github.com/FatmaElzhraaAbuKhdra/Chat_bot.git"
CONTAINER="chatbot-app-1"

echo "[1/3] syncing schema file from upstream..."
git remote get-url upstream 2>/dev/null || git remote add upstream "$UPSTREAM"
git fetch upstream main --quiet
git checkout upstream/main -- justclick_comments.sql
echo "      OK: $(wc -l < justclick_comments.sql) lines"

echo "[2/3] copying into container $CONTAINER..."
docker cp justclick_comments.sql "$CONTAINER":/app/justclick_comments.sql

echo "[3/3] reloading schema + clearing caches..."
docker exec "$CONTAINER" python3 -c "
import urllib.request, json
req = urllib.request.Request('http://localhost:8000/chat/reload-schema', data=b'', method='POST')
r = json.loads(urllib.request.urlopen(req).read())
print('  tables:', r['tables'], '| columns:', r['columns'])
print('  cleared:', r['caches_cleared'])
"
echo "done."
