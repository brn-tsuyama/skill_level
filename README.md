# skill_level

厚生労働省「職業能力評価基準」（建設業）の Excel ファイルを自動ダウンロード・解析し、DuckDB に格納するパイプラインです。

---

## 概要

MHLW の公開ページから各工事業の ZIP ファイルを取得し、様式１・２で単位コードとレベルをマッピングした上で、能力ユニット Excel を解析して構造化データとして DB に保存します。

対応工事業: 7 業種（型枠・左官・防水・総合・建具・電気通信・鉄筋工事業）

---

## 依存関係

| ツール | バージョン |
|--------|-----------|
| Python | ≥ 3.12 |
| uv | 最新 |
| DuckDB | ≥ 1.2 |
| xlrd | ≥ 2.0 (.xls 読み込み) |
| openpyxl | ≥ 3.1 (.xlsx 読み込み) |

```bash
uv sync
```

---

## 使い方

```bash
# フルパイプライン（全工事業）
uv run python main.py

# スカウトモード（最初の1業種のみ構造確認、DBへの書き込みなし）
uv run python main.py --scout
```

出力: `data/db/skill_level.duckdb`

---

## パイプライン構成

```
scraper.py         Webページから工事業リストと ZIP URL を取得
downloader.py      ZIP ファイルをダウンロード → data/zips/
extractor.py       ZIP を展開（トップレベルプレフィックスを除去）→ data/extracted/
parser/            Excel を解析して SkillSheet オブジェクトに変換
database.py        DuckDB への挿入・更新
```

### parser パッケージ（SOLID 設計）

```
skill_level/parser/
  __init__.py      parse_industry_dir(), scout() — パブリック API
  _models.py       _Sheet データクラス（フォーマット非依存）
  _normalize.py    NFKC 正規化・単位コード抽出・レベル推定ユーティリティ
  _loaders.py      SheetLoader プロトコル + XlsLoader / XlsxLoader 実装
  _style.py        StyleParser — 様式１・２から単位コードマップを構築
  _unit.py         UnitParser — 1 シート → SkillSheet への変換
  _industry.py     IndustryParser — ディレクトリ全体のオーケストレーション
```

各クラスの責務は1つ（SRP）。新しいファイル形式は `SheetLoader` を実装するだけで追加可能（OCP / DIP）。

---

## DB スキーマ

```sql
industries       (id, name, category, zip_url, downloaded_at, processed_at)
skill_sheets     (id, industry_id, source_file, group_name,
                  unit_code, unit_name, unit_summary,
                  excel_type, level, job_type)
skill_criteria   (id, sheet_id, category, criterion_text, criterion_type)
required_knowledge (id, sheet_id, content)
```

`level`: `L1` / `L2` / `L3` / `L4` / `L3-L4`  
`excel_type`: `A`（10列・施工技能系）/ `B`（7列・施工管理系）  
`criterion_type`: `●`=エントリー / `■`=サブ / `○`=標準

---

## フォーマット差異への対応

| 業種 | 差異 | 対応 |
|------|------|------|
| 防水工事業 | 様式２のレベルヘッダが `レベル１` 表記 | `_LEVEL_CELL_RE` で両パターンを吸収 |
| 電気通信工事業 | 様式２シート名が括弧なし（`様式２施工管理`） | 括弧なし suffix も抽出 |
| 総合工事業 | .xlsx ファイルが混在 | `XlsxLoader` で透過的に処理 |

---

## テスト

```bash
uv run pytest                  # 全テスト（102件）
uv run mypy skill_level/       # 型チェック
uv run ruff check skill_level/ tests/  # リント
```

テストは外部サービスや実 Excel ファイルに依存しません。フィクスチャとして `_Sheet` オブジェクトを直接構築することで、全ユニットをオフラインで実行できます。
