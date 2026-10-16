#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

TARGET="backend/app/services/challenge_registry.py"

if [[ ! -f "$TARGET" ]]; then
  echo "ERROR: Missing $TARGET"
  exit 1
fi

python - "$TARGET" <<'PY'
from pathlib import Path
import sys

target = Path(sys.argv[1])
source = target.read_text()

old = "CHALLENGE_ROOT = Path(\"/challenges\")"
new = '''REPO_CHALLENGE_ROOT = Path(__file__).resolve().parents[3] / "challenges"
CHALLENGE_ROOT = (
    Path("/challenges")
    if Path("/challenges").is_dir()
    else REPO_CHALLENGE_ROOT
)'''

if new in source:
    print("Already patched; no changes made.")
elif source.count(old) == 1:
    backup = target.with_suffix(".py.bak")
    if backup.exists():
        raise SystemExit(f"ERROR: Backup already exists: {backup}")
    backup.write_text(source)
    target.write_text(source.replace(old, new, 1))
    print(f"Patched {target}")
    print(f"Backup: {backup}")
else:
    raise SystemExit(
        "ERROR: Expected original line was not found exactly once. "
        "No changes made."
    )
PY

echo "=== Verify manifest discovery ==="
cd backend
source .venv/bin/activate
python - <<'PY'
from app.services.challenge_registry import ChallengeRegistry

registry = ChallengeRegistry()
manifests = registry.list()
ids = sorted(m.get("id", "<missing-id>") for m in manifests)

print("Registry path:", registry.root)
print("Manifest count:", len(manifests))
print("Challenge IDs:", ids)

expected = {
    "ignore-the-rules",
    "poisoned-doc",
    "too-much-power",
    "whose-data",
}
if not expected.issubset(set(ids)):
    raise SystemExit("ERROR: Expected challenge manifests are missing.")
print("SUCCESS: All four expected challenges were discovered.")
PY
