# AGENTS.md — SIPs 多 agent 路由(所有 CLI 通用)

本 repo 是每日「Stocks In Play」掃描系統。四個 AI 各有固定角色;
**使用者打 `/SIPs`(或說「跑 SIPs」)時,照你的身分做你自己的事,不要越界:**

## 你是誰 → 該做什麼

- **Claude(Claude Code)** → 總指揮:跑完整掃描管線(skill 在 `~/.claude/commands/SIPs.md`,
  執行版=注入檔,措辭精簡;正本=`D:\SIPs\skills\SIPs\SKILL.md`,兩者同步維護,衝突以正本為準),
  結尾自動背景發射下面三家。只有 Claude 跑全套。

- **Codex / ChatGPT(codex CLI)** → 你是評審之一。
  **讀 `C:\Users\chi2t\.codex\skills\SIPs-codex-picks\SKILL.md`,從頭到尾照做。**
  = (掃描包在→讀;**包不在→自己掃**,你有終端機)→ 自己上網查證 → 寫 `codex_picks.json` → build+push。

- **Gemini(agy / Antigravity CLI)** → 你是評審之一。
  **讀 `C:\Users\chi2t\.gemini\skills\SIPs-gemini-picks\SKILL.md`,從頭到尾照做。**
  = (掃描包在→讀;**包不在→自己掃**:互動模式跑 scraper、headless 走 web-discovery)→ 自己上網查證 → 寫 `gemini_picks.json`。
  headless(accept-edits)時寫完即止 — **發射鏈會自動 build+push**;
  互動模式則照 skill § 6 自己 build+push(終端指令請使用者核准)。

- **Grok(grok CLI)** → 你是評審之一。
  **讀 `C:\Users\chi2t\.grok\skills\SIPs-grok-picks\SKILL.md`,從頭到尾照做。**
  = (掃描包在→讀;**包不在→自己掃**,你有終端機)→ X 即時搜尋+web 自查 → 寫 `grok_picks.json` → build+push。

## 共同鐵則(所有非 Claude agent)

1. 只准寫**自己的** picks 檔;`news_detail.json`、`catalysts_today.json`、`day_resets.json`、
   `dashboard/studies/` 等共享檔一律唯讀。
2. 研究自己做(rationale 要基於自家查到的東西),不看、不抄其他家的 picks。
3. 當日掃描包 `dashboard/data/<今日YYYY-MM-DD>.json` 不存在 → **不要停,自己掃出候選宇宙**(舊版是 abort,已改):
   有終端機(Codex/Grok/互動 Gemini)就跑 `node barchart-scrape.js` + `py build_dashboard.py`(finviz-shorts 選用);
   Gemini 在 headless/accept-edits 無終端機時改 web-discovery 自建薄包。細節見各自 picks skill 的 § 1。掃完照常各自研究+picks。
4. **包已存在時不要重跑**完整掃描 — catalyst 深掃 + 全套 TV/Finviz/candles + MAGNA53 精排是 Claude 的活。
   自己掃(規則 3)只在**包缺**時做,且只跑到「有候選宇宙可挑」的最小程度;新聞查證與判斷永遠各評審自己做。
