# skill_level — Claude Code 引継ぎドキュメント

## プロジェクト概要

厚生労働省「職業能力評価基準（建設業）」の公開 Excel ファイルを自動取得・解析して DuckDB に格納するパイプライン。

- **データソース**: https://www.mhlw.go.jp/stf/newpage_04653.html
- **対象**: 建設業関係 7 業種の ZIP ファイル（型枠・左官・防水・総合・建具・電気通信・鉄筋工事業）
- **出力**: `data/db/skill_level.duckdb`（711 シート・9,331 基準行・710 必要知識レコード）

## ツール・言語

| 項目 | 内容 |
|------|------|
| 言語 | Python 3.12 |
| パッケージ管理 | `uv` |
| 型チェック | `mypy --strict` |
| リント | `ruff` |
| テスト | `pytest` |
| DB | DuckDB 1.2 |
| Excel 読み込み | xlrd (.xls) / openpyxl (.xlsx) |

```bash
uv sync                       # 依存インストール
uv run python main.py         # フルパイプライン
uv run python main.py --scout # スカウトモード（最初の1業種のみ構造確認）
uv run pytest                 # テスト（102件、全 PASS）
uv run mypy skill_level/      # 型チェック
uv run ruff check skill_level/ tests/  # リント
```

---

## ディレクトリ構成

```
skill_level/
  scraper.py         Webスクレイピング（lxml + BeautifulSoup）
  downloader.py      ZIP ダウンロード
  extractor.py       ZIP 展開（cp932 エンコーディング修正・トップレベル除去）
  parser/            Excel 解析パッケージ（SOLID 設計）
    __init__.py      parse_industry_dir(), scout() パブリック API
    _models.py       _Sheet dataclass + _cell_str
    _normalize.py    NFKC 正規化・単位コード抽出・レベル推定
    _loaders.py      SheetLoader Protocol + XlsLoader / XlsxLoader
    _style.py        StyleParser — 様式１・２からユニットマップ構築
    _unit.py         UnitParser — 1 シート → SkillSheet
    _industry.py     IndustryParser — ディレクトリオーケストレーション
  database.py        DuckDB スキーマ定義・CRUD
  models.py          データクラス（Industry, SkillSheet, SkillCriterion）
tests/
  conftest.py        フィクスチャ（_Sheet・ZIP・DuckDB）
  test_models.py
  test_normalize.py
  test_loaders.py
  test_style_parser.py
  test_unit_parser.py
  test_extractor.py
  test_database.py
data/
  zips/              ダウンロード済み ZIP キャッシュ
  extracted/         展開済みファイル
  db/skill_level.duckdb
  csv/criteria_flat.csv  （UTF-8 BOM、Excel で開ける）
```

---

## DB スキーマ

```sql
industries (
  id INTEGER PRIMARY KEY,
  name VARCHAR NOT NULL UNIQUE,
  category VARCHAR NOT NULL,
  zip_url VARCHAR,
  downloaded_at TIMESTAMPTZ,
  processed_at TIMESTAMPTZ
)

skill_sheets (
  id INTEGER PRIMARY KEY,
  industry_id INTEGER NOT NULL REFERENCES industries(id),
  source_file VARCHAR NOT NULL,
  group_name VARCHAR NOT NULL,   -- 例: "06_01_施工技能"
  unit_code VARCHAR NOT NULL,    -- 例: "06C022L11"
  unit_name VARCHAR NOT NULL,    -- 例: "段取り"
  unit_summary VARCHAR,
  excel_type VARCHAR NOT NULL,   -- "A"(10列) | "B"(7列)
  level VARCHAR NOT NULL,        -- "L1"|"L2"|"L3"|"L4"|"L3-L4"
  job_type VARCHAR               -- "施工技能"|"現場管理"|"施工管理"|...
)

skill_criteria (
  id INTEGER PRIMARY KEY,
  sheet_id INTEGER NOT NULL REFERENCES skill_sheets(id),
  category VARCHAR,              -- 能力細目ラベル（マージセルは前行から引継ぎ）
  criterion_text VARCHAR NOT NULL,
  criterion_type VARCHAR         -- "●"=エントリー|"■"=サブ|"○"=標準
)

required_knowledge (
  id INTEGER PRIMARY KEY,
  sheet_id INTEGER NOT NULL REFERENCES skill_sheets(id),
  content VARCHAR NOT NULL
)
```

