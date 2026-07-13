# AGENTS.md — SIPs 多 agent 路由(所有 CLI 通用)

本 repo 是每日「Stocks In Play」掃描系統。四個 AI 各有固定角色;
**使用者打 `/SIPs`(或說「跑 SIPs」)時,照你的身分做你自己的事,不要越界:**

## 你是誰 → 該做什麼

- **Claude(Claude Code)** → 跑完整掃描管線 + 自己的 `claude_picks.json`(skill 在 `~/.claude/commands/SIPs.md`,
  執行版=注入檔,措辭精簡;正本=`D:\SIPs\skills\SIPs\SKILL.md`,兩者同步維護,衝突以正本為準)。
  **到 build+push 就結束 —— 不再自動發射其他三家(Phase 12 已於 2026-07-13 取消,各 AI 各自獨立跑)。**
  只有 Claude 跑全套機械掃描;其他三家各自在自己 CLI 打 /SIPs 獨立工作。

- **Codex / ChatGPT(codex CLI)** → 你是評審之一。
  **讀 `C:\Users\chi2t\.codex\skills\SIPs-codex-picks\SKILL.md`,從頭到尾照做。**
  = (包新→讀;**包舊或不在→重掃 barchart 抓新增**,你有終端機)→ 自己上網查證 → 寫 `codex_picks.json` → build+push。

- **Gemini(agy / Antigravity CLI)** → 你是評審之一。
  **讀 `C:\Users\chi2t\.gemini\skills\SIPs-gemini-picks\SKILL.md`,從頭到尾照做。**
  = (包新→讀;**包舊或不在→重掃**:互動模式跑 barchart、headless 讀現有包或 web-discovery)→ 自己上網查證 → 寫 `gemini_picks.json`。
  headless(accept-edits)時寫完即止 — **發射鏈會自動 build+push**;
  互動模式則照 skill § 6 自己 build+push(終端指令請使用者核准)。

- **Grok(grok CLI)** → 你是評審之一。
  **讀 `C:\Users\chi2t\.grok\skills\SIPs-grok-picks\SKILL.md`,從頭到尾照做。**
  = (包新→讀;**包舊或不在→重掃 barchart 抓新增**,你有終端機)→ X 即時搜尋+web 自查 → 寫 `grok_picks.json` → build+push。

## 共同鐵則(所有非 Claude agent)

1. 只准寫**自己的** picks 檔;`news_detail.json`、`catalysts_today.json`、`day_resets.json`、
   `dashboard/studies/` 等共享檔一律唯讀。
2. 研究自己做(rationale 要基於自家查到的東西),不看、不抄其他家的 picks。
3. 掃描包 `dashboard/data/<今日YYYY-MM-DD>.json` **舊了(scanTimestamp 距今 > ~10 分)或不存在** → **不要停、也別只吃舊包,重掃 barchart 抓新增名字**:
   有終端機(Codex/Grok/互動 Gemini)跑 `node barchart-scrape.js` + `py build_dashboard.py`(build_dashboard 對掃描日做 **union** — 新 gapper 加入、既有已分析/被 pick 的名字保留不掉);
   Gemini 在 headless/accept-edits 無終端機時:包在就直接用、包缺才 web-discovery 自建薄包。細節見各自 picks skill § 1。
   包**很新**(≤ ~10 分,通常 Claude 剛在 Phase 12 建好)就免重掃直接讀 —— 避免與 Claude 剛跑的掃描互撞。
4. **重掃只做便宜的 barchart gap 掃描**抓新名字;**昂貴的完整管線**(catalyst 深掃、全套 TV/Finviz/candles、MAGNA53 精排)仍是 Claude 的活,不要重跑。新聞查證與判斷永遠各評審自己做。
