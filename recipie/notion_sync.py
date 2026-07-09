"""抽出したレシピをNotionの「レシピ集」データベースに追加する。

既存の「レシピ集」データベースのスキーマ・ページ形式に合わせている:
  プロパティ: レシピ名(title) / カテゴリー(select) / メイン材料(multi_select)
            / 調理時間(number) / 作成済(checkbox) / 情報源(text) / 画像(url)
  本文: 説明 → ## 材料 → ## 作り方
"""

from __future__ import annotations

import re

from notion_client import Client

from .scraper import Recipe

# Notion API の制限
MAX_TEXT_LENGTH = 2000
MAX_CHILDREN_PER_REQUEST = 100

DB_TITLE = "レシピ集"

CATEGORIES = [
    "メインディッシュ",
    "サイドディッシュ",
    "スープ・汁物",
    "サラダ",
    "デザート",
    "朝食",
    "パン・パスタ",
    "お弁当",
]

# 「レシピ集」がまだ無い場合に init --parent で作るスキーマ(既存DBと同一)
DB_PROPERTIES = {
    "レシピ名": {"title": {}},
    "カテゴリー": {"select": {"options": [{"name": c} for c in CATEGORIES]}},
    "メイン材料": {"multi_select": {}},
    "調理時間": {"number": {"format": "number"}},
    "作成済": {"checkbox": {}},
    "情報源": {"rich_text": {}},
    "画像": {"url": {}},
    "手順": {"rich_text": {}},
}

_CATEGORY_HINTS: list[tuple[str, str]] = [
    ("サラダ", "サラダ"),
    ("スープ", "スープ・汁物"),
    ("汁", "スープ・汁物"),
    ("シチュー", "スープ・汁物"),
    ("ポタージュ", "スープ・汁物"),
    ("デザート", "デザート"),
    ("ケーキ", "デザート"),
    ("クッキー", "デザート"),
    ("プリン", "デザート"),
    ("お菓子", "デザート"),
    ("スイーツ", "デザート"),
    ("パスタ", "パン・パスタ"),
    ("スパゲッティ", "パン・パスタ"),
    ("パン", "パン・パスタ"),
    ("トースト", "パン・パスタ"),
    ("お弁当", "お弁当"),
    ("弁当", "お弁当"),
    ("朝食", "朝食"),
    ("朝ごはん", "朝食"),
    ("副菜", "サイドディッシュ"),
    ("付け合わせ", "サイドディッシュ"),
    ("浅漬け", "サイドディッシュ"),
    ("漬け", "サイドディッシュ"),
    ("和え", "サイドディッシュ"),
    ("ナムル", "サイドディッシュ"),
    ("おつまみ", "サイドディッシュ"),
    ("主菜", "メインディッシュ"),
    ("主食", "メインディッシュ"),
    ("丼", "メインディッシュ"),
    ("カレー", "メインディッシュ"),
    ("定番", "メインディッシュ"),
]

# 「豚バラ肉(薄切り) 250g」→「豚バラ肉」のように材料名だけを取り出すための表現
_PAREN_RE = re.compile(r"[（(][^）)]*[）)]")
_MARKER_RE = re.compile(r"^[・◎○●★☆◇◆\s]+|[【〈\[][^】〉\]]*[】〉\]]")
# 行末の「大さじ2」「250g」「少々」といった分量表現
_QUANTITY_RE = re.compile(
    r"[\s…‥:：]*[\d０-９/／.．〜~\s]*"
    r"(?:大さじ|小さじ|カップ|g|kg|ml|cc|L|ｇ|㎏|個|本|枚|片|株|束|袋|缶|丁|玉|杯|合|かけ|少々|適量|適宜|お好みで?)?"
    r"[\d０-９/／.．〜~\s]*$"
)


def guess_category(recipe: Recipe) -> str | None:
    """タイトルとキーワードから「レシピ集」のカテゴリーを推定する。不明ならNone。"""
    haystack = recipe.title + " " + " ".join(recipe.keywords)
    # 「フライパン」「パン粉」の「パン」などへの誤反応を防ぐ
    for noise in ("フライパン", "パン粉", "パン切り"):
        haystack = haystack.replace(noise, "")
    for hint, category in _CATEGORY_HINTS:
        if hint in haystack:
            return category
    return None


