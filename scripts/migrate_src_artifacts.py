"""
Migrate legacy artifacts directory from `src/artifacts/` -> project-level `artifacts/`.

Why:
- `src/` is a Python package; runtime outputs should not live inside it.
- We now write artifacts to the top-level `artifacts/` directory.

Run:
  python scripts/migrate_src_artifacts.py
"""

from __future__ import annotations

from pathlib import Path
import shutil


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    src_artifacts = root / "src" / "artifacts"
    dst_artifacts = root / "artifacts"

    if not src_artifacts.exists():
        print("No src/artifacts directory found. Nothing to migrate.")
        return

    moved = 0
    for path in src_artifacts.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src_artifacts)
        target = dst_artifacts / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
        moved += 1

    print(f"Migrated {moved} file(s) from src/artifacts -> artifacts/")
    print("Note: empty directories under src/artifacts may remain; safe to delete manually if desired.")


if __name__ == "__main__":
    main()


