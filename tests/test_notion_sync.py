from unittest.mock import MagicMock

from recipie.cli import extract_page_id
from recipie.notion_sync import (
    MAX_TEXT_LENGTH,
    add_recipe,
    extract_ingredient_name,
    guess_category,
    match_main_ingredients,
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
            IngredientGroup(purpose=None, ingredients=["豚バラ肉(薄切り) 250g", "玉ねぎ 1/2個"]),
            IngredientGroup(purpose="タレ", ingredients=["醤油 大さじ2"]),
        ],
        instructions=["切る。", "炒める。", "盛る。"],
        keywords=["豚肉", "時短"],
    )
    defaults.update(overrides)
    return Recipe(**defaults)


def test_properties_match_recipe_db_schema():
    props = recipe_to_properties(
        make_recipe(), category="メインディッシュ", main_ingredients=["豚バラ肉", "玉ねぎ"]
    )
    assert props["レシピ名"]["title"][0]["text"]["content"] == "テストレシピ"
    assert props["情報源"]["rich_text"][0]["text"]["link"]["url"] == "https://example.com/recipe/1"
    assert props["カテゴリー"]["select"]["name"] == "メインディッシュ"
    assert [m["name"] for m in props["メイン材料"]["multi_select"]] == ["豚バラ肉", "玉ねぎ"]
    assert props["調理時間"]["number"] == 20
    assert props["画像"]["url"] == "https://example.com/img.jpg"
    assert props["作成済"]["checkbox"] is False


def test_long_text_is_truncated():
    props = recipe_to_properties(make_recipe(title="あ" * 3000))
    assert len(props["レシピ名"]["title"][0]["text"]["content"]) == MAX_TEXT_LENGTH


def test_blocks_structure():
    blocks = recipe_to_blocks(make_recipe())
    assert blocks[0]["type"] == "paragraph"  # 先頭は説明文
    headings2 = [b["heading_2"]["rich_text"][0]["text"]["content"] for b in blocks if b["type"] == "heading_2"]
    assert headings2 == ["材料（2人分）", "作り方"]
    bullets = [b for b in blocks if b["type"] == "bulleted_list_item"]
    steps = [b for b in blocks if b["type"] == "numbered_list_item"]
    headings3 = [b for b in blocks if b["type"] == "heading_3"]
    assert len(bullets) == 3
    assert len(steps) == 3
    assert headings3[0]["heading_3"]["rich_text"][0]["text"]["content"] == "タレ"


def test_guess_category():
    assert guess_category(make_recipe(title="夏野菜のキーマカレー")) == "メインディッシュ"
    assert guess_category(make_recipe(title="10分浅漬け", keywords=[])) == "サイドディッシュ"
    assert guess_category(make_recipe(title="豚汁", keywords=[])) == "スープ・汁物"
    assert guess_category(make_recipe(title="名前から不明", keywords=["サラダ"])) == "サラダ"
    assert guess_category(make_recipe(title="名前から不明", keywords=[])) is None
    # 「フライパン」の「パン」に誤反応しない
    assert guess_category(make_recipe(title="フライパンで簡単！豚丼", keywords=[])) == "メインディッシュ"


def test_extract_ingredient_name():
    assert extract_ingredient_name("豚バラ肉(薄切り) 250g") == "豚バラ肉"
    assert extract_ingredient_name("玉ねぎ 1/2個") == "玉ねぎ"
    assert extract_ingredient_name("醤油 大さじ2") == "醤油"
    assert extract_ingredient_name("塩少々") == "塩"
    assert extract_ingredient_name("・にんにく 1かけ") == "にんにく"
    assert extract_ingredient_name("【A】みりん 大さじ2") == "みりん"


def test_match_main_ingredients_only_known_options():
    recipe = make_recipe()
    known = ["豚バラ肉", "玉ねぎ", "鶏もも", "味噌"]
    assert match_main_ingredients(recipe, known) == ["豚バラ肉", "玉ねぎ"]


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
