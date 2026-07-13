<?php
/**
 * Shima Salon LP — Notion 開催スケジュール（PHP・キャッシュ付き）
 *
 * index.php から include して使う。<div class="sched-grid">…</div> を出力する。
 * Notion トークンは notion-config.php（同ディレクトリ・.htaccessで直接アクセス禁止）から取得。
 * 表示時にキャッシュ（既定1時間）が新しければそれを返し、古ければNotionを取得して更新する。
 */

// ===== 設定 =====
$SCHEDULE_TOKEN    = @include __DIR__ . '/notion-config.php';   // トークン文字列を返すファイル
$SCHEDULE_DB       = '2bf255fa-038d-80e7-b48c-e68fe27c39bc';    // サロンイベントスケジュール（非機密）
$SCHEDULE_YEAR     = '2026';                                    // 掲載年（見出しと一致させる）
$SCHEDULE_EXCLUDE  = array('ウェビナー', '健康管理');           // 非掲載のイベントタイプ
$SCHEDULE_OVERSEAS = array('海外視察', '海外アテンド');         // 青（海外）扱いのタイプ
$SCHEDULE_TTL      = 3600;                                      // キャッシュ有効秒数（1時間）
$SCHEDULE_CACHE    = __DIR__ . '/cache/schedule.html';

// ===== 実処理（関数定義は下部） =====
echo shima_schedule_html($SCHEDULE_TOKEN, $SCHEDULE_DB, $SCHEDULE_YEAR,
    $SCHEDULE_EXCLUDE, $SCHEDULE_OVERSEAS, $SCHEDULE_TTL, $SCHEDULE_CACHE);


function shima_schedule_html($token, $db, $year, $exclude, $overseas, $ttl, $cache) {
    // URL に ?refresh=1 を付けるとキャッシュを無視して即時再取得（動作確認・即反映用）
    $force = !empty($_GET['refresh']);
    // 1) 新しいキャッシュがあれば即返す
    if (!$force && is_file($cache) && (time() - filemtime($cache) < $ttl)) {
        $c = @file_get_contents($cache);
        if ($c !== false && $c !== '') return $c;
    }
    // 2) Notion から生成
    $html = null;
    if (is_string($token) && $token !== '') {
        $rows = shima_notion_fetch_all($token, $db);
        if ($rows !== null) {
            $html = shima_build_grid($rows, $year, $exclude, $overseas);
            @mkdir(dirname($cache), 0755, true);
            @file_put_contents($cache, $html, LOCK_EX);
        }
    }
    // 3) 取得失敗時は 古いキャッシュ → 最終フォールバック
    if ($html === null) {
        if (is_file($cache)) {
            $c = @file_get_contents($cache);
            if ($c !== false && $c !== '') return $c;
        }
        return '<div class="sched-grid"><p style="grid-column:1/-1;text-align:center;color:var(--muted)">スケジュールは準備中です。</p></div>';
    }
    return $html;
}

function shima_http_post($url, $headers, $body) {
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, array(
            CURLOPT_POST => true,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 20,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_POSTFIELDS => $body,
        ));
        $res  = curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        return ($res !== false && $code === 200) ? $res : null;
    }
    $ctx = stream_context_create(array('http' => array(
        'method'        => 'POST',
        'header'        => implode("\r\n", $headers),
        'content'       => $body,
        'timeout'       => 20,
        'ignore_errors' => true,
    )));
    $res = @file_get_contents($url, false, $ctx);
    return $res !== false ? $res : null;
}

function shima_notion_fetch_all($token, $db) {
    $rows = array();
    $cursor = null;
    $headers = array(
        "Authorization: Bearer $token",
        "Notion-Version: 2022-06-28",
        "Content-Type: application/json",
    );
    for ($i = 0; $i < 20; $i++) { // 安全上限（最大2000件）
        $body = array('page_size' => 100, 'sorts' => array(array('property' => '開催期間', 'direction' => 'ascending')));
        if ($cursor) $body['start_cursor'] = $cursor;
        $res = shima_http_post("https://api.notion.com/v1/databases/$db/query", $headers,
            json_encode($body, JSON_UNESCAPED_UNICODE));
        if ($res === null) return null;
        $d = json_decode($res, true);
        if (!is_array($d) || (isset($d['object']) && $d['object'] === 'error')) return null;
        foreach ($d['results'] as $r) $rows[] = $r;
        if (empty($d['has_more'])) break;
        $cursor = isset($d['next_cursor']) ? $d['next_cursor'] : null;
        if (!$cursor) break;
    }
    return $rows;
}

