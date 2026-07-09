from pathlib import Path

import pytest

from recipie.scraper import parse_recipe_html

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://example.com/recipe/butadon/"


@pytest.fixture()
def recipe():
    html = (FIXTURES / "butadon.html").read_text(encoding="utf-8")
    return parse_recipe_html(html, URL)


def test_basic_fields(recipe):
    assert recipe.title == "フライパンで簡単！豚丼"
    assert recipe.yields == "2 人分" or "2" in recipe.yields
    assert recipe.total_time_minutes == 20
    assert recipe.image == "https://example.com/images/butadon.jpg"
    assert recipe.author == "テスト太郎"
    assert "豚丼" in recipe.description


def test_ingredients(recipe):
    assert len(recipe.ingredients) == 7
    assert recipe.ingredients[0] == "豚バラ肉(薄切り) 250g"


def test_instructions(recipe):
    assert len(recipe.instructions) == 4
    assert recipe.instructions[-1].endswith("完成。")


def test_keywords(recipe):
    assert recipe.keywords == ["豚肉", "丼もの", "時短"]


def test_non_recipe_page_raises():
    html = "<html><head><title>ただのページ</title></head><body><p>レシピなし</p></body></html>"
    with pytest.raises(Exception):
        parse_recipe_html(html, "https://example.com/not-recipe/")
