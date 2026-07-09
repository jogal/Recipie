"""抽出したレシピをNotionデータベースに見やすいページとして追加する。"""

from __future__ import annotations

from datetime import date

from notion_client import Client

from .scraper import Recipe

# Notion API の制限
MAX_TEXT_LENGTH = 2000
MAX_CHILDREN_PER_REQUEST = 100

DB_TITLE = "レシピ帳"

DB_PROPERTIES = {
    "名前": {"title": {}},
    "URL": {"url": {}},
    "サイト": {"select": {}},
    "タグ": {"multi_select": {}},
    "調理時間(分)": {"number": {"format": "number"}},
    "分量": {"rich_text": {}},
    "追加日": {"date": {}},
    "作った": {"checkbox": {}},
    "評価": {
        "select": {
            "options": [
                {"name": "★★★", "color": "yellow"},
                {"name": "★★", "color": "orange"},
                {"name": "★", "color": "gray"},
            ]
        }
    },
}


def _text(content: str, link: str | None = None) -> dict:
    rich: dict = {"type": "text", "text": {"content": content[:MAX_TEXT_LENGTH]}}
    if link:
        rich["text"]["link"] = {"url": link}
    return rich


def _heading(level: int, content: str) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [_text(content)]}}


def create_database(notion: Client, parent_page_id: str) -> str:
    """親ページ配下にレシピ用データベースを作成し、そのIDを返す。"""
    response = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[_text(DB_TITLE)],
        icon={"type": "emoji", "emoji": "🍳"},
        properties=DB_PROPERTIES,
    )
    return response["id"]


def find_existing_page(notion: Client, database_id: str, url: str) -> str | None:
    """同じURLのレシピが既に登録済みならそのページIDを返す。"""
    response = notion.databases.query(
        database_id=database_id,
        filter={"property": "URL", "url": {"equals": url}},
        page_size=1,
    )
    results = response.get("results", [])
    return results[0]["id"] if results else None


def recipe_to_properties(recipe: Recipe, extra_tags: list[str] | None = None) -> dict:
    tags = list(dict.fromkeys((extra_tags or []) + recipe.keywords))
    properties: dict = {
        "名前": {"title": [_text(recipe.title)]},
        "URL": {"url": recipe.url},
        "追加日": {"date": {"start": date.today().isoformat()}},
        "作った": {"checkbox": False},
    }
    if recipe.site_name:
        # select のオプション名にカンマは使えない
        properties["サイト"] = {"select": {"name": recipe.site_name.replace(",", " ")[:100]}}
    if tags:
        properties["タグ"] = {
            "multi_select": [{"name": t.replace(",", " ")[:100]} for t in tags[:20]]
        }
    if recipe.total_time_minutes:
        properties["調理時間(分)"] = {"number": recipe.total_time_minutes}
    if recipe.yields:
        properties["分量"] = {"rich_text": [_text(recipe.yields)]}
    return properties


def recipe_to_blocks(recipe: Recipe) -> list[dict]:
    """レシピをNotionページ本文のブロック列に変換する。

    構成: 元レシピへのリンク → 説明 → 材料(チェックボックス。買い物リスト
    としても使える) → 作り方(番号付きリスト) → メモ欄
    """
    blocks: list[dict] = []

    link_label = recipe.site_name or "元のページ"
    link_texts = [_text("元レシピ: "), _text(link_label, link=recipe.url)]
    if recipe.author:
        link_texts.append(_text(f"　（{recipe.author} さん）"))
    blocks.append(
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "🔗"},
                "color": "gray_background",
                "rich_text": link_texts,
            },
        }
    )

    if recipe.description:
        blocks.append(
            {
                "object": "block",
                "type": "quote",
                "quote": {"rich_text": [_text(recipe.description)]},
            }
        )

    if recipe.ingredient_groups:
        heading = "🧺 材料"
        if recipe.yields:
            heading += f"（{recipe.yields}）"
        blocks.append(_heading(2, heading))
        for group in recipe.ingredient_groups:
            if group.purpose:
                blocks.append(_heading(3, group.purpose))
            for item in group.ingredients:
                blocks.append(
                    {
                        "object": "block",
                        "type": "to_do",
                        "to_do": {"rich_text": [_text(item)], "checked": False},
                    }
                )

    if recipe.instructions:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append(_heading(2, "👨‍🍳 作り方"))
        for step in recipe.instructions:
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": [_text(step)]},
                }
            )

    blocks.append({"object": "block", "type": "divider", "divider": {}})
    blocks.append(_heading(2, "📝 メモ"))
    blocks.append(
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [_text("感想や自分なりのアレンジをここに。")]},
        }
    )

    return blocks


def add_recipe(
    notion: Client,
    database_id: str,
    recipe: Recipe,
    extra_tags: list[str] | None = None,
) -> str:
    """レシピをデータベースに追加し、作成したページのURLを返す。"""
    blocks = recipe_to_blocks(recipe)

    page_args: dict = {
        "parent": {"type": "database_id", "database_id": database_id},
        "properties": recipe_to_properties(recipe, extra_tags),
        "children": blocks[:MAX_CHILDREN_PER_REQUEST],
        "icon": {"type": "emoji", "emoji": "🍽️"},
    }
    if recipe.image:
        page_args["cover"] = {"type": "external", "external": {"url": recipe.image}}

    page = notion.pages.create(**page_args)

    # 1リクエスト100ブロックの上限を超える分は追記する
    remaining = blocks[MAX_CHILDREN_PER_REQUEST:]
    while remaining:
        notion.blocks.children.append(
            block_id=page["id"], children=remaining[:MAX_CHILDREN_PER_REQUEST]
        )
        remaining = remaining[MAX_CHILDREN_PER_REQUEST:]

    return page.get("url", page["id"])