---

## 重要な設計決定

### Excel フォーマット差異への対応

各工事業で微妙に書式が異なる。ハードコードを避けて動的検出で吸収:

| 業種 | 差異 | 対応箇所 |
|------|------|---------|
| 防水工事業 | レベルヘッダが `レベル１` 表記（`Ｌ１` でない） | `_LEVEL_CELL_RE = re.compile(r"(?:L|レベル)(\d)$")` |
| 電気通信工事業 | 様式２シート名が括弧なし（`様式２施工管理`） | `_extract_job_type` で suffix を直接抽出 |
| 総合工事業 | `.xlsx` と `.xls` 混在 | `_XL_EXTS = (".xls", ".xlsx")` でどちらも処理 |

### 単位コード解決（`_normalize.py`）

- 全角文字列 `"０６Ｃ０２２Ｌ１１"` → NFKC で `"06C022L11"` に正規化
- `_UNIT_CODE_RE = re.compile(r"\d{2}[CScs]\d{3}L\d{2}", re.ASCII)` でマッチ
- レベル推定: `L11`→`L1`、`L22`→`L2`、`L34`→`L3-L4`

### レベル・job_type の解決優先順位（`_unit.py`）

1. 様式１・２の unit_map にある → map の値を使用
2. map に job_type が空 → グループディレクトリ名から推定
3. map に存在しない → サフィックスとディレクトリ名から推定

### ZIP エンコーディング（`extractor.py`）

- 日本語ツールの ZIP はファイル名を cp932 で保存（UTF-8 フラグなし）
- `raw.encode("cp437").decode("cp932")` で復元

---

## SOLID 設計の説明

`skill_level/parser/` は Single Responsibility / Open-Closed / Liskov / Interface Segregation / Dependency Inversion を意識した構造:

- **SRP**: 各クラスの責務は1つ（`StyleParser` はユニットマップ構築だけ、`UnitParser` は1シート解析だけ）
- **OCP**: 新しいフォーマット（例: .ods）は `SheetLoader` を実装するだけで追加可能。既存コード変更不要
- **LSP**: `XlsLoader` / `XlsxLoader` は `SheetLoader` プロトコルを満たし相互交換可能
- **ISP**: `SheetLoader` プロトコルは `load(path) -> list[_Sheet]` の1メソッドのみ
- **DIP**: `IndustryParser` は具象クラスでなく `SheetLoader` プロトコルに依存。コンストラクタインジェクション対応

---

## テスト方針

- 外部依存なし（HTTP・実 Excel ファイル不要）
- `_Sheet` オブジェクトを直接構築してユニットテスト
- DuckDB は `:memory:` 接続で DB テスト
- 業種ごとのフォーマット差異（レベル表記・シート名形式）はフィクスチャで個別にカバー

---

## CSV エクスポート

```python
import duckdb
conn = duckdb.connect("data/db/skill_level.duckdb")
conn.execute("""
    COPY (
        SELECT
            sc.id,
            i.name AS industry_name,
            ss.unit_code,
            ss.unit_name,
            ss.level,
            ss.job_type,
            ss.group_name,
            ss.unit_summary,
            sc.category,
            sc.criterion_type,
            sc.criterion_text
        FROM skill_criteria sc
        JOIN skill_sheets ss ON sc.sheet_id = ss.id
        JOIN industries i ON ss.industry_id = i.id
        ORDER BY i.name, ss.unit_code, sc.id
    ) TO 'data/csv/criteria_flat.csv'
    (HEADER, DELIMITER ',', ENCODING 'UTF8BOM')
""")
```

---

## 未対応・今後の改善案

- 様式１（能力ユニット一覧の詳細）の完全解析は未実装。現在は様式２のみ
- 建設業以外の業種（製造業関係など）は未対応
- 増分更新（差分のみ再取得）は未実装。現在は全件再処理
