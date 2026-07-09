from unittest.mock import patch

import pytest

from recipie.scraper import IngredientGroup, Recipe
from recipie.service import AddResult
from recipie.webapp import create_app


def sample_recipe() -> Recipe:
    return Recipe(
        url="https://example.com/recipe/1",
        title="テスト豚丼",
        site_name="テストキッチン",
        total_time_minutes=20,
        yields="2人分",
        ingredient_groups=[IngredientGroup(purpose=None, ingredients=["豚バラ肉 250g"])],
        instructions=["炒める。", "盛る。"],
    )


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_form_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "レシピ集に追加" in resp.get_data(as_text=True)


def test_post_adds_recipe(client):
    result = AddResult(
        recipe=sample_recipe(),
        category="メインディッシュ",
        main_ingredients=["豚バラ肉"],
        page_url="https://notion.so/created-page",
    )
    with patch("recipie.webapp.add_recipe_from_url", return_value=result) as mocked:
        resp = client.post("/add", data={"url": "https://example.com/recipe/1"})
    body = resp.get_data(as_text=True)
    assert "追加しました" in body
    assert "https://notion.so/created-page" in body
    assert "テスト豚丼" in body
    mocked.assert_called_once()


def test_post_duplicate_shows_force(client):
    result = AddResult(
        recipe=sample_recipe(), category=None, main_ingredients=[], duplicate=True
    )
    with patch("recipie.webapp.add_recipe_from_url", return_value=result):
        resp = client.post("/add", data={"url": "https://example.com/recipe/1"})
    body = resp.get_data(as_text=True)
    assert "追加済み" in body
    assert "name='force'" in body  # 「それでも追加する」ボタン
    assert "それでも追加する" in body


def test_scrape_error_shown(client):
    with patch("recipie.webapp.add_recipe_from_url", side_effect=ValueError("抽出失敗")):
        resp = client.post("/add", data={"url": "https://example.com/bad"})
    body = resp.get_data(as_text=True)
    assert "取得できませんでした" in body
    assert "抽出失敗" in body


def test_empty_url_redirects(client):
    resp = client.post("/add", data={"url": ""})
    assert resp.status_code == 302
