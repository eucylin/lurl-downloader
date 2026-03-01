#!/usr/bin/env python3
"""lurl.cc / myppt.cc 影片下載工具"""

import argparse
import os
import re
import sys
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

SUPPORTED_DOMAINS = ["lurl.cc", "myppt.cc"]

PASSWORD_SELECTORS = ["input#password", "input#pasahaicsword"]

VIDEO_SELECTORS = [
    ".vjs-tech source",
    "#video source",
    "#my_video_html5_api source",
    "video source",
    "video[src]",
    "#my_video_html5_api[src]",
]


def extract_video_url_from_html(html: str) -> str | None:
    """從 HTML 中解析影片 URL"""
    soup = BeautifulSoup(html, "html.parser")
    for selector in VIDEO_SELECTORS:
        elements = soup.select(selector)
        for el in elements:
            src = el.get("src")
            if src and src.startswith("http"):
                return src
    return None


def phase1_requests(url: str) -> str | None:
    """Phase 1: 用 requests 直接嘗試取得影片 URL"""
    print("[Phase 1] 嘗試用 HTTP 請求取得影片 URL...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}，跳過 Phase 1")
            return None
        video_url = extract_video_url_from_html(resp.text)
        if video_url:
            print(f"  找到影片 URL: {video_url}")
            return video_url
        print("  未在 HTML 中找到影片 URL，可能需要 JS 執行")
    except requests.RequestException as e:
        print(f"  請求失敗: {e}")
    return None


def extract_password_from_page(page) -> str | None:
    """從頁面的日期資訊提取密碼 (MMDD)"""
    try:
        span = page.query_selector("div.col-sm-12 span.login_span")
        if not span:
            return None
        text = span.inner_text()
        match = re.search(r"\d{4}-(\d{2})-(\d{2})", text)
        if match:
            password = match.group(1) + match.group(2)
            print(f"  提取密碼: {password}")
            return password
    except Exception:
        pass
    return None


def handle_age_verification(page) -> None:
    """處理年齡驗證對話框"""
    try:
        buttons = page.query_selector_all("button")
        if len(buttons) == 13:
            print("  偵測到年齡驗證，點擊確認...")
            buttons[1].click()
            page.wait_for_timeout(2000)
            return

        # 嘗試尋找常見的年齡確認按鈕
        for selector in [
            "button:has-text('我已年滿')",
            "button:has-text('進入')",
            "button:has-text('確認')",
            "button:has-text('Yes')",
            "button:has-text('Enter')",
        ]:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                print(f"  點擊年齡驗證按鈕: {selector}")
                btn.click()
                page.wait_for_timeout(2000)
                return
    except Exception:
        pass


def find_password_input(page):
    """遍歷 PASSWORD_SELECTORS 找到可見的密碼欄位"""
    for selector in PASSWORD_SELECTORS:
        el = page.query_selector(selector)
        if el and el.is_visible():
            return el
    return None


def submit_password(page, password: str) -> bool:
    """填入密碼並提交，回傳是否成功（密碼框消失表示成功）"""
    password_input = find_password_input(page)
    if not password_input:
        return True  # 沒有密碼框，視為成功

    print(f"  填入密碼: {password}")
    password_input.fill(password)

    # 尋找提交按鈕
    submitted = False
    for selector in [
        "form button",
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('立即解密')",
        "button:has-text('送出')",
        "button:has-text('Submit')",
        "button:has-text('確認')",
    ]:
        btn = page.query_selector(selector)
        if btn and btn.is_visible():
            btn.click()
            submitted = True
            break

    if not submitted:
        password_input.press("Enter")

    page.wait_for_timeout(5000)

    # 檢查密碼框是否還在（還在表示密碼錯誤）
    return not find_password_input(page)


def handle_password(page, cli_password: str | None = None) -> None:
    """處理密碼保護頁面"""
    try:
        password_input = find_password_input(page)
        if not password_input:
            return

        # 優先使用命令列指定的密碼
        if cli_password:
            if submit_password(page, cli_password):
                print("  命令列密碼驗證成功")
                return
            print("  命令列指定的密碼錯誤")

        # 嘗試日期密碼
        date_password = extract_password_from_page(page)
        if date_password and date_password != cli_password:
            if submit_password(page, date_password):
                print("  日期密碼驗證成功")
                return
            print("  日期密碼錯誤，需要手動輸入")

        # 自動密碼都失敗，提示使用者手動輸入
        while True:
            user_pw = input("  請輸入密碼（輸入 q 放棄）: ").strip()
            if user_pw.lower() == "q":
                print("  放棄密碼輸入")
                return
            if submit_password(page, user_pw):
                print("  密碼驗證成功")
                return
            print("  密碼錯誤，請重試")

    except Exception as e:
        print(f"  密碼處理失敗: {e}")


