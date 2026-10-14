"""Regenerate the six checked-in feedback-model templates from the executable definition."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import INDUSTRIES, ROOT
from app.sd_feedback import default_model


def main() -> None:
    model_dir = Path(ROOT) / "models"
    for index, industry in enumerate(INDUSTRIES, 1):
        target = model_dir / f"{index}.json"
        previous = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
        model = default_model(industry)
        # Keep the stable template identity. Runtime migration preserves user IDs,
        # versions and historical snapshots independently of these source files.
        if previous.get("id"):
            model["id"] = previous["id"]
        model["version"] = 1
        model.pop("created_at", None)
        target.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
