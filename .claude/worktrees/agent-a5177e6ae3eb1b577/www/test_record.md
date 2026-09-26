# 最終大戰 WWW — 測試記錄

**測試日期：** 2026-06-20  
**測試結果：** 90 / 90 通過，0 失敗  

---

## 測試環境

- Python 3.13，Flask 3.1.3，venv 位於 `www/venv/`
- 隊伍代號：數字 1–10
- 島嶼代號：英文縮寫（HK, ELF, DV, ORC, GNT, DWF, FOX, MK, PUD, KPA, GOB, DOLL, NEU, FOG, GOLD, VORT）

---

## 指令格式

```
moving(S, E, n)             移動兵力（不進攻）
attack(S, E, n)             進攻
union(S, P, E, n)           請求/接受聯軍進駐
union_attack(S, P, E, n)    聯盟進攻（P 可為 [2,3] 或單一隊伍）
set(zone, T:n, ...)         管理員設定領地（ADMIN 隊專用）
set(zone)                   管理員清除領地
```

S / E 使用英文代號（如 `HK`）或完整中文名（如 `人類王國`）皆可，大小寫不敏感。

---

## 案例一覽

| # | 案例名稱 | 測試內容 | 結果 |
|---|----------|----------|------|
| 1 | Simple moving | moving(HK, NEU, 200)：兵力移出 HK，移入 NEU，觸發 ×1.5 | ✓ |
| 2 | Attack wins | attack(HK, ELF, 400) vs 300 防守：進攻方勝，獲 20% 獎勵兵力 | ✓ |
| 3 | Attack loses | attack(HK, ELF, 150) vs 600 防守：防守方勝 | ✓ |
| 4 | Attack — insufficient troops | 出兵超過現有兵力：rejected（兵力不足） | ✓ |
| 5 | Attack own territory | 進攻己方領地：rejected | ✓ |
| 6 | Attack neutral island | 進攻中立小島：rejected | ✓ |
| 7 | 3-op limit | 4 條指令只有前 3 條有效；第 4 條標記「超過上限」 | ✓ |
| 8 | Conflict penalty | 從 HK 出兵 200+200 超過 300：兩條指令全部失效，兵力強制移入 NEU（×1.5＝450） | ✓ |
| 9 | Union confirmed | 雙方提交相同 (S=HK, E=ELF, n=200)、P 互指：confirmed；requesting 方兵力移動，accepting 方無需出兵 | ✓ |
| 10 | Union pending | 只有一方提交 union：pending 狀態 | ✓ |
| 11 | union_attack coalition 2v1 | 隊 1+2 各出 300 聯攻 DV（守方 200）：防守方清零，攻方各 +20 獎勵 | ✓ |
| 12 | union_attack solo | 聯盟夥伴未提交對應指令：effective_allies = [] | ✓ |
| 13 | Admin set | set(HK, 2:999, 3:500)：設定多隊兵力，清除原有兵力 | ✓ |
| 14 | Admin set clear | set(HK)：清空整個領地 | ✓ |
| 15 | Neutral island ×1.5 | NEU 兵力每回合自動 ×1.5（200→300, 100→150） | ✓ |
| 16 | Zero-troop relief | 沒有任何兵力的隊伍：自動獲得 1000 兵力到 NEU | ✓ |
| 17 | FOG (R1) round 2 | 第 2 回合起，FOG 按比例分配 1000 兵力（600:400 → +600:+400） | ✓ |
| 18 | FOG not active round 1 | 第 1 回合 FOG 不觸發 | ✓ |
| 19 | GOLD (R2) national power | GOLD 按比例分配 1000 國力（60%→600 NP, 40%→400 NP） | ✓ |
| 20 | VORT even teams (2) | 漩渦 2 隊：分配 2000 兵力（比例 1200:800） | ✓ |
| 21 | VORT odd teams (3) | 漩渦 3 隊：分配 2000 國力（總計 ~2000） | ✓ |
| 22 | VORT 4 teams | 漩渦恰好 4 隊：不產出，log 記錄「不產出」 | ✓ |
| 23 | Game end | 最後一回合執行後 phase→done，回合計數 +1 | ✓ |
| 24 | Tie — defender wins | 進攻 300 vs 防守 300（平手）：防守方勝 | ✓ |
| 25 | Multi-zone attacks | 從同一領地攻兩個目標（300+200 ≤ 600）：兩條指令都有效 | ✓ |
| 26 | Overdraw two attacks | 從同一領地攻兩個目標（300+200 > 400）：兩條指令都失效（衝突）| ✓ |
| 27 | NP multi-occupant | HK 隊1:600, 隊2:400；owner 得 720 NP，守備 得 180 NP，總 900 | ✓ |
| 28 | Case-insensitive codes | hk / ELF / vort / doll 不分大小寫全部正確解析 | ✓ |
| 29 | All 16 island codes | 全部 16 個英文代號正確對應中文名稱 | ✓ |
| 30 | Team 10 (two-digit) | 隊 10 的指令正確解析、驗證、執行 | ✓ |
| 31 | Union self-alliance | union(HK, 1, ELF, 100) 隊 1 與自己結盟：rejected | ✓ |
| 32 | Unknown zone | attack(INVALID, ELF, 100)：parse 失敗 | ✓ |
| 33 | Moving uncontrolled | 從他隊領地移動：rejected | ✓ |
| 34 | Moving to opponent | moving(HK, ELF, 100)（ELF 是他隊領地）：rejected | ✓ |
| 35 | to_dict zone codes | 每個 zone 的 to_dict 輸出包含 code 欄位 | ✓ |
| 36 | Commands reset | 執行後各隊 round_commands 清空 | ✓ |
| 37 | NP accumulation | 國力跨回合累積（900→1800） | ✓ |
| 38 | Multi-line commands | 指令跨行（括號開啟）：正確合併解析 | ✓ |
| 39 | Empty lines ignored | 文字中有空白行：正確忽略 | ✓ |
| 40 | Undo snapshot | state.copy() 保留快照，執行後原快照不受影響 | ✓ |

---

## 重要規則確認

### union 指令規則
- **雙方必須提交相同的 (S, E, n)**，P 值互指對方隊伍
- **requesting 方**（E 是對方領地）：實際移動 n 兵力從 S 到 E
- **accepting 方**（E 是己方領地）：不移動兵力，只接受駐守
- 只有一方提交時狀態為 **pending**（本回合無效）

### union_attack 指令規則
- 所有參與方必須互相列出對方（完整互指才成立聯盟）
- 不完整互指：從有效子集中計算最大覆蓋聯盟
- 沒有配對到的隊伍視為獨立進攻（effective_allies = []）

### 衝突懲罰
- 同一隊從同一出發領地要求的總兵力超過現有兵力
- 涉及該出發領地的所有指令全部失效
- 該領地全部兵力強制移入中立小島

### 漩渦特殊規則
- 恰好 4 隊：無產出
- 偶數隊（≠4）：分配 2000 兵力
- 奇數隊：分配 2000 國力
- 第 1 回合不觸發（第 2 回合起）

---

## 已知設計決策

1. 領地國力 X 值依難度分級設定（★★=600, ★★★=700, ★★★★=900, ★★★★★=1000）
2. 戰鬥平手：防守方勝（確保穩定性）；若防守方也平手則按聯盟 ID 字典序決定
3. 戰鬥獎勵：獲勝方獲得失敗方總兵力的 20%，按比例分配給聯盟各員
4. 中立小島：每回合 ×1.5，且不可被進攻
5. 零兵力救濟：每回合結算後，沒有任何兵力的隊伍獲得 1000 兵力（加入中立小島）
