// ==UserScript==
// @name         lurl.cc 影片下載器
// @name:zh-TW   lurl.cc 影片下載器
// @namespace    https://github.com/cloudlin/lurl-downloader
// @version      1.0.0
// @description  自動年齡驗證、自動密碼填入、一鍵下載 lurl.cc 影片
// @description:zh-TW  自動年齡驗證、自動密碼填入、一鍵下載 lurl.cc 影片
// @author       cloudlin
// @match        *://lurl.cc/*
// @grant        GM_download
// @grant        GM_addStyle
// @license      MIT
// @downloadURL  https://raw.githubusercontent.com/cloudlin/lurl-downloader/main/lurl-downloader.user.js
// @updateURL    https://raw.githubusercontent.com/cloudlin/lurl-downloader/main/lurl-downloader.user.js
// ==/UserScript==

(function () {
  "use strict";

  const VIDEO_SELECTORS = [
    ".vjs-tech source",
    "#video source",
    "video source",
    "video[src]",
  ];

  const AGE_BUTTON_TEXTS = ["我已年滿", "進入", "確認", "Yes", "Enter"];

  const SUBMIT_SELECTORS = [
    "form button",
    "button[type='submit']",
    "input[type='submit']",
  ];

  const LOG_PREFIX = "[lurl-downloader]";

  function log(...args) {
    console.log(LOG_PREFIX, ...args);
  }

  // --- 影片 URL 提取 ---

  function findVideoUrl() {
    for (const selector of VIDEO_SELECTORS) {
      const elements = document.querySelectorAll(selector);
      for (const el of elements) {
        const src = el.src || el.getAttribute("src");
        if (src && src.startsWith("http")) {
          return src;
        }
      }
    }
    // 嘗試 Video.js player API
    const player = document.querySelector(".video-js");
    if (player && player.player) {
      try {
        const tech = player.player.tech({ IWillNotUseThisInPlugins: true });
        if (tech && tech.src_) return tech.src_;
      } catch (_) {
        // ignore
      }
      try {
        const src = player.player.currentSrc();
        if (src) return src;
      } catch (_) {
        // ignore
      }
    }
    return null;
  }

  // --- 年齡驗證 ---

  function handleAgeVerification() {
    const buttons = document.querySelectorAll("button");
    for (const btn of buttons) {
      const text = btn.textContent || "";
      if (AGE_BUTTON_TEXTS.some((t) => text.includes(t)) && btn.offsetParent !== null) {
        log("點擊年齡驗證按鈕:", text.trim());
        btn.click();
        return true;
      }
    }
    return false;
  }

  // --- 密碼處理 ---

  function extractDatePassword() {
    const span = document.querySelector("div.col-sm-12 span.login_span");
    if (!span) return null;
    const match = span.textContent.match(/\d{4}-(\d{2})-(\d{2})/);
    if (match) {
      return match[1] + match[2];
    }
    return null;
  }

  function submitPassword(password) {
    const input = document.querySelector("input#password");
    if (!input || input.offsetParent === null) return false;

    log("填入密碼:", password);

    // 使用 native setter 確保 React/Vue 等框架能偵測到值變化
    const nativeSetter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value"
    ).set;
    nativeSetter.call(input, password);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));

    // 尋找提交按鈕
    for (const selector of SUBMIT_SELECTORS) {
      const btn = document.querySelector(selector);
      if (btn && btn.offsetParent !== null) {
        log("點擊提交按鈕:", selector);
        btn.click();
        return true;
      }
    }

    // fallback: 模擬 Enter 鍵
    input.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true })
    );
    input.dispatchEvent(
      new KeyboardEvent("keypress", { key: "Enter", code: "Enter", bubbles: true })
    );
    input.dispatchEvent(
      new KeyboardEvent("keyup", { key: "Enter", code: "Enter", bubbles: true })
    );
    return true;
  }

  function getPasswordStorageKey() {
    return "lurl-pw-tried:" + location.pathname;
  }

  function handlePassword() {
    const input = document.querySelector("input#password");
    if (!input || input.offsetParent === null) return false;

    const storageKey = getPasswordStorageKey();
    if (sessionStorage.getItem(storageKey)) {
      log("已嘗試過自動密碼，跳過（避免無限重試）");
      return false;
    }

    const password = extractDatePassword();
    if (password) {
      log("嘗試日期密碼:", password);
      sessionStorage.setItem(storageKey, password);
      submitPassword(password);
      return true;
    }
    return false;
  }

  // --- 下載按鈕 ---

  function getFilenameFromUrl(url) {
    try {
      const pathname = new URL(url).pathname;
      const filename = pathname.split("/").pop();
      if (filename && filename.includes(".")) return filename;
    } catch (_) {
      // ignore
    }
    return "video.mp4";
  }

  function injectDownloadButton(videoUrl) {
    if (document.getElementById("lurl-download-btn")) return;

    const filename = getFilenameFromUrl(videoUrl);

    const btn = document.createElement("button");
    btn.id = "lurl-download-btn";
    btn.textContent = "⬇ 下載影片";
    btn.title = filename;

    btn.addEventListener("click", () => {
      btn.textContent = "⏳ 下載中...";
      btn.disabled = true;

      log("開始下載:", videoUrl);
      log("檔名:", filename);
      log("Referer:", location.href);

      GM_download({
        url: videoUrl,
        name: filename,
        headers: { Referer: location.href },
        onload: () => {
          log("下載完成");
          btn.textContent = "✅ 下載完成";
          setTimeout(() => {
            btn.textContent = "⬇ 下載影片";
            btn.disabled = false;
          }, 3000);
        },
        onerror: (err) => {
          log("GM_download 失敗:", err);
          // fallback: 開新分頁讓使用者右鍵另存
          btn.textContent = "⬇ 下載影片";
          btn.disabled = false;
          window.open(videoUrl, "_blank");
        },
      });
    });

    document.body.appendChild(btn);
    log("下載按鈕已注入");
  }

  // --- 狀態通知 ---

  function showNotification(message, duration) {
    let container = document.getElementById("lurl-notification");
    if (!container) {
      container = document.createElement("div");
      container.id = "lurl-notification";
      document.body.appendChild(container);
    }
    container.textContent = message;
    container.style.display = "block";
    if (duration) {
      setTimeout(() => {
        container.style.display = "none";
      }, duration);
    }
  }

  // --- 樣式 ---

  GM_addStyle(`
    #lurl-download-btn {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 999999;
      padding: 12px 24px;
      background: #2563eb;
      color: #fff;
      border: none;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      transition: background 0.2s, transform 0.1s;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    #lurl-download-btn:hover:not(:disabled) {
      background: #1d4ed8;
      transform: translateY(-1px);
    }
    #lurl-download-btn:active:not(:disabled) {
      transform: translateY(0);
    }
    #lurl-download-btn:disabled {
      background: #6b7280;
      cursor: not-allowed;
    }
    #lurl-notification {
      position: fixed;
      top: 16px;
      right: 16px;
      z-index: 999999;
      padding: 10px 18px;
      background: rgba(0, 0, 0, 0.8);
      color: #fff;
      border-radius: 6px;
      font-size: 14px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      display: none;
    }
  `);

  // --- 主流程 ---

  function run() {
    log("腳本啟動");

    // 第一步：處理年齡驗證
    if (handleAgeVerification()) {
      showNotification("已自動通過年齡驗證", 2000);
    }

    // 第二步：處理密碼
    if (handlePassword()) {
      showNotification("已自動嘗試密碼", 2000);
    }

    // 第三步：監聽影片元素出現
    const videoUrl = findVideoUrl();
    if (videoUrl) {
      log("直接找到影片 URL:", videoUrl);
      injectDownloadButton(videoUrl);
      return;
    }

    // 使用 MutationObserver 等待影片元素動態載入
    log("等待影片元素載入...");
    const observer = new MutationObserver(() => {
      const url = findVideoUrl();
      if (url) {
        log("偵測到影片 URL:", url);
        observer.disconnect();
        injectDownloadButton(url);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["src"],
    });

    // 30 秒超時
    setTimeout(() => {
      observer.disconnect();
      if (!findVideoUrl()) {
        log("30 秒內未偵測到影片");
      }
    }, 30000);
  }

  // 頁面載入後延遲執行，確保 DOM 穩定
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => setTimeout(run, 1500));
  } else {
    setTimeout(run, 1500);
  }
})();
