from pathlib import Path

import yaml

CHALLENGE_ROOT = Path("/challenges")


class ChallengeRegistry:
    def __init__(self, root: Path = CHALLENGE_ROOT):
        self.root = root

    def list(self) -> list[dict]:
        manifests = []
        if not self.root.exists():
            return manifests
        for path in sorted(self.root.glob("*/challenge.yaml")):
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            data["_source"] = str(path)
            manifests.append(data)
        return manifests

    def get(self, challenge_id: str) -> dict:
        for manifest in self.list():
            if manifest.get("id") == challenge_id:
                return manifest
        raise KeyError(f"Challenge not found: {challenge_id}")


def load_challenge_manifests() -> list[dict]:
    return ChallengeRegistry().list()
