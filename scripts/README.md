# 開催スケジュール Notion 同期

`index.html` の開催スケジュール（`.sched-grid`）を、Notion DB「サロンイベントスケジュール」から自動生成します。

## 仕組み
- `sync_schedule.py` が Notion API からイベントを取得し、`index.html` の
  `<!-- SCHEDULE:START -->` ～ `<!-- SCHEDULE:END -->` 間を再生成します。
- **トークンはコードに含めません**。環境変数 `NOTION_TOKEN` から読み込みます。
- GitHub Actions（`.github/workflows/sync-schedule.yml`）が **毎日 06:00 JST** に自動同期し、
  変更があれば自動コミット → GitHub Pages が更新されます。手動実行も可能（Actions → Run workflow）。

## トークンの管理
- GitHub リポジトリの **Settings → Secrets and variables → Actions → `NOTION_TOKEN`** に保存済み。
- Notion 側で、対象 DB を Integration「池内さん サロンLP連携」に「接続」しておく必要があります。

## 手動で実行する場合
```bash
NOTION_TOKEN=xxxxxxxx python3 scripts/sync_schedule.py
```

## 表示の調整（スクリプト冒頭の設定 / 環境変数）
- `SCHEDULE_YEAR`（既定 `2026`）: 掲載する年。見出し「◯◯年 開催スケジュール」と一致させる。
- `SCHEDULE_EXCLUDE_TYPES`（既定 `ウェビナー,健康管理`）: 公開スケジュールに載せないイベントタイプ。
  例）ウェビナーも載せる → `SCHEDULE_EXCLUDE_TYPES="健康管理"`
- 海外（青ドット）判定: イベント名の国旗絵文字、または種別 `海外視察 / 海外アテンド`。

## Notion DB のマッピング
| LP表示 | Notion プロパティ |
|---|---|
| イベント名（絵文字・「日本」除去、`※`注記除去） | イベント名（title） |
| 日付（`M/D` / 範囲。「未定」なら「日程調整中」） | 開催期間（date） |
| 赤=日本 / 青=海外 の色分け | イベントタイプ（select）＋国旗絵文字 |
