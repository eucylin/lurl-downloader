# CLAUDE.md — AI 開發筆記

## 專案概述

lurl.cc / myppt.cc 影片下載工具。用 Python 從 lurl.cc 和 myppt.cc 頁面提取並下載影片。兩個網站使用同一套系統，頁面結構幾乎一致。

## 技術堆疊

- Python 3.11+
- requests + BeautifulSoup4（Phase 1 簡單 HTTP）
- Playwright + Chromium（Phase 2/3 瀏覽器自動化）

## 關鍵檔案

- `download.py` — 唯一的程式檔案，包含所有邏輯
- `downloads/` — 影片下載目錄（已 gitignore）

## 頁面結構（lurl.cc / myppt.cc 共用）

- 使用 Video.js 播放器
- 影片 URL 在 `<video>` 標籤內的 `<source>` 元素
- 選擇器優先順序：`.vjs-tech source` > `#video source` > `video source` > `video[src]`
- 部分頁面有年齡驗證對話框（按鈕文字：「我已年滿18歲」）
- 部分頁面有密碼保護（lurl: `input#password`，myppt: `input#pasahaicsword`）
- myppt.cc 有額外影片元素 `#my_video_html5_api`
- 密碼提交按鈕在 `<form>` 內，文字為「立即解密」
- 密碼通常是上傳日期的 MMDD，但不一定（有例外）
- 日期從 `div.col-sm-12 span.login_span` 提取，格式 `YYYY-MM-DD`

## 已知問題與踩坑紀錄

### Cloudflare Turnstile 防護

- **問題**：Playwright headless 模式會被 Cloudflare 偵測為自動化瀏覽器，頁面完全無法載入（0 個按鈕、無 form、無 input）
- **解法**：必須使用 `headless=False` + 以下反偵測設定：
  ```python
  browser = p.chromium.launch(
      headless=False,
      args=["--disable-blink-features=AutomationControlled"],
  )
  page.add_init_script(
      'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
  )
  ```

### 密碼提交按鈕找不到

- **問題**：原本的選擇器（`button[type='submit']`、`button:has-text('送出')` 等）找不到提交按鈕
- **原因**：實際按鈕是 `<form>` 內的 `<button>`，文字為「立即解密」
- **解法**：選擇器清單第一個改為 `form button`，並加入 `button:has-text('立即解密')`

### 密碼不一定是日期

- **問題**：有些頁面的密碼不是上傳日期的 MMDD（例如密碼是 `7777`）
- **解法**：支援 `--password` / `-p` CLI 參數手動指定密碼，且當自動密碼失敗時提示使用者手動輸入

### Phase 1 有時能成功

- 沒有密碼保護的頁面，Phase 1（純 HTTP 請求）就能直接取得影片 URL
- 有密碼保護的頁面必須走 Phase 2（Playwright）
