# schedule-writer

:gb: [English README](README.md)

強化スケジュール DSL プログラム（`contingency-dsl` の表層構文）を手書き
することなく組み立てるためのビルダ API、CLI、スタンドアロン HTML ツール。

想定読者は、文法を暗記せずドロップダウンとパラメータ入力から
`Conc(VI 30s, VI 60s)` のようなスケジュールを組み立てたい実務家と研究者。

## コンポーネント

- **`schedule_writer.builder`** — 純 Python の流暢な API。関数は DSL
  文字列を返す; パース・評価・実行は一切行わない。希望があれば
  コンシューマは出力を `contingency-dsl-py` にパイプして検証できる。
- **`schedule_writer.cli`** — 2 つのサブコマンドを持つコマンドライン・
  エントリポイント:
  - `schedule-writer build <schedule> <args...>` — 単発構築
    （例: `schedule-writer build fr 5` は `FR 5` を出力）。
  - `schedule-writer interactive` — スケジュール・ファミリとパラメータ
    をプロンプトで聞き、結果の DSL 文字列を出力するガイド付き REPL。
- **`schedule_writer.standalone_html`** — CDN 無し、外部スクリプト無しの
  自己完結型 HTML ファイルを生成する。バニラ JS のドロップダウンと
  入力でクライアントサイドで DSL 文字列を計算する。Python 環境を持た
  ないユーザへのツール配布に有用。
- **`schedule_writer.block_editor_html`** — ビジュアルブロック型のドラッグ＆ドロップ
  エディタを単一の自己完結型 HTML として生成する。左のパレット
  から原子スケジュール・コンビネータ・アノテーションのブロックを
  キャンバスへドラッグし、複合ブロックのスロットに別のブロックを入れ子に
  ドロップできる。DSL 文字列はブロック木からライブでコンパイルされる。
  エンジニアではない実務家を対象とする。

## インストール（開発）

```bash
mise exec -- python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## 30 秒で動く例

```bash
pip install git+https://github.com/OperantKit/schedule-writer
pip install contingency-dsl-py   # 下のように出力を検査するときだけ必要
```

DSL の構文を書かずにスケジュールを組み立て、パーサが受理することを確かめる:

```python
from schedule_writer.builder import ScheduleBuilder
from contingency_dsl import parse

b = ScheduleBuilder()
source = b.concurrent(b.vi(30), b.vi(60))
print(source)  # Conc(VI 30s, VI 60s)
print(type(parse(source)).__name__)  # Program — 正しい contingency-dsl の文字列

try:
    b.rr(5)  # 確率比率 (RR) は回数でなく確率を取る
except ValueError as error:
    print(error)  # RR requires a probability in (0, 1], got 5
```

この文字列は [contingency-py](https://github.com/OperantKit/contingency-py)（`from_dsl(parse(source))`）に渡せばスケジュールとして動き、[operantkit-cli](https://github.com/OperantKit/operantkit-cli)（`operant run --schedule "Conc(VI 30s, VI 60s)"`）にも渡せる。

## DSL の文字列を手で書かない理由

- **どのビルダメソッドも構文解析できる DSL を出す.** 14 の単一スケジュール（CRF・EXT・FR・VR・RR・FI・VI・RI・FT・VT・RT・DRO・DRL・DRH）と 5 つの結合子（`Conc`・`Mult`・`Chain`・`Tand`・`Alt`）の出力を、`tests/test_builder_parses.py` で contingency-dsl-py に通して確かめている。
- **文字列を作る前にパラメータを検査する.** 例えば `rr` は (0, 1] の確率を要し、注釈は `@` で始まらなければならない。
- **単位と綴りが文法どおり.** 時間に基づくスケジュールには単位（`s`・`ms`・`min`）が付き、結合子は正規の名前を使う。
- **利用者に Python は要らない.** `schedule-writer html` と `schedule-writer blocks` は、同じ文字列をブラウザ内で組み立てる 1 ファイルのオフライン HTML（フォーム版とドラッグ＆ドロップのブロックエディタ）を書き出す。

## 使用方法

### ビルダ API

```python
from schedule_writer.builder import ScheduleBuilder

b = ScheduleBuilder()
b.fr(5)                       # "FR 5"
b.vi(30)                      # "VI 30s"
b.concurrent(b.vi(30), b.vi(60))   # "Conc(VI 30s, VI 60s)"
b.chained(b.fr(5), b.fi(30))       # "Chain(FR 5, FI 30s)"
b.with_annotation(b.fr(5), '@reinforcer("food")')
#   'FR 5 @reinforcer("food")'
```

### CLI

```bash
schedule-writer --help
schedule-writer build fr 5
schedule-writer build vi 30
schedule-writer build conc "VI 30s" "VI 60s"
schedule-writer interactive
```

### スタンドアロン HTML（フォーム型）

```bash
schedule-writer html --output schedule-writer.html
# schedule-writer.html を任意のブラウザで開く。オフラインで動作する。
```

### ブロックエディタ HTML（ビジュアルブロック型ドラッグ＆ドロップ）

```bash
schedule-writer blocks --output schedule-writer-blocks.html
# 任意のブラウザで開く。左のパレットからブロックをキャンバスへドラッグし、
# 複合ブロックのスロットに別のブロックを入れ子にドロップする。オフライン動作。
```

## 出力文法

生成される文字列は `contingency-dsl` の operant 文法に従う。
時間領域スケジュールはデフォルトで単位接尾辞 (`s`, `ms`, `min`) を
付加する; 比率領域スケジュールは単純な数値を発する (`FR 5`, `VR 20`)。
複合スケジュールは正典コンビネータ名を使う: `Conc`, `Mult`, `Chain`,
`Tand`, `Alt`。

## ステータス

Alpha。ビルダ API は DSL の表層構文を反映するが、結果を形式文法に
対してパース・検証することは自身で行わない。コンシューマは出力を
下流パーサへの入力テキストとして扱うべき。
