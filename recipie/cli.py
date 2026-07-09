"""recipie コマンドラインインターフェース。

使い方:
    recipie init --database <「レシピ集」データベースのURL>   # 初回セットアップ
    recipie add <レシピページのURL>                            # レシピを追加
"""

from __future__ import annotations

import argparse
import getpass
import re
import sys

from notion_client import Client

from . import notion_sync, scraper, service
from .config import Config, load_config, save_config

PAGE_ID_RE = re.compile(r"([0-9a-f]{32})|([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")


def extract_page_id(value: str) -> str:
    """NotionのURLまたはIDからページ/データベースIDを取り出す。"""
    candidates = PAGE_ID_RE.findall(value.lower().split("?")[0])
    if not candidates:
        raise SystemExit(f"NotionのIDを読み取れませんでした: {value}")
    raw = "".join(candidates[-1]).replace("-", "")
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


def require_token(config: Config) -> str:
    if config.notion_token:
        return config.notion_token
    print("Notionインテグレーションのトークンが必要です。")
    print("https://www.notion.so/my-integrations で作成できます(ntn_ で始まる文字列)。")
    token = getpass.getpass("トークンを入力: ").strip()
    if not token:
        raise SystemExit("トークンが入力されませんでした。")
    return token


def cmd_init(args: argparse.Namespace) -> None:
    if bool(args.database) == bool(args.parent):
        raise SystemExit("--database (既存のレシピ集を使う) または --parent (新規作成) のどちらか一方を指定してください。")

    config = load_config()
    config.notion_token = args.token or require_token(config)
    notion = Client(auth=config.notion_token)

    if args.database:
        database_id = extract_page_id(args.database)
        title, _ = notion_sync.get_database_info(notion, database_id)
        print(f"✅ 既存のデータベース「{title or notion_sync.DB_TITLE}」を使います (id: {database_id})")
    else:
        parent_id = extract_page_id(args.parent)
        database_id = notion_sync.create_database(notion, parent_id)
        print(f"✅ データベース「{notion_sync.DB_TITLE}」を作成しました (id: {database_id})")

    config.database_id = database_id
    save_config(config)
    print("   これから `recipie add <レシピのURL>` でレシピを追加できます。")


def print_recipe(recipe: scraper.Recipe, category: str | None, mains: list[str]) -> None:
    print(f"📖 {recipe.title}")
    meta = [m for m in [
        recipe.site_name,
        f"{recipe.total_time_minutes}分" if recipe.total_time_minutes else None,
        recipe.yields,
        f"カテゴリー: {category}" if category else None,
        f"メイン材料: {', '.join(mains)}" if mains else None,
    ] if m]
    if meta:
        print("   " + " / ".join(meta))
    for group in recipe.ingredient_groups:
        if group.purpose:
            print(f"   [{group.purpose}]")
        for item in group.ingredients:
            print(f"   ・{item}")
    for i, step in enumerate(recipe.instructions, 1):
        print(f"   {i}. {step}")


def cmd_add(args: argparse.Namespace) -> None:
    mains = [m.strip() for m in (args.main or "").split(",") if m.strip()]

    if args.dry_run:
        print(f"🔍 レシピを取得中: {args.url}")
        recipe = scraper.scrape_recipe(args.url)
        category = args.category or notion_sync.guess_category(recipe)
        print_recipe(recipe, category, mains)
        print("(--dry-run のため、Notionには追加していません)")
        return

    print(f"🔍 レシピを取得中: {args.url}")
    try:
        result = service.add_recipe_from_url(
            args.url,
            category=args.category or None,
            main_ingredients=mains or None,
            force=args.force,
        )
    except service.ConfigError as e:
        raise SystemExit(str(e))

    print_recipe(result.recipe, result.category, result.main_ingredients)
    if result.duplicate:
        raise SystemExit("⚠️ このレシピは追加済みです。もう一度追加するには --force を付けてください。")
    print(f"✅ レシピ集に追加しました: {result.page_url}")


def cmd_serve(args: argparse.Namespace) -> None:
    from . import webapp

    webapp.serve(host=args.host, port=args.port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recipie",
        description="ブラウザで見ているレシピをNotionの「レシピ集」に追加する",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="使うNotionデータベースを設定する(初回のみ)")
    p_init.add_argument("--database", help="既存の「レシピ集」データベースのURLまたはID")
    p_init.add_argument("--parent", help="レシピ集を新規作成する場合の親ページのURLまたはID")
    p_init.add_argument("--token", help="Notionインテグレーションのトークン(省略時は対話入力)")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="レシピページのURLからレシピ集に追加する")
    p_add.add_argument("url", help="レシピページのURL")
    p_add.add_argument("--category", help=f"カテゴリー(省略時は自動推定: {', '.join(notion_sync.CATEGORIES)})")
    p_add.add_argument("--main", help="メイン材料をカンマ区切りで指定(省略時はDBの既存選択肢から自動判定)")
    p_add.add_argument("--dry-run", action="store_true", help="抽出結果の表示のみでNotionには追加しない")
    p_add.add_argument("--force", action="store_true", help="追加済みでも再追加する")
    p_add.set_defaults(func=cmd_add)

    p_serve = sub.add_parser("serve", help="URLを貼るだけで追加できるWebフォームを起動する")
    p_serve.add_argument("--host", default="127.0.0.1", help="待ち受けホスト(既定: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8000, help="待ち受けポート(既定: 8000)")
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
