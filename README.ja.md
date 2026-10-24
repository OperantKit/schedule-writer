# schedule-writer

:gb: [English README](README.md)

schedule-writer は、`Conc(VI 30s, VI 60s)` のような強化スケジュールの式を、Python の呼び出し・コマンドライン・ブラウザのページから組み立てる道具です。正確な書き方を覚えていなくても式が作れます。研究者・学生・実験を組む人に向けたものです。[OperantKit](https://github.com/OperantKit) の中では、[contingency-dsl](https://github.com/OperantKit/contingency-dsl) が定め [contingency-py](https://github.com/OperantKit/contingency-py) が実行する入力を書く役目を持ちます。

- **文法を覚えなくてよい。** スケジュールと値を選べば式ができます。
- **あり得ない値ははじかれる。** `RR 5`（確率比率スケジュールは回数でなく確率を取る）は、文字列を作る前に拒否されます。
- **Python が無くても使える。** フォームとドラッグ＆ドロップのブロックエディタという 2 つのオフライン HTML ページがあり、<https://operantkit.github.io/schedule-writer/> でも公開しています。

## インストール

Python 3.11 以上。schedule-writer はまだ PyPI に公開されていないので、GitHub から入れます。依存するパッケージはありません。

```bash
pip install git+https://github.com/OperantKit/schedule-writer
pip install git+https://github.com/OperantKit/contingency-dsl-py   # 任意: 下の例のように出力を確かめるとき
```

## 例

並立スケジュールを組み立て、contingency-dsl のパーサが受理することを確かめ、値の誤りがどう報告されるかを見ます。

```python
from schedule_writer.builder import ScheduleBuilder
from contingency_dsl import parse

b = ScheduleBuilder()
source = b.concurrent(b.vi(30), b.vi(60))
print(source)                        # Conc(VI 30s, VI 60s)
print(type(parse(source)).__name__)  # Program

print(b.chained(b.fr(5), b.fi(30)))  # Chain(FR 5, FI 30s)

try:
    b.rr(5)
except ValueError as error:
    print(error)                     # RR requires a probability in (0, 1], got 5
```

できた文字列は contingency-py（`from_dsl(parse(source))`）や [operantkit-cli](https://github.com/OperantKit/operantkit-cli)（`operant run --schedule "Conc(VI 30s, VI 60s)"`）でそのまま実行できます。

## 何が入っているか

| 部品 | すること |
|---|---|
| `ScheduleBuilder`（Python） | スケジュールごとに 1 つのメソッド。単一のスケジュール 14 種（`crf`、`ext`、`fr`、`vr`、`rr`、`fi`、`vi`、`ri`、`ft`、`vt`、`rt`、`dro`、`drl`、`drh`）と、組み合わせ方 5 種（`concurrent` → `Conc`、`multiple` → `Mult`、`chained` → `Chain`、`tandem` → `Tand`、`alternative` → `Alt`）。`with_annotation` は `@reinforcer("food")` のような注釈を後ろに付けます。 |
| `schedule-writer build` | 式を 1 つ出力します。`schedule-writer build fr 5` → `FR 5`、`schedule-writer build conc "VI 30s" "VI 60s"` → `Conc(VI 30s, VI 60s)`。 |
| `schedule-writer interactive` | `vi 30` や `conc "VI 30s" "VI 60s"` などを 1 行ずつ打ち込む対話式の入力です。 |
| `schedule-writer html -o form.html` | オフラインで動く HTML のフォームを 1 ファイルで書き出します。 |
| `schedule-writer blocks -o blocks.html` | オフラインで動くドラッグ＆ドロップのブロックエディタを 1 ファイルで書き出します。スケジュールを組み合わせのブロックの中に落とすと入れ子になります。 |

時間に基づくスケジュールには単位が付きます（既定は `s`。`ms` と `min` も使えます。例: `schedule-writer build fi 2 min`）。比率スケジュールは数だけです（`FR 5`、`VR 20`）。どのメソッドの出力も、テストの中で contingency-dsl-py にパースさせています。

## 制限

- ビルダは値を検査しますが、自分の出力をパースはしません。最後にできた文字列は contingency-dsl-py でパースしてください。とくにビルダの出力に自分で書いた文字列をつなげたときは必ずです。
- 扱えるのは上に挙げたスケジュールだけです。累進比率スケジュール、切替遅延（COD）、制限時間（limited hold）、複数の段階からなる実験計画は contingency-dsl で直接書いてください。
- 注釈は書いたまま付け足すだけです。拡張の登録なしの `parse()` は注釈を受け付けません。注釈の引数は引用符で囲んだ文字列か数にします（`@reinforcer("food")`）。

## AI のコーディングエージェント向け

AI のコーディングエージェント向けの案内は [AGENTS.md](AGENTS.md) にあります。

## 開発

```bash
python -m venv .venv
.venv/bin/python -m pip install git+https://github.com/OperantKit/contingency-dsl-py
.venv/bin/python -m pip install -e . pytest pytest-cov hypothesis
.venv/bin/pytest
```

`[test]` と `[dev]` の extra は、まだ PyPI に無い公開版の contingency-dsl-py を求めるので、上のようにテストの道具を名前で入れます。両方の README の `python` ブロックはすべて `tests/test_readme_examples.py` が実行します。

## ライセンス

MIT。[LICENSE](LICENSE) を参照してください。
