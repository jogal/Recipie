# 🍳 Recipie

ブラウザで見ているレシピページのURLを渡すだけで、レシピを自動で抽出して
Notionの **「レシピ集」データベース** に見やすいページとして追加するツールです。
**URLを貼って送信するだけのWebフォーム**と、コマンドラインの両方で使えます。

```bash
recipie serve   # → ブラウザでフォームを開き、URLを貼るだけ
```

## 追加されるページの形式

既存の「レシピ集」のスキーマ・ページ構成にそのまま合わせています。

- **プロパティ**: レシピ名 / カテゴリー(自動推定) / メイン材料(既存の選択肢から自動判定) /
  調理時間 / 作成済 / 情報源(元レシピへのリンク) / 画像
- **ページ本文**: カバー画像 → 説明 → `## 材料（分量）` の箇条書き → `## 作り方` の番号付きリスト
- カテゴリーはタイトル・キーワードから自動推定します(`--category` で指定も可能)
- メイン材料は、データベースに登録済みの選択肢と材料リストを照合して付けます。
  選択肢を勝手に増やして汚すことはありません(`--main 豚肉,玉ねぎ` で手動指定も可能)

## 対応サイト

[recipe-scrapers](https://github.com/hhursev/recipe-scrapers) によるサイト別対応
(クックパッド・キッコーマン・レタスクラブなど数百サイト)に加えて、
未対応のサイトでも schema.org/Recipe の構造化データ(JSON-LD)があれば抽出できます。
国内の主要レシピサイト(白ごはん.com、クラシル、Nadia、DELISH KITCHEN など)は
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
3. Notionで「レシピ集」データベースのページを開き、右上の `…` メニュー →
   「接続」→ 作成したインテグレーションを追加する

### 3. 「レシピ集」をツールに登録

```bash
recipie init --database <「レシピ集」データベースのURL>
```

設定は `~/.config/recipie/config.json` に保存されます。
(まだレシピ集が無い環境では `recipie init --parent <親ページのURL>` で
同じスキーマのデータベースを新規作成できます)

## 使い方その1：Webフォーム（おすすめ）

URLを貼って送信するだけでレシピ集に追加できる画面を起動します。

```bash
recipie serve
```

ブラウザで <http://127.0.0.1:8000> を開き、レシピのURLを貼って「レシピ集に追加」を
押すだけです。カテゴリーとメイン材料は自動で判定され、追加後は作成された
Notionページへのリンクと抽出結果のプレビューが表示されます。
同じURLのレシピには「追加済み」と出て、必要なら再追加もできます。

- **スマホから使う**: 同じWi-Fi内で `recipie serve --host 0.0.0.0` として起動すれば、
  スマホのブラウザから `http://<PCのIPアドレス>:8000` で開けます。
- **ブックマークレット（ワンタップ追加）**: 下記をブックマーク登録しておくと、
  レシピページを見ながらタップするだけでフォームにURLが入った状態で開きます。

  ```
  javascript:location.href='http://127.0.0.1:8000/?url='+encodeURIComponent(location.href)
  ```

## 使い方その2：コマンドライン

```bash
# レシピを追加(ブラウザのアドレスバーからURLをコピーして渡す)
recipie add https://example.com/recipe/12345

# カテゴリーやメイン材料を指定して追加
recipie add https://example.com/recipe/12345 --category メインディッシュ --main 豚バラ肉,玉ねぎ

# Notionに追加せず、抽出結果だけ確認する
recipie add https://example.com/recipe/12345 --dry-run
```

同じURLのレシピは重複追加されません(`--force` で再追加できます)。

## 開発

```bash
pip install -e ".[dev]"
pytest
```

| ファイル | 役割 |
|---|---|
| `recipie/scraper.py` | レシピページからの情報抽出 |
| `recipie/notion_sync.py` | 「レシピ集」のプロパティ/ページ本文の生成、カテゴリー推定、材料名の正規化 |
| `recipie/service.py` | URL→レシピ集追加の共通処理（CLI・Webフォーム両方が利用） |
| `recipie/webapp.py` | `serve` で起動するWebフォーム |
| `recipie/cli.py` | `init` / `add` / `serve` コマンド |
| `recipie/config.py` | トークン等の設定の読み書き |
