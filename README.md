# 🍳 Recipie

ブラウザで見ているレシピページのURLを渡すだけで、レシピを自動で抽出して
**Notionのレシピ帳データベースに見やすいページとして追加**するCLIツールです。

```
recipie add https://www.sirogohan.com/recipe/butadon/
```

## Notionにできるページのイメージ

- **データベースのプロパティ**: 名前 / URL / サイト / タグ / 調理時間(分) / 分量 / 追加日 / 作った(チェックボックス) / 評価(★)
- **ページ本文**:
  - 🔗 元レシピへのリンク(カバー画像付き)
  - 🧺 材料 — チェックボックス形式なので**そのまま買い物リストとして使える**
  - 👨‍🍳 作り方 — 番号付きリスト
  - 📝 メモ — 感想やアレンジを書き込む欄

## 対応サイト

[recipe-scrapers](https://github.com/hhursev/recipe-scrapers) によるサイト別対応
(クックパッド・キッコーマン・レタスクラブなど数百サイト)に加えて、
未対応のサイトでも schema.org/Recipe の構造化データ(JSON-LD)があれば抽出できます。
国内の主要レシピサイト(白ごはん.com、クラシル、DELISH KITCHEN など)は
ほぼ構造化データを持っているため、大半のレシピページで動作します。

## セットアップ

### 1. インストール

```bash
git clone https://github.com/jogal/Recipie.git
cd Recipie
pip install .
```

### 2. Notionインテグレーションを作成

1. https://www.notion.so/my-integrations で「新しいインテグレーション」を作成
   (名前は例えば `recipie`、対象は自分のワークスペース)
2. 表示される **シークレットトークン**(`ntn_` で始まる文字列)を控える
3. Notionで、レシピ帳を置きたいページを開き、右上の `…` メニュー →
   「接続」→ 作成したインテグレーションを追加する

### 3. レシピ帳データベースを作成

```bash
recipie init --parent <手順2で接続したページのURL>
```

ページ配下に「レシピ帳」データベースが作られ、設定が
`~/.config/recipie/config.json` に保存されます。

## 使い方

```bash
# レシピを追加(ブラウザのアドレスバーからURLをコピーして渡す)
recipie add https://example.com/recipe/12345

# タグを付けて追加
recipie add https://example.com/recipe/12345 --tags 和食,時短

# Notionに追加せず、抽出結果だけ確認する
recipie add https://example.com/recipe/12345 --dry-run
```

同じURLのレシピは重複追加されません(`--force` で再追加できます)。

## スマホ・ブラウザからの利用

- **ブックマークレット**: ブラウザのブックマークに以下を登録すると、
  レシピページを見ながらワンクリックでコマンドをコピーできます。

  ```
  javascript:navigator.clipboard.writeText('recipie add '+location.href).then(()=>alert('コマンドをコピーしました'))
  ```

- **iOSショートカット等**: 共有シートからURLを受け取り、SSH経由で
  `recipie add <URL>` を実行するショートカットを作れば、スマホからも追加できます。

## 開発

```bash
pip install -e ".[dev]"
pytest
```

| ファイル | 役割 |
|---|---|
| `recipie/scraper.py` | レシピページからの情報抽出 |
| `recipie/notion_sync.py` | Notionのデータベース/ページ生成 |
| `recipie/cli.py` | `init` / `add` コマンド |
| `recipie/config.py` | トークン等の設定の読み書き |
