---
description: Daily SIPs scan (NTRT/MTRT gappers → MAGNA53 → claude_picks → GitHub Pages). Cloud-session entry point; local machine falls through to the user-level /SIPs.
argument-hint: "[TICKER1,TICKER2 ...]"
---

# /SIPs — 入口(cloud / local 自動分流)

先判斷執行環境:`echo $CLAUDE_CODE_REMOTE`

- **不是 `true`(本機 Windows)** → 本檔不適用。讀 `~/.claude/commands/SIPs.md`(使用者層級注入檔)並完全照做,忽略下面所有 cloud 規則。
- **是 `true`(Claude Code cloud session)** → 照下面做。

## Cloud 執行方式

1. **第一步先跑:** `bash cloud/setup.sh`
   (建立 `py` → `python3` 的 shim 並固定 `TZ=Asia/Taipei`、確認 Playwright、裝與 `model_spike.pkl` 相符的 scikit-learn、把 repo rebase 到最新 `origin/main`、印出台北/紐約時間。任何一行印 `WARN` 就先處理再開跑。)
2. **然後讀正本 `skills/SIPs/SKILL.md`,從頭到尾照做**,參數 = `$ARGUMENTS`。正本的所有判斷規則、路由、輸出格式一律照舊;只有下面「Cloud 覆寫」列出的項目改掉。

## Cloud 覆寫(與正本衝突時以這裡為準)

**交付面 = GitHub Pages,不是本機 dashboard。** 使用者在 cloud 只要 GitHub 上的 dashboard 更新:<https://chi2tseng.github.io/stocks-in-play/>

| 正本寫的 | Cloud 改成 |
|---|---|
| § 0.6 T+0a 檢查 `127.0.0.1:5510` / `preview_start` / sidecar / 殺殭屍 PID | **整段跳過。** 不起 server,不檢查 5510,直接進 Phase 1 |
| § 8.x「Then open http://127.0.0.1:5510/」、收尾回報附本機網址 | 改附 <https://chi2tseng.github.io/stocks-in-play/>;push 後約 30 秒部署 |
| `cd C:\Users\chi2t` / `cd D:\SIPs` / 任何 Windows 路徑 | 一律在 repo 根目錄(本 session 的工作目錄)執行;`D:\SIPs\X` = `./X` |
| PowerShell 區塊、`Get-CimInstance`、`.cmd`、`.vbs` | 改用 bash 等價寫法;本機專屬的維運步驟直接跳過 |
| `py <script>` | 照打 `py`(setup.sh 建的 shim,= `python3` + TZ 台北) |
| `npx.cmd playwright install chromium` / `npm install` | **禁止。** 容器已預裝 Playwright + Chromium;腳本會自動 fallback 到預裝的 `playwright` |
| § 2.3 `node x-scrape.js`(需要本機登入過的 X profile) | **跳過。** X/Twitter 改用 WebSearch(`"$SYM" <DATE> site:x.com` 或 `"$SYM" stock <DATE>`) |
| § 0.5「先確認 session 是 Opus 5 max(`/model` 切換)」 | 不擋。用本 session 現有模型照跑;sonnet 蒐集 / 主模型判斷的路由不變 |
| Phase 12 / 其他 CLI(codex、agy、grok)的路徑 | 不適用(本來就已取消) |

**Cloud 專屬規則:**

- **容器是暫時的,沒 push = 白做。** 照正本「先完成先上線」:每次 `build_dashboard.py` 後就 commit + push 一次,收尾再補。
- **push 前一律先同步**(本機可能同時在跑/推):
  ```bash
  git fetch origin main && git rebase --autostash origin/main
  ```
  rebase 若在資料檔衝突:以**本次 run 產出的檔案**為準(`git checkout --theirs` 對 rebase 而言是本地 commit),然後重跑 `py build_dashboard.py` 再 commit。push 失敗(網路)指數退避重試最多 4 次(2s/4s/8s/16s)。
- **直接推 `main`**(GitHub Pages 由 `main` 的 `dashboard/**` 觸發部署)。commit 只加正本 § 8.7 列出的資料/狀態檔,**不要 commit** 掃描暫存檔(`candidates.csv`、`shorts.json`、`tv-summary.*`、`*-earnings-fq.md`、`barchart-*.json` 已在 `.gitignore`)。
- **不要改程式碼或 skill。** cloud run 只產資料;若發現腳本壞掉,修最小必要範圍並在 brief 最後明列改了什麼。
- **時間:** 掃描邏輯依美東時間(Barchart session-date 規則內建 ET 換算);Python 腳本的「今天」= 台北日期(與本機一致)。setup.sh 已印出兩地時間,開跑前看一眼。
