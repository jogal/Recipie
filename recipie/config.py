"""設定の読み書き。

優先順位: 環境変数 (NOTION_TOKEN / RECIPIE_DATABASE_ID)
        > 設定ファイル (~/.config/recipie/config.json)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(
    os.environ.get("RECIPIE_CONFIG", "~/.config/recipie/config.json")
).expanduser()


@dataclass
class Config:
    notion_token: str | None = None
    database_id: str | None = None


def load_config() -> Config:
    data: dict = {}
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return Config(
        notion_token=os.environ.get("NOTION_TOKEN") or data.get("notion_token"),
        database_id=os.environ.get("RECIPIE_DATABASE_ID") or data.get("database_id"),
    )


def save_config(config: Config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(
            {"notion_token": config.notion_token, "database_id": config.database_id},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    CONFIG_PATH.chmod(0o600)  # トークンを含むため本人のみ読み書き可にする
