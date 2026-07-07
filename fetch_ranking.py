# -*- coding: utf-8 -*-
"""StockWeather 寄付からの値上がり率ランキング(東証プライム/スタンダード/グロース 各100位)を取得し、
前営業日と比較した順位変動付きで CSV と公開サイト用 JSON に出力する。

出力:
  history/YYYY-MM-DD.json       … 当日の生データ(翌日以降の比較用、市場別)
  output/ranking_YYYY-MM-DD.csv … 当日のランキングCSV(UTF-8、3市場まとめ)
  docs/data/YYYY-MM-DD.json     … GitHub Pages 用データ
  docs/data/index.json          … 日付一覧(新しい順)
  標準出力に CSV のフルパスを表示する。
"""
import html as htmllib
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent
HISTORY = BASE / "history"
OUTPUT = BASE / "output"
DOCS_DATA = BASE / "docs" / "data"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
URL = ("https://finance.stockweather.co.jp/contents/ranking.aspx"
       "?mkt={mkt}&cat=0000&type=2")  # type=2 = 寄付からの値上がり率
# 1ページに100位まで全て載っている(ページング・Cookie不要)
MARKETS = [
    ("prime", "東証プライム", 1),
    ("standard", "東証スタンダード", 2),
    ("growth", "東証グロース", 3),
]

# ページ内の「更新日時:YYYY/MM/DD HH:MM」表記(データ時点、コロンは全角)
AS_OF_RE = re.compile(r'更新日時[：:]\s*(\d{4})/(\d{2})/(\d{2})\s*(\d{1,2}:\d{2})')

# 値セル: <td>2,531.0</td> / <td><span class="red">+393.0</span> </td> /
# <td><span class="gray">－</span></td> をすべて許容。
# [^<]* なのでセル境界(タグ)は越えられない。
_CELL = r'<td[^>]*>\s*(?:<span[^>]*>)?([^<]*)(?:</span>)?\s*</td>'

ROW_RE = re.compile(
    r'<tr>\s*'
    r'<th>(?P<sitrank>\d+)</th>\s*'
    r'<td class="ll"><a href="\./stockdetail\.aspx\?cntcode=JP&skubun=\d+'
    r'&stkcode=(?P<code>[0-9A-Z]+)&exctype=\d+">(?P<name>[^<]+)</a>'
    r'<br><span class="small">（[0-9A-Z]+）</span></td>\s*'
    r'<td class="ce"[^>]*>(?P<market>[^<]*)</td>\s*'
    + _CELL.replace('([^<]*)', '(?P<price>[^<]*)') + r'\s*'
    + _CELL.replace('([^<]*)', '(?P<change>[^<]*)') + r'\s*'
    + _CELL.replace('([^<]*)', '(?P<change_pct>[^<]*)') + r'\s*'
    r'<td class="focus">(?P<yori_pct>[^<]*)</td>')


def fetch(mkt: int) -> str:
    req = urllib.request.Request(
        URL.format(mkt=mkt), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", errors="replace")


def parse(page_html: str):
    # ランキング本体のテーブル以降のみを対象にする
    body = page_html.split("<tbody>", 1)[-1]
    rows = []
    for m in ROW_RE.finditer(body):
        d = {k: v.strip() for k, v in m.groupdict().items()}
        d["name"] = htmllib.unescape(d["name"])
        del d["sitrank"]  # 順位は取得順で振り直す
        rows.append(d)
    return rows


def main():
    today = date.today().isoformat()
    HISTORY.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    DOCS_DATA.mkdir(parents=True, exist_ok=True)

    # 前回(直近の過去ファイル)のデータを読み込み(市場別)
    prev_files = sorted(p for p in HISTORY.glob("*.json") if p.stem < today)
    prev_hist = {}
    prev_date = None
    if prev_files:
        prev_date = prev_files[-1].stem
        prev_hist = json.loads(prev_files[-1].read_text(encoding="utf-8"))

    markets_out = {}
    as_of_latest = None
    for key, label, mkt in MARKETS:
        page = fetch(mkt)
        m = AS_OF_RE.search(page)
        as_of = None
        if m:
            as_of = f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}"
            if as_of_latest is None or as_of > as_of_latest:
                as_of_latest = as_of
        stocks = parse(page)
        if not stocks:
            print(f"ERROR: {label} (mkt={mkt}) から行を抽出できませんでした"
                  "(ページ構造の変更の可能性)", file=sys.stderr)
            sys.exit(1)

        # 念のため重複コードを除去して順位を振り直す
        seen = set()
        stocks = [s for s in stocks
                  if not (s["code"] in seen or seen.add(s["code"]))]
        for i, s in enumerate(stocks, 1):
            s["rank"] = i

        # 前営業日の同市場ランキングと比較
        prev_data = {s["code"]: s["rank"]
                     for s in prev_hist.get(key, {}).get("stocks", [])}
        for s in stocks:
            if s["code"] in prev_data:
                diff = prev_data[s["code"]] - s["rank"]
                s["move"] = f"↑{diff}" if diff > 0 else (
                    f"↓{-diff}" if diff < 0 else "→")
                s["prev_rank"] = prev_data[s["code"]]
                s["move_num"] = diff
                s["is_new"] = False
            else:
                s["move"] = "NEW" if prev_data else ""
                s["prev_rank"] = ""
                s["move_num"] = None
                s["is_new"] = bool(prev_data)

        markets_out[key] = {
            "label": label,
            "as_of": as_of,
            "count": len(stocks),
            "stocks": stocks,
        }
        time.sleep(1.5)

    # 当日データを保存(同日再実行時は上書き)
    (HISTORY / f"{today}.json").write_text(
        json.dumps(markets_out, ensure_ascii=False, indent=1),
        encoding="utf-8")

    # 公開サイト(GitHub Pages)用データを保存
    site_payload = {
        "date": today,
        "as_of": as_of_latest,
        "prev_date": prev_date,
        "markets": markets_out,
    }
    (DOCS_DATA / f"{today}.json").write_text(
        json.dumps(site_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    dates = sorted((p.stem for p in DOCS_DATA.glob("????-??-??.json")),
                   reverse=True)
    (DOCS_DATA / "index.json").write_text(
        json.dumps({"dates": dates}, ensure_ascii=False), encoding="utf-8")

    # CSV を保存(3市場まとめ)
    csv_path = OUTPUT / f"ranking_{today}.csv"
    header = ["市場", "順位", "順位変動", "前日順位", "コード", "銘柄名",
              "現在値", "前日比", "前日比%", "寄付からの値上がり率"]
    lines = [",".join(header)]
    for key, label, _ in MARKETS:
        for s in markets_out[key]["stocks"]:
            cells = [label, str(s["rank"]), s["move"], str(s["prev_rank"]),
                     s["code"], s["name"], s["price"], s["change"],
                     s["change_pct"], s["yori_pct"]]
            lines.append(",".join(
                '"' + c.replace('"', '""') + '"' for c in cells))
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    print(str(csv_path))
    counts = ", ".join(f"{markets_out[k]['label']}:{markets_out[k]['count']}"
                       for k, _, _ in MARKETS)
    print(f"銘柄数: {counts} / 比較対象: {prev_date or 'なし(初回)'}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
