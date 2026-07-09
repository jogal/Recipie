"""URLからレシピを取り込んで「レシピ集」に追加する共通処理。

CLI (`recipie add`) とWebフォームのどちらからもこのAPIを使う。
"""

from __future__ import annotations

from dataclasses import dataclass

from notion_client import Client

from . import notion_sync, scraper
from .config import Config, load_config


@dataclass
class AddResult:
    recipe: scraper.Recipe
    category: str | None
    main_ingredients: list[str]
    page_url: str | None = None
    duplicate: bool = False  # 追加済みのため何もしなかった


class ConfigError(RuntimeError):
    """トークンやデータベースIDが未設定."""


def _client(config: Config) -> Client:
    if not config.notion_token or not config.database_id:
        raise ConfigError(
            "Notionのトークン/データベースが未設定です。"
            "先に `recipie init --database <レシピ集のURL>` を実行してください。"
        )
    return Client(auth=config.notion_token)


def add_recipe_from_url(
    url: str,
    *,
    category: str | None = None,
    main_ingredients: list[str] | None = None,
    force: bool = False,
    config: Config | None = None,
) -> AddResult:
    """レシピURLを取り込んで「レシピ集」に追加する。

    category / main_ingredients を省略すると、それぞれ自動推定・自動判定する。
    既に追加済みで force=False の場合は追加せず duplicate=True を返す。
    """
    config = config or load_config()
    notion = _client(config)

    recipe = scraper.scrape_recipe(url)
    category = category or notion_sync.guess_category(recipe)

    existing = notion_sync.find_existing_page(notion, config.database_id, recipe.url)
    if existing and not force:
        return AddResult(
            recipe=recipe,
            category=category,
            main_ingredients=main_ingredients or [],
            duplicate=True,
        )

    mains = main_ingredients
    if not mains:
        _, known_options = notion_sync.get_database_info(notion, config.database_id)
        mains = notion_sync.match_main_ingredients(recipe, known_options)

    page_url = notion_sync.add_recipe(
        notion, config.database_id, recipe, category=category, main_ingredients=mains
    )
    return AddResult(
        recipe=recipe, category=category, main_ingredients=mains, page_url=page_url
    )
