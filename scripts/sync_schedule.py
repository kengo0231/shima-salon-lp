#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shima Salon LP — Notion 開催スケジュール同期スクリプト

Notion DB「サロンイベントスケジュール」から当年のイベントを取得し、
index.html の <!-- SCHEDULE:START --> ～ <!-- SCHEDULE:END --> 間の
月別グリッド（.sched-grid）を再生成する。

- トークンは環境変数 NOTION_TOKEN から読む（このファイルには秘密情報を一切含めない）。
- ネットワークは curl 経由（実行環境のSSL事情に左右されにくくするため）。
- ローカル手動実行と GitHub Actions の両方で動作する。

使い方:
    NOTION_TOKEN=xxxx python3 scripts/sync_schedule.py
"""
import os
import re
import sys
import json
import subprocess

DB_ID = "2bf255fa-038d-80e7-b48c-e68fe27c39bc"   # サロンイベントスケジュール（公開情報・非機密）
# 掲載対象年（カンマ区切り・記載順に表示）。例: "2026,2027"
YEARS = [y.strip() for y in os.environ.get("SCHEDULE_YEARS", "2026,2027").split(",") if y.strip()]
NOTION_VERSION = "2022-06-28"
DATE_PROP = "開催期間"
TYPE_PROP = "イベントタイプ"

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.normpath(os.path.join(HERE, "..", "index.html"))

# 海外扱いにするイベントタイプ
OVERSEAS_TYPES = {"海外視察", "海外アテンド"}
# 公開スケジュールから除外するイベントタイプ（環境変数でカンマ区切り上書き可）
#   既定: ウェビナー（毎週開催・オンライン。機能セクションで訴求済み）／健康管理（社内ウェルネス）
EXCLUDE_TYPES = set(
    t.strip() for t in os.environ.get("SCHEDULE_EXCLUDE_TYPES", "ウェビナー,健康管理").split(",") if t.strip()
)
# 絵文字・国旗・記号を除去する正規表現
_EMOJI = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"   # 国旗（Regional Indicator）
    "\U0001F000-\U0001FAFF"   # 絵文字・ピクトグラム・囲み文字（🈵等）
    "\U00002600-\U000027BF"   # その他記号
    "\U00002B00-\U00002BFF"   # 記号・矢印
    "️‍"            # 異体字セレクタ・ZWJ
    "]"
)
_JP_FLAG = "\U0001F1EF\U0001F1F5"  # 🇯🇵


def notion_query(body):
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        sys.exit("ERROR: 環境変数 NOTION_TOKEN が設定されていません。")
    proc = subprocess.run(
        [
            "curl", "-s", "--max-time", "30", "-X", "POST",
            f"https://api.notion.com/v1/databases/{DB_ID}/query",
            "-H", f"Authorization: Bearer {token}",
            "-H", f"Notion-Version: {NOTION_VERSION}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(body),
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"ERROR: curl 失敗 (code {proc.returncode}): {proc.stderr[:300]}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"ERROR: Notion応答をJSON解析できません: {proc.stdout[:300]}")
    if data.get("object") == "error":
        sys.exit(f"ERROR: Notion API {data.get('status')} {data.get('code')}: {data.get('message')}")
    return data


def fetch_all():
    rows, cursor = [], None
    while True:
        body = {"page_size": 100, "sorts": [{"property": DATE_PROP, "direction": "ascending"}]}
        if cursor:
            body["start_cursor"] = cursor
        data = notion_query(body)
        rows += data.get("results", [])
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return rows


def title_text(prop):
    if not prop:
        return ""
    key = "title" if prop.get("type") == "title" else "rich_text"
    return "".join(x.get("plain_text", "") for x in prop.get(key, []))


def clean_name(raw):
    s = _EMOJI.sub("", raw)
    s = s.replace("　", " ")
    s = re.sub(r"\s*※.*$", "", s)          # 「※満員」等の注記を除去
    s = re.sub(r"\s*日程未定\s*", " ", s)   # 「日程未定」表記を除去（日付側で表現）
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^日本\s*", "", s)          # 「日本 福岡」→「福岡」（赤ドットで国内は表現）
    return s or "イベント"


def classify(raw_name, ev_type):
    flags = re.findall(r"[\U0001F1E6-\U0001F1FF]{2}", raw_name)
    if flags:
        return "jp" if _JP_FLAG in flags else "ov"
    return "ov" if ev_type in OVERSEAS_TYPES else "jp"


def fmt_date(start, end):
    sm, sd = int(start[5:7]), int(start[8:10])
    if end and end[:10] != start[:10]:
        em, ed = int(end[5:7]), int(end[8:10])
        return f"{sm}/{sd}-{ed}" if em == sm else f"{sm}/{sd}-{em}/{ed}"
    return f"{sm}/{sd}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_grid(rows):
    # 年 -> {月: [events]}
    data = {y: {m: [] for m in range(1, 13)} for y in YEARS}
    total = 0
    for r in rows:
        props = r.get("properties", {})
        date = props.get(DATE_PROP, {}).get("date")
        if not date or not date.get("start"):
            continue
        start = date["start"]
        year = start[:4]
        if year not in data:
            continue
        sel = props.get(TYPE_PROP, {}).get("select")
        ev_type = sel["name"] if sel else ""
        if ev_type in EXCLUDE_TYPES:
            continue
        raw_name = title_text(props.get("イベント名"))
        name = clean_name(raw_name)
        cls = classify(raw_name, ev_type)
        d = "日程調整中" if "未定" in raw_name else fmt_date(start, date.get("end"))
        data[year][int(start[5:7])].append((start, cls, name, d))
        total += 1

    blocks = []
    for year in YEARS:
        cards = []
        for m in range(1, 13):
            evs = sorted(data[year][m], key=lambda x: x[0])
            if not evs:
                continue  # イベントが無い月は非表示
            lis = "".join(
                f'<li class="{cls}">{esc(name)}（{d}）</li>' for _, cls, name, d in evs
            )
            cards.append(
                f'<div class="sched reveal"><div class="sched__m latin">{m}<em>月</em></div><ul>{lis}</ul></div>'
            )
        if not cards:
            continue  # イベントが無い年は非表示
        grid = '<div class="sched-grid">\n        ' + "\n        ".join(cards) + "\n      </div>"
        blocks.append(
            f'<div class="sched-year-block reveal">\n      <h3 class="sched-year latin">{year}<span>年</span></h3>\n      {grid}\n    </div>'
        )

    if not blocks:
        return '<div class="sched-grid"><p style="grid-column:1/-1;text-align:center;color:var(--muted)">開催予定は準備中です。</p></div>', 0
    return "\n    ".join(blocks), total


def main():
    rows = fetch_all()
    grid_html, total = build_grid(rows)
    with open(INDEX, encoding="utf-8") as f:
        doc = f.read()

    pattern = re.compile(r"(<!-- SCHEDULE:START[^\n]*-->)(.*?)(<!-- SCHEDULE:END -->)", re.S)
    if not pattern.search(doc):
        sys.exit("ERROR: index.html に SCHEDULE:START / END マーカーが見つかりません。")

    new_block = lambda mo: f"{mo.group(1)}\n    {grid_html}\n    {mo.group(3)}"
    new_doc = pattern.sub(new_block, doc)

    if new_doc == doc:
        print(f"変更なし（{'/'.join(YEARS)}年 {total}件）")
        return
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(new_doc)
    print(f"更新しました: {'/'.join(YEARS)}年 {total}件 をスケジュールに反映")


if __name__ == "__main__":
    main()
