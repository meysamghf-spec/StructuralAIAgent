"""Create local .env from .env.example when credentials are not yet present."""

from __future__ import annotations

import getpass
import shutil
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    example_path = repo_root / ".env.example"

    if env_path.exists():
        print(".env already exists — leaving unchanged")
        return 0

    if not example_path.exists():
        print("Missing .env.example")
        return 1

    shutil.copyfile(example_path, env_path)
    password = getpass.getpass("Enter local PostgreSQL password for user postgres: ")
    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    for line in lines:
        if line.startswith("POSTGRES_PASSWORD="):
            updated.append(f"POSTGRES_PASSWORD={password}")
        else:
            updated.append(line)
    env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    print(f"Created {env_path} (password not displayed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
