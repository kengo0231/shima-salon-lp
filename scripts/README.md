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

## お名前.com（PHP）で自動同期する場合
GitHub / FTP再アップを使わず、**お名前.comサーバー単体で自動同期**する方式。ページ表示時に
`schedule.php` がNotionを取得（1時間キャッシュ）してスケジュールを描画する。Notionを更新すれば
最大1時間以内に自動反映され、再アップロードは不要。

### FTP でアップロードするファイル（Web公開領域へ）
```
index.php            ← index.html の代わりにこちら（schedule.php を include）
schedule.php         ← Notion取得＋キャッシュ＋グリッド生成
notion-config.php    ← Notionトークン（1行）。※GitHub非コミット・直接アクセス禁止
.htaccess            ← index.php優先・notion-config.php保護・ディレクトリ一覧禁止
css/  img/           ← そのまま
```
- **index.html はアップしない**（.htaccess で index.php を優先するが、混同を避けるため）。
- `scripts/` `.github/` `cache/` はアップ不要（`cache/` は初回表示時にPHPが自動生成）。
- 前提: プランで **PHP が使え、PHPから外部HTTPS（curl/allow_url_fopen）が可能**なこと。

### 運用
- Notion で予定を編集 → 最大1時間で反映（`schedule.php` の `$SCHEDULE_TTL` で調整可）。
- LPのデザイン/文言を変えたら `python3 scripts/build_onamae.py` で **index.php を作り直して**再アップ。
- トークンを変えたら `notion-config.php` の1行を差し替えて再アップ。

## Notion DB のマッピング
| LP表示 | Notion プロパティ |
|---|---|
| イベント名（絵文字・「日本」除去、`※`注記除去） | イベント名（title） |
| 日付（`M/D` / 範囲。「未定」なら「日程調整中」） | 開催期間（date） |
| 赤=日本 / 青=海外 の色分け | イベントタイプ（select）＋国旗絵文字 |