def phase2_playwright(url: str, password: str | None = None) -> str | None:
    """Phase 2: 用 Playwright 瀏覽器取得影片 URL"""
    print("[Phase 2] 使用 Playwright 瀏覽器...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright 未安裝，請執行: pip install playwright && playwright install chromium")
        return None

    video_url = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="zh-TW",
        )
        page = context.new_page()
        page.add_init_script(
            'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        )

        try:
            print(f"  導航至 {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            # 處理年齡驗證
            handle_age_verification(page)

            # 處理密碼
            handle_password(page, password)

            # 等待影片元素載入
            print("  等待影片元素載入...")
            for selector in VIDEO_SELECTORS:
                try:
                    page.wait_for_selector(selector, timeout=10000)
                    element = page.query_selector(selector)
                    if element:
                        src = element.get_attribute("src")
                        if src and src.startswith("http"):
                            video_url = src
                            print(f"  找到影片 URL: {video_url}")
                            break
                except Exception:
                    continue

            if not video_url:
                # 嘗試從 video 標籤的 src 屬性取得
                video_el = page.query_selector("video")
                if video_el:
                    src = video_el.get_attribute("src")
                    if src and src.startswith("http"):
                        video_url = src
                        print(f"  從 video 標籤找到 URL: {video_url}")

            if not video_url:
                # 嘗試從頁面 JS 變數中取得
                try:
                    src = page.evaluate("""
                        () => {
                            const video = document.querySelector('video');
                            if (video && video.src) return video.src;
                            const source = document.querySelector('video source');
                            if (source && source.src) return source.src;
                            const myVideo = document.querySelector('#my_video_html5_api');
                            if (myVideo && myVideo.src) return myVideo.src;
                            const myVideoSource = document.querySelector('#my_video_html5_api source');
                            if (myVideoSource && myVideoSource.src) return myVideoSource.src;
                            // Video.js player
                            const player = document.querySelector('.video-js');
                            if (player && player.player) {
                                const tech = player.player.tech({ IWillNotUseThisInPlugins: true });
                                if (tech && tech.src_) return tech.src_;
                            }
                            return null;
                        }
                    """)
                    if src:
                        video_url = src
                        print(f"  從 JS 取得影片 URL: {video_url}")
                except Exception:
                    pass

        except Exception as e:
            print(f"  Playwright 錯誤: {e}")
        finally:
            browser.close()

    return video_url


def phase3_playwright_headed(url: str, password: str | None = None) -> str | None:
    """Phase 3: 用 Playwright 有頭瀏覽器（最後手段）"""
    print("[Phase 3] 使用 Playwright 有頭瀏覽器...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright 未安裝")
        return None

    video_url = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="zh-TW",
        )
        page = context.new_page()
        page.add_init_script(
            'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        )

        try:
            print(f"  導航至 {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(8000)

            handle_age_verification(page)
            handle_password(page, password)

            # 較長的等待時間
            print("  等待影片載入（最多 30 秒）...")
            for selector in VIDEO_SELECTORS:
                try:
                    page.wait_for_selector(selector, timeout=15000)
                    element = page.query_selector(selector)
                    if element:
                        src = element.get_attribute("src")
                        if src and src.startswith("http"):
                            video_url = src
                            print(f"  找到影片 URL: {video_url}")
                            break
                except Exception:
                    continue

            if not video_url:
                try:
                    src = page.evaluate("""
                        () => {
                            const video = document.querySelector('video');
                            if (video && video.src) return video.src;
                            const source = document.querySelector('video source');
                            if (source && source.src) return source.src;
                            const myVideo = document.querySelector('#my_video_html5_api');
                            if (myVideo && myVideo.src) return myVideo.src;
                            const myVideoSource = document.querySelector('#my_video_html5_api source');
                            if (myVideoSource && myVideoSource.src) return myVideoSource.src;
                            return null;
                        }
                    """)
                    if src:
                        video_url = src
                        print(f"  從 JS 取得影片 URL: {video_url}")
                except Exception:
                    pass

        except Exception as e:
            print(f"  Playwright 錯誤: {e}")
        finally:
            browser.close()

    return video_url


def download_video(video_url: str, page_url: str) -> str:
    """下載影片檔案"""
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    # 從 URL 取得檔名
    parsed = urlparse(video_url)
    filename = os.path.basename(parsed.path)
    if not filename or "." not in filename:
        filename = "video.mp4"

    filepath = os.path.join(DOWNLOADS_DIR, filename)

    # 避免覆蓋
    base, ext = os.path.splitext(filepath)
    counter = 1
    while os.path.exists(filepath):
        filepath = f"{base}_{counter}{ext}"
        counter += 1

    print(f"\n下載影片: {video_url}")
    print(f"儲存至: {filepath}")

    download_headers = {**HEADERS, "Referer": page_url}
    resp = requests.get(video_url, headers=download_headers, stream=True, timeout=60)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                bar = "=" * int(pct / 2) + ">" + " " * (50 - int(pct / 2))
                print(f"\r  [{bar}] {pct:.1f}% ({downloaded}/{total})", end="", flush=True)

    print(f"\n\n下載完成: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="lurl.cc / myppt.cc 影片下載工具")
    parser.add_argument("url", help="lurl.cc / myppt.cc 影片頁面 URL")
    parser.add_argument("-p", "--password", help="手動指定密碼（預設會嘗試從日期自動提取）")
    args = parser.parse_args()

    url = args.url
    password = args.password
    if not any(domain in url for domain in SUPPORTED_DOMAINS):
        print("警告: 這不是 lurl.cc / myppt.cc 的網址，但仍嘗試處理")

    # Phase 1: 直接 HTTP 請求
    video_url = phase1_requests(url)

    # Phase 2: Playwright headless
    if not video_url:
        video_url = phase2_playwright(url, password)

    # Phase 3: Playwright headed
    if not video_url:
        video_url = phase3_playwright_headed(url, password)

    if not video_url:
        print("\n所有方法都無法取得影片 URL，下載失敗")
        sys.exit(1)

    # 下載影片
    try:
        download_video(video_url, url)
    except Exception as e:
        print(f"\n下載失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
