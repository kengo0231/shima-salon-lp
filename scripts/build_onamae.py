#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
お名前.com（PHP）用の index.php を index.html から生成する。

index.html のスケジュール部分（<!-- SCHEDULE:START --> ～ <!-- SCHEDULE:END -->）を
`<?php include __DIR__ . "/schedule.php"; ?>` に置き換えるだけ。
LPのデザイン/文言を変更したら、このスクリプトを再実行して index.php を作り直す。

    python3 scripts/build_onamae.py
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "index.html"))
DST = os.path.normpath(os.path.join(HERE, "..", "index.php"))

INCLUDE = '<?php include __DIR__ . "/schedule.php"; ?>'


def main():
    with open(SRC, encoding="utf-8") as f:
        html = f.read()

    pattern = re.compile(r"(<!-- SCHEDULE:START[^\n]*-->)(.*?)(<!-- SCHEDULE:END -->)", re.S)
    if not pattern.search(html):
        raise SystemExit("index.html に SCHEDULE:START / END マーカーが見つかりません。")

    php = pattern.sub(lambda m: f"{m.group(1)}\n    {INCLUDE}\n    {m.group(3)}", html)
    with open(DST, "w", encoding="utf-8") as f:
        f.write(php)
    print(f"生成しました: {DST}")


if __name__ == "__main__":
    main()
