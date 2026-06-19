# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repository Is

This is a game design document repository for **大地遊戲** (Territory Game), the main activity of NTU CSIE Camp. All files are Markdown documents written in Traditional Chinese. There is no code, build system, or test suite.

## Overall Game Structure

The game runs 13:00–16:00 and has four layers:

1. **大地遊戲 (Territory Game, 13:00–15:10)** — Teams (小隊, labeled A/B/C…) split into two subgroups (小組, e.g. A1/A2) and explore classroom-based stages to earn currency (貨幣) and flags (旗子). Flags are placed on 4×4 grids in classroom "territories" (領地) to compete for control. Every ~30 minutes a **世界史更新** (World History Update) scores each territory and penalizes teams that are holding enemy flags.

2. **間諜メカニクス (Spy mechanic)** — A minority of each team are secret spies (Ab) loyal to a rival team. Spies coordinate through an anonymous group chat. The tension between normal play and spy sabotage is a core design pillar.

3. **中央市集 (Central Market, 103)** — Teams spend currency to draw or buy item cards (道具卡) in rarity tiers N/R/SR/SSR that give strategic advantages (extra time, flag manipulation, scoring multipliers, information, etc.).

4. **最終大戰 / WWW (Final Battle, 15:10–15:45)** — A board-game-style military phase in room 103. Teams convert accumulated resources into "military power" (兵力), then spend 3 rounds of 7 minutes each issuing `moving()`, `attack()`, `union()`, and `union_attack()` operations to capture territories and accumulate "national power" (國力). The team with the most 國力 at the end wins.

## Document Map

| File | Content |
|------|---------|
| `一驗企劃書-完成版.md` | Core rulebook: all mechanics, scoring formula, feedback from 1st review |
| `時程&特殊事件-時間有問題還在調整.md` | Master timeline and special events (U1–U4 world updates) |
| `道具卡.md` | Item card catalog — two versions: current `main` and the original `Original` |
| `最終大戰.md` | Full WWW (Final Battle) rules: operations API, territory resolution, resource points |
| `大地遊戲關主包.md` | 4 stages by Wiwi: 九宮戰術陣, 禁語回聲林, 龍王試煉場, 荒原躲避戰 |
| `大地遊戲關主包_完整版.md` | 4 stages by 曾: 肢體石陣, 節拍回聲圈, 謊言骰杯, 四色旗令台 |
| `大地遊戲關卡.md` | Stages by 安 (partially complete) |
| `二驗-未完成.md` | Links to all Google Docs + per-item notes for the 2nd review handoff |

## Design Status

The project is iterating through formal review stages (一驗 → 二驗 → 三驗). As of the current state:
- Core mechanics and 世界史更新 cycle are defined but some timing is still being adjusted
- All 8+ stages have basic rules; prop lists and physical production are pending
- 最終大戰 rules are complete; the spy-resolution / final judgment ceremony is still being designed
- 道具卡 has two versions in the same file — `main` is the current design, `Original` is kept for reference

## Key Design Constraints to Keep in Mind

- Each territory has its own 4×4 grid and a **unique occupation rule** (longest line, largest area, etc.) — changes to one territory's rule affect game balance differently than others.
- The spy mechanic is controversial (1st review feedback flagged it as potentially too complex); any changes should explicitly address whether the mechanic is being simplified or justified.
- Currency values and reward tiers across all stages should be balanced against each other — a change to one stage's payout ripples through market pricing.
- Physical production constraints matter: flags need laminating, currency does not; classroom layout limits stage placement.
