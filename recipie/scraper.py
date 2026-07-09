"""レシピページからレシピ情報を抽出する。

recipe-scrapers のサイト別スクレイパー(クックパッド等の国内サイトを含む
数百サイト対応)を優先し、未対応サイトは schema.org/Recipe の構造化データ
(JSON-LD)から抽出する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
from recipe_scrapers import scrape_html

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


@dataclass
class IngredientGroup:
    """材料のグループ(例: 「タレ」「トッピング」)。purpose が None なら無題。"""

    purpose: str | None
    ingredients: list[str] = field(default_factory=list)


@dataclass
class Recipe:
    url: str
    title: str
    site_name: str | None = None
    author: str | None = None
    description: str | None = None
    image: str | None = None
    total_time_minutes: int | None = None
    yields: str | None = None
    ingredient_groups: list[IngredientGroup] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    @property
    def ingredients(self) -> list[str]:
        return [i for g in self.ingredient_groups for i in g.ingredients]


def _try(getter, default=None):
    """recipe-scrapers のフィールド取得は情報がないと例外を投げるため握りつぶす。"""
    try:
        value = getter()
    except Exception:
        return default
    if value in (None, "", [], 0):
        return default
    return value


def fetch_html(url: str, timeout: int = 30) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    # 文字化け対策: ヘッダに charset がない場合は本文から推定する
    if response.encoding == "ISO-8859-1":
        response.encoding = response.apparent_encoding
    return response.text


def parse_recipe_html(html: str, url: str) -> Recipe:
    """取得済みHTMLからレシピ情報を抽出する。レシピが見つからなければ ValueError。"""
    scraper = scrape_html(html, org_url=url, supported_only=False)

    title = _try(scraper.title)
    if not title:
        raise ValueError(f"レシピのタイトルを抽出できませんでした: {url}")

    groups: list[IngredientGroup] = []
    raw_groups = _try(scraper.ingredient_groups, default=[])
    for g in raw_groups or []:
        items = [i.strip() for i in g.ingredients if i and i.strip()]
        if items:
            groups.append(IngredientGroup(purpose=g.purpose, ingredients=items))
    if not groups:
        flat = _try(scraper.ingredients, default=[]) or []
        items = [i.strip() for i in flat if i and i.strip()]
        if items:
            groups.append(IngredientGroup(purpose=None, ingredients=items))

    instructions_text = _try(scraper.instructions, default="") or ""
    instructions = [line.strip() for line in instructions_text.split("\n") if line.strip()]

    if not groups and not instructions:
        raise ValueError(f"材料も手順も抽出できませんでした。レシピページではない可能性があります: {url}")

    keywords = _try(scraper.keywords, default=[]) or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]

    return Recipe(
        url=_try(scraper.canonical_url) or url,
        title=title.strip(),
        site_name=_try(scraper.site_name) or urlparse(url).hostname,
        author=_try(scraper.author),
        description=_try(scraper.description),
        image=_try(scraper.image),
        total_time_minutes=_try(scraper.total_time),
        yields=_try(scraper.yields),
        ingredient_groups=groups,
        instructions=instructions,
        keywords=[str(k).strip() for k in keywords if str(k).strip()],
    )


def scrape_recipe(url: str) -> Recipe:
    """URLからレシピを取得して抽出する。"""
    return parse_recipe_html(fetch_html(url), url)