function shima_title_text($prop) {
    if (!$prop) return '';
    $key = (isset($prop['type']) && $prop['type'] === 'title') ? 'title' : 'rich_text';
    $out = '';
    if (!empty($prop[$key])) {
        foreach ($prop[$key] as $x) $out .= isset($x['plain_text']) ? $x['plain_text'] : '';
    }
    return $out;
}

function shima_clean_name($raw) {
    // 絵文字・国旗・記号を除去
    $s = preg_replace('/[\x{1F000}-\x{1FAFF}\x{1F1E6}-\x{1F1FF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE0F}\x{200D}]/u', '', $raw);
    $s = str_replace("\xe3\x80\x80", ' ', $s);       // 全角スペース U+3000
    $s = preg_replace('/\s*※.*$/u', '', $s);          // 「※満員」等の注記を除去
    $s = preg_replace('/\s*日程未定\s*/u', ' ', $s);   // 「日程未定」表記を除去
    $s = trim(preg_replace('/\s+/u', ' ', $s));
    $s = preg_replace('/^日本\s*/u', '', $s);          // 「日本 福岡」→「福岡」
    return $s !== '' ? $s : 'イベント';
}

function shima_classify($raw, $type, $overseas) {
    if (preg_match('/[\x{1F1E6}-\x{1F1FF}]{2}/u', $raw)) {
        return (strpos($raw, "\xf0\x9f\x87\xaf\xf0\x9f\x87\xb5") !== false) ? 'jp' : 'ov'; // 🇯🇵
    }
    return in_array($type, $overseas, true) ? 'ov' : 'jp';
}

function shima_fmt_date($start, $end) {
    $sm = (int)substr($start, 5, 2);
    $sd = (int)substr($start, 8, 2);
    if ($end && substr($end, 0, 10) !== substr($start, 0, 10)) {
        $em = (int)substr($end, 5, 2);
        $ed = (int)substr($end, 8, 2);
        return $em === $sm ? "$sm/$sd-$ed" : "$sm/$sd-$em/$ed";
    }
    return "$sm/$sd";
}

function shima_build_grid($rows, $year, $exclude, $overseas) {
    $months = array();
    for ($m = 1; $m <= 12; $m++) $months[$m] = array();

    foreach ($rows as $r) {
        $props = isset($r['properties']) ? $r['properties'] : array();
        $date  = isset($props['開催期間']['date']) ? $props['開催期間']['date'] : null;
        if (!$date || empty($date['start'])) continue;
        $start = $date['start'];
        if (substr($start, 0, 4) !== $year) continue;
        $type = isset($props['イベントタイプ']['select']['name']) ? $props['イベントタイプ']['select']['name'] : '';
        if (in_array($type, $exclude, true)) continue;

        $m    = (int)substr($start, 5, 2);
        $raw  = shima_title_text(isset($props['イベント名']) ? $props['イベント名'] : null);
        $name = shima_clean_name($raw);
        $cls  = shima_classify($raw, $type, $overseas);
        $d    = (strpos($raw, '未定') !== false) ? '日程調整中' : shima_fmt_date($start, isset($date['end']) ? $date['end'] : null);
        $months[$m][] = array('start' => $start, 'cls' => $cls, 'name' => $name, 'd' => $d);
    }

    $cards = array();
    for ($m = 1; $m <= 12; $m++) {
        usort($months[$m], function ($a, $b) { return strcmp($a['start'], $b['start']); });
        $lis = '';
        foreach ($months[$m] as $e) {
            $lis .= '<li class="' . $e['cls'] . '">'
                  . htmlspecialchars($e['name'], ENT_QUOTES, 'UTF-8')
                  . '（' . htmlspecialchars($e['d'], ENT_QUOTES, 'UTF-8') . '）</li>';
        }
        $cards[] = '<div class="sched reveal"><div class="sched__m latin">' . $m . '<em>月</em></div><ul>' . $lis . '</ul></div>';
    }
    return "<div class=\"sched-grid\">\n      " . implode("\n      ", $cards) . "\n    </div>";
}
