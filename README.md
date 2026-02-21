# lurl.cc / myppt.cc 影片下載工具

從 lurl.cc / myppt.cc 頁面自動下載影片的命令列工具。

## 功能

- 自動處理年齡驗證對話框
- 自動從上傳日期提取密碼（MMDD 格式），也支援手動指定密碼
- 密碼錯誤時提示手動輸入
- 漸進式下載策略：先嘗試簡單方式，失敗再升級
- 下載進度條顯示

## 安裝

```bash
pip install -r requirements.txt
playwright install chromium
```

### 依賴

- `requests` — HTTP 請求
- `beautifulsoup4` — HTML 解析
- `playwright` — 瀏覽器自動化（處理需要 JS 執行的頁面）

## 使用方式

```bash
# 基本用法（自動嘗試日期密碼）
python download.py https://lurl.cc/XXXXX
python download.py https://myppt.cc/XXXXX

# 手動指定密碼
python download.py https://lurl.cc/XXXXX -p 7777
python download.py https://myppt.cc/XXXXX -p 1234
```

影片會下載至 `downloads/` 目錄。

## UserScript（瀏覽器腳本）

除了命令列工具，也提供 UserScript 瀏覽器腳本。安裝後開啟 lurl.cc 或 myppt.cc 頁面會自動運作，不需要使用終端機。

功能：
- 自動年齡驗證
- 自動嘗試日期密碼
- 頁面右下角一鍵下載按鈕

### 安裝

1. 安裝 [Tampermonkey](https://www.tampermonkey.net/) 瀏覽器擴充功能（支援 Chrome / Firefox / Edge）
2. 點擊 [`lurl-downloader.user.js`](https://raw.githubusercontent.com/cloudlin/lurl-downloader/main/lurl-downloader.user.js) 安裝腳本，或手動複製檔案內容貼到 Tampermonkey 的新腳本中

### 使用流程

1. 安裝完成後，開啟任何 `lurl.cc/*` 或 `myppt.cc/*` 頁面，腳本會自動執行
2. 年齡驗證 — 自動點擊確認按鈕（不需操作）
3. 密碼保護 — 自動從頁面提取日期並填入密碼（不需操作）
4. 影片載入後，右下角出現藍色「下載影片」按鈕
5. 點擊按鈕即可下載影片

### 注意事項

- 密碼不一定是日期，自動密碼失敗時需手動輸入
- 下載功能依賴 Tampermonkey 的 `GM_download` API 帶入 Referer，若 `GM_download` 失敗會自動開新分頁讓你右鍵另存

## 架構

```
lurl-downloader/
├── download.py                # CLI 主程式
├── lurl-downloader.user.js    # UserScript 瀏覽器腳本
├── requirements.txt           # Python 依賴
├── downloads/                 # 影片存放目錄
├── CLAUDE.md                  # AI 開發筆記
└── README.md
```

### 下載策略（漸進式）

程式依序嘗試以下方式，成功就停止：

1. **Phase 1 — HTTP 請求**：用 `requests` 直接取得頁面 HTML，解析 `<video><source>` 標籤。最快但會被有密碼保護或需要 JS 的頁面擋住。

2. **Phase 2 — Playwright 瀏覽器**：啟動 Chromium，帶反偵測設定繞過 Cloudflare。自動處理年齡驗證和密碼，等待影片元素載入後提取 URL。

3. **Phase 3 — Playwright 瀏覽器（較長等待）**：同 Phase 2 但等待時間更長，作為最後手段。

### 影片 URL 提取

依序嘗試以下選擇器：

1. `.vjs-tech source` — Video.js 播放器
2. `#video source`
3. `video source`
4. `video[src]`
5. JavaScript 評估取得 `video.src`

### 密碼處理流程

1. 若有 `-p` 參數 → 使用指定密碼
2. 從 `span.login_span` 提取日期 → 轉 MMDD 格式
3. 以上都失敗 → 提示使用者手動輸入