def extract_ingredient_name(line: str) -> str:
    """材料行から分量などを除いて材料名だけを取り出す。"""
    name = _PAREN_RE.sub("", line)
    name = _MARKER_RE.sub("", name).strip()
    name = name.split()[0] if name.split() else name
    name = _QUANTITY_RE.sub("", name).strip()
    return name


def match_main_ingredients(recipe: Recipe, known_options: list[str]) -> list[str]:
    """材料リストを、データベースに登録済みの「メイン材料」の選択肢と照合する。

    選択肢を勝手に増やして汚さないよう、既存の選択肢に一致したものだけ返す。
    """
    names = [extract_ingredient_name(i) for i in recipe.ingredients]
    matched = []
    for option in known_options:
        if any(option == n or (option and option in n) for n in names if n):
            matched.append(option)
    return matched


def _text(content: str, link: str | None = None) -> dict:
    rich: dict = {"type": "text", "text": {"content": content[:MAX_TEXT_LENGTH]}}
    if link:
        rich["text"]["link"] = {"url": link}
    return rich


def _heading(level: int, content: str) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [_text(content)]}}


def create_database(notion: Client, parent_page_id: str) -> str:
    """「レシピ集」がまだ無い人向けに、同じスキーマのデータベースを新規作成する。"""
    response = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[_text(DB_TITLE)],
        icon={"type": "emoji", "emoji": "🍳"},
        properties=DB_PROPERTIES,
    )
    return response["id"]


def get_database_info(notion: Client, database_id: str) -> tuple[str, list[str]]:
    """データベースのタイトルと「メイン材料」の既存選択肢を取得する。"""
    db = notion.databases.retrieve(database_id=database_id)
    title = "".join(t.get("plain_text", "") for t in db.get("title", []))
    options: list[str] = []
    prop = db.get("properties", {}).get("メイン材料", {})
    if prop.get("type") == "multi_select":
        options = [o["name"] for o in prop["multi_select"].get("options", [])]
    return title, options


def find_existing_page(notion: Client, database_id: str, url: str) -> str | None:
    """同じ情報源URLのレシピが既に登録済みならそのページIDを返す。"""
    response = notion.databases.query(
        database_id=database_id,
        filter={"property": "情報源", "rich_text": {"contains": url}},
        page_size=1,
    )
    results = response.get("results", [])
    return results[0]["id"] if results else None


def recipe_to_properties(
    recipe: Recipe,
    category: str | None = None,
    main_ingredients: list[str] | None = None,
) -> dict:
    properties: dict = {
        "レシピ名": {"title": [_text(recipe.title)]},
        "情報源": {"rich_text": [_text(recipe.url, link=recipe.url)]},
        "作成済": {"checkbox": False},
    }
    if category:
        properties["カテゴリー"] = {"select": {"name": category.replace(",", " ")[:100]}}
    if main_ingredients:
        properties["メイン材料"] = {
            "multi_select": [{"name": m.replace(",", " ")[:100]} for m in main_ingredients[:20]]
        }
    if recipe.total_time_minutes:
        properties["調理時間"] = {"number": recipe.total_time_minutes}
    if recipe.image:
        properties["画像"] = {"url": recipe.image}
    return properties


def recipe_to_blocks(recipe: Recipe) -> list[dict]:
    """レシピを「レシピ集」の既存ページと同じ構成の本文ブロック列に変換する。

    構成: 説明 → ## 材料（分量） → ## 作り方
    """
    blocks: list[dict] = []

    if recipe.description:
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [_text(recipe.description)]},
            }
        )

    if recipe.ingredient_groups:
        heading = "材料"
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
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": [_text(item)]},
                    }
                )

    if recipe.instructions:
        blocks.append(_heading(2, "作り方"))
        for step in recipe.instructions:
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": [_text(step)]},
                }
            )

    return blocks


def add_recipe(
    notion: Client,
    database_id: str,
    recipe: Recipe,
    category: str | None = None,
    main_ingredients: list[str] | None = None,
) -> str:
    """レシピを「レシピ集」に追加し、作成したページのURLを返す。"""
    blocks = recipe_to_blocks(recipe)

    page_args: dict = {
        "parent": {"type": "database_id", "database_id": database_id},
        "properties": recipe_to_properties(recipe, category, main_ingredients),
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
