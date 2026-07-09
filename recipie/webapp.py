"""URLを貼って送信するだけでレシピ集に追加するWebフォーム。

`recipie serve` で起動し、ブラウザ(スマホ可)からURLを送信すると、
既存のCLIと同じ処理で「レシピ集」にレシピを追加する。
"""

from __future__ import annotations

import html

from flask import Flask, redirect, request, url_for

from . import notion_sync
from .config import load_config
from .service import AddResult, ConfigError, add_recipe_from_url

PAGE_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans",
    "Yu Gothic UI", sans-serif;
  margin: 0; padding: 24px 16px; line-height: 1.6;
  background: #faf8f5; color: #23201c;
}
@media (prefers-color-scheme: dark) {
  body { background: #1c1a17; color: #ece7df; }
  .card { background: #26231f !important; }
  input, select { background: #1c1a17 !important; color: #ece7df !important;
    border-color: #4a453d !important; }
}
.wrap { max-width: 560px; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 4px; }
.sub { color: #8a8377; margin: 0 0 24px; font-size: 0.9rem; }
.card {
  background: #fff; border-radius: 16px; padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 16px;
}
label { display: block; font-weight: 600; margin: 0 0 6px; font-size: 0.9rem; }
input, select {
  width: 100%; padding: 12px 14px; font-size: 1rem; border-radius: 10px;
  border: 1px solid #ddd6cc; background: #fff; margin-bottom: 14px;
}
.row { display: flex; gap: 10px; }
.row > div { flex: 1; }
button {
  width: 100%; padding: 14px; font-size: 1.05rem; font-weight: 700;
  color: #fff; background: #e8703a; border: none; border-radius: 10px;
  cursor: pointer;
}
button:hover { background: #d9612d; }
.msg { padding: 14px 16px; border-radius: 12px; margin-bottom: 16px; font-weight: 500; }
.msg.ok { background: #e5f3e2; color: #216016; }
.msg.warn { background: #fbf0d9; color: #7a5a12; }
.msg.err { background: #f7e0dc; color: #8a2b1c; }
@media (prefers-color-scheme: dark) {
  .msg.ok { background: #1f3a1a; color: #b6e6ad; }
  .msg.warn { background: #3a3115; color: #f0d99a; }
  .msg.err { background: #3a1f1a; color: #f0b6ab; }
}
a { color: #e8703a; }
.preview h2 { font-size: 1.15rem; margin: 0 0 4px; }
.preview .meta { color: #8a8377; font-size: 0.85rem; margin: 0 0 12px; }
.preview h3 { font-size: 0.95rem; margin: 14px 0 4px; }
.preview ul, .preview ol { margin: 0; padding-left: 20px; }
.preview li { margin: 2px 0; }
"""


def _chip(text: str) -> str:
    return html.escape(text)


def render_page(body: str, title: str = "レシピ集に追加") -> str:
    return (
        "<!doctype html><html lang='ja'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{PAGE_CSS}</style></head>"
        f"<body><div class='wrap'>{body}</div></body></html>"
    )


def render_form(prefill_url: str = "") -> str:
    options = "".join(
        f"<option value='{_chip(c)}'>{_chip(c)}</option>" for c in notion_sync.CATEGORIES
    )
    return f"""
    <h1>🍳 レシピ集に追加</h1>
    <p class='sub'>レシピページのURLを貼って送信するだけ。カテゴリー・メイン材料は自動で判定します。</p>
    <form method='post' action='{url_for("add")}' class='card'>
      <label for='url'>レシピのURL</label>
      <input id='url' name='url' type='url' required placeholder='https://...'
        value='{_chip(prefill_url)}' autofocus>
      <div class='row'>
        <div>
          <label for='category'>カテゴリー（任意）</label>
          <select id='category' name='category'>
            <option value=''>自動で判定</option>{options}
          </select>
        </div>
        <div>
          <label for='main'>メイン材料（任意）</label>
          <input id='main' name='main' placeholder='自動判定（カンマ区切りで指定可）'>
        </div>
      </div>
      <button type='submit'>レシピ集に追加</button>
    </form>
    """


def render_preview(result: AddResult) -> str:
    r = result.recipe
    meta_parts = [p for p in [
        r.site_name,
        f"{r.total_time_minutes}分" if r.total_time_minutes else None,
        r.yields,
        f"カテゴリー: {result.category}" if result.category else None,
    ] if p]
    meta = " ／ ".join(_chip(m) for m in meta_parts)
    mains = ""
    if result.main_ingredients:
        mains = "<p class='meta'>メイン材料: " + _chip("、".join(result.main_ingredients)) + "</p>"

    ing = ""
    for g in r.ingredient_groups:
        if g.purpose:
            ing += f"<h3>{_chip(g.purpose)}</h3>"
        ing += "<ul>" + "".join(f"<li>{_chip(i)}</li>" for i in g.ingredients) + "</ul>"

    steps = "<ol>" + "".join(f"<li>{_chip(s)}</li>" for s in r.instructions) + "</ol>"

    return f"""
    <div class='card preview'>
      <h2>{_chip(r.title)}</h2>
      <p class='meta'>{meta}</p>
      {mains}
      <h3>材料</h3>{ing}
      <h3>作り方</h3>{steps}
    </div>
    """


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        prefill = request.args.get("url", "")
        return render_page(render_form(prefill))

    @app.get("/add")
    def add_get():
        # ブックマークレット等からGET /add?url=... で来ても動くようにする
        url = request.args.get("url", "")
        if not url:
            return redirect(url_for("index"))
        return _do_add(url, "", "", force=False)

    @app.post("/add")
    def add():
        return _do_add(
            request.form.get("url", "").strip(),
            request.form.get("category", "").strip(),
            request.form.get("main", "").strip(),
            force=request.form.get("force") == "1",
        )

    def _do_add(url: str, category: str, main: str, *, force: bool) -> str:
        if not url:
            return redirect(url_for("index"))
        mains = [m.strip() for m in main.split(",") if m.strip()] or None
        try:
            result = add_recipe_from_url(
                url, category=category or None, main_ingredients=mains, force=force
            )
        except ConfigError as e:
            return render_page(
                f"<div class='msg err'>{_chip(str(e))}</div>" + render_form(url)
            )
        except Exception as e:  # noqa: BLE001 — 抽出失敗などは画面に出す
            return render_page(
                f"<div class='msg err'>レシピを取得できませんでした: {_chip(str(e))}</div>"
                + render_form(url)
            )

        if result.duplicate:
            force_form = f"""
            <div class='msg warn'>このレシピは追加済みです。</div>
            <form method='post' action='{url_for("add")}' class='card'>
              <input type='hidden' name='url' value='{_chip(url)}'>
              <input type='hidden' name='category' value='{_chip(category)}'>
              <input type='hidden' name='main' value='{_chip(main)}'>
              <input type='hidden' name='force' value='1'>
              <button type='submit'>それでも追加する</button>
            </form>
            """
            return render_page(
                force_form + render_preview(result)
                + f"<p style='text-align:center'><a href='{url_for('index')}'>別のレシピを追加</a></p>"
            )

        link = (
            f"<a href='{_chip(result.page_url)}' target='_blank'>Notionで開く →</a>"
            if result.page_url else ""
        )
        return render_page(
            f"<div class='msg ok'>✅ レシピ集に追加しました！ {link}</div>"
            + render_preview(result)
            + f"<p style='text-align:center'><a href='{url_for('index')}'>続けて別のレシピを追加</a></p>"
        )

    return app


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    config = load_config()
    if not config.notion_token or not config.database_id:
        print("⚠️ 先に `recipie init --database <レシピ集のURL>` でセットアップしてください。")
    print(f"🍳 レシピ集フォームを起動します → http://{host}:{port}")
    print("   停止するには Ctrl+C")
    create_app().run(host=host, port=port)
