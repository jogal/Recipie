from unittest.mock import MagicMock

from recipie.cli import extract_page_id
from recipie.notion_sync import (
    MAX_TEXT_LENGTH,
    add_recipe,
    recipe_to_blocks,
    recipe_to_properties,
)
from recipie.scraper import IngredientGroup, Recipe


def make_recipe(**overrides) -> Recipe:
    defaults = dict(
        url="https://example.com/recipe/1",
        title="テストレシピ",
        site_name="テストキッチン",
        author="テスト太郎",
        description="説明文",
        image="https://example.com/img.jpg",
        total_time_minutes=20,
        yields="2人分",
        ingredient_groups=[
            IngredientGroup(purpose=None, ingredients=["豚肉 250g", "玉ねぎ 1/2個"]),
            IngredientGroup(purpose="タレ", ingredients=["醤油 大さじ2"]),
        ],
        instructions=["切る。", "炒める。", "盛る。"],
        keywords=["豚肉", "時短"],
    )
    defaults.update(overrides)
    return Recipe(**defaults)


def test_properties():
    props = recipe_to_properties(make_recipe(), extra_tags=["和食", "豚肉"])
    assert props["名前"]["title"][0]["text"]["content"] == "テストレシピ"
    assert props["URL"]["url"] == "https://example.com/recipe/1"
    assert props["調理時間(分)"]["number"] == 20
    tag_names = [t["name"] for t in props["タグ"]["multi_select"]]
    assert tag_names == ["和食", "豚肉", "時短"]  # 重複は除去される


def test_long_text_is_truncated():
    props = recipe_to_properties(make_recipe(title="あ" * 3000))
    assert len(props["名前"]["title"][0]["text"]["content"]) == MAX_TEXT_LENGTH


def test_blocks_structure():
    blocks = recipe_to_blocks(make_recipe())
    assert blocks[0]["type"] == "callout"  # 先頭は元レシピへのリンク
    to_dos = [b for b in blocks if b["type"] == "to_do"]
    steps = [b for b in blocks if b["type"] == "numbered_list_item"]
    headings = [b for b in blocks if b["type"] == "heading_3"]
    assert len(to_dos) == 3
    assert len(steps) == 3
    assert headings[0]["heading_3"]["rich_text"][0]["text"]["content"] == "タレ"


def test_add_recipe_chunks_blocks():
    # 材料を大量にして100ブロック超の分割追記を確認する
    many = IngredientGroup(purpose=None, ingredients=[f"材料{i}" for i in range(150)])
    recipe = make_recipe(ingredient_groups=[many])

    notion = MagicMock()
    notion.pages.create.return_value = {"id": "page-id", "url": "https://notion.so/page"}

    url = add_recipe(notion, "db-id", recipe)

    assert url == "https://notion.so/page"
    assert len(notion.pages.create.call_args.kwargs["children"]) == 100
    appended = notion.blocks.children.append.call_args_list
    total_appended = sum(len(c.kwargs["children"]) for c in appended)
    assert total_appended == len(recipe_to_blocks(recipe)) - 100


def test_extract_page_id():
    assert (
        extract_page_id("https://www.notion.so/myspace/My-Page-0123456789abcdef0123456789abcdef")
        == "01234567-89ab-cdef-0123-456789abcdef"
    )
    assert (
        extract_page_id("01234567-89ab-cdef-0123-456789abcdef")
        == "01234567-89ab-cdef-0123-456789abcdef"
    )
