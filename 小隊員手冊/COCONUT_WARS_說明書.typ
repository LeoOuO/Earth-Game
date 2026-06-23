// COCONUT WARS 小隊員說明書
// Typst 0.13.1 | Font: PingFang TC | A4 Printable

// ─── Global typography & page settings ──────────────────────────────────────
#set text(
  font: ("PingFang TC", "Heiti TC"),
  size: 8.5pt,
  lang: "zh",
  region: "TW",
  fallback: true,
)
#set page(
  paper: "a4",
  margin: (top: 1.4cm, bottom: 1.5cm, left: 1.5cm, right: 1.5cm),
  numbering: none,
)
#set par(leading: 0.45em, spacing: 0.6em)
#set list(indent: 0.8em)

// ─── Color tokens ────────────────────────────────────────────────────────────
#let accent     = rgb("#2E7D32")
#let accent-bg  = rgb("#E8F5E9")
#let accent-mid = rgb("#A5D6A7")
#let warn-bg    = rgb("#FFF8E1")
#let warn-brd   = rgb("#F9A825")
#let info-bg    = rgb("#E3F2FD")
#let info-brd   = rgb("#1565C0")
#let neutral-bg = rgb("#F5F5F5")
#let neutral-brd= rgb("#9E9E9E")
#let white      = rgb("#FFFFFF")
#let dark       = rgb("#1B1B1B")
#let mid-gray   = rgb("#616161")

// ─── Reusable components ─────────────────────────────────────────────────────

// Section heading (h2-style)
#let section(title) = {
  v(0.25em)
  block(
    width: 100%,
    inset: (x: 7pt, y: 3.5pt),
    fill: accent,
    radius: 4pt,
    text(fill: white, size: 11pt, weight: "bold", title)
  )
  v(0.15em)
}

// Sub-section heading (h3-style)
#let subsection(title) = {
  v(0.2em)
  block(
    width: 100%,
    inset: (x: 6pt, y: 2.5pt),
    fill: accent-bg,
    radius: 3pt,
    stroke: (left: 3pt + accent),
    text(fill: accent, size: 10pt, weight: "bold", title)
  )
  v(0.1em)
}

// Callout box (info/warn/neutral)
#let callout(body, kind: "info") = {
  let (bg, brd) = if kind == "warn" { (warn-bg, warn-brd) }
                  else if kind == "neutral" { (neutral-bg, neutral-brd) }
                  else { (info-bg, info-brd) }
  block(
    width: 100%,
    inset: (x: 6pt, y: 3pt),
    fill: bg,
    stroke: (left: 3pt + brd),
    radius: 3pt,
    body
  )
}

// Example box with title
#let example-box(number, title, body) = {
  v(0.3em)
  block(
    width: 100%,
    stroke: 1.5pt + accent,
    radius: 5pt,
    inset: 0pt,
    clip: true,
  )[
    #block(
      width: 100%,
      fill: accent,
      inset: (x: 9pt, y: 4pt),
    )[
      #text(fill: white, weight: "bold", size: 10pt)[範例#number　#title]
    ]
    #block(
      width: 100%,
      fill: white,
      inset: (x: 9pt, y: 6pt),
    )[#body]
  ]
  v(0.2em)
}

// Inline code style
#let op(code) = box(
  fill: neutral-bg,
  stroke: 0.5pt + neutral-brd,
  radius: 3pt,
  inset: (x: 4pt, y: 2pt),
  text(font: ("Menlo", "Courier New", "Courier"), size: 9.5pt, code)
)

// Param table for operations
#let param-table(rows) = {
  table(
    columns: (auto, auto, 1fr),
    inset: (x: 7pt, y: 4pt),
    stroke: 0.5pt + rgb("#BDBDBD"),
    fill: (col, row) => if row == 0 { accent-bg } else { white },
    align: (col, row) => if col == 0 { center } else { left },
    table.header(
      text(weight: "bold", fill: accent, "參數"),
      text(weight: "bold", fill: accent, "類型"),
      text(weight: "bold", fill: accent, "說明"),
    ),
    ..rows
  )
}

// ─── PAGE 1 — COVER ──────────────────────────────────────────────────────────
#page(
  margin: 0pt,
  background: block(width: 100%, height: 100%, fill: accent),
)[
  // Decorative circles
  #place(top + right, dx: 80pt, dy: -80pt,
    circle(radius: 160pt, fill: rgb("#1B5E20").transparentize(40%))
  )
  #place(bottom + left, dx: -60pt, dy: 60pt,
    circle(radius: 120pt, fill: rgb("#1B5E20").transparentize(40%))
  )
  #place(top + left, dx: 20pt, dy: 20pt,
    circle(radius: 40pt, fill: rgb("#4CAF50").transparentize(60%))
  )

  // Content centered
  #align(center + horizon)[
    #v(1fr)

    // Coconut icon (text-based)
    #text(size: 60pt)[🥥]

    #v(0.5em)

    // Main title
    #text(fill: white, size: 42pt, weight: "black",
      tracking: 4pt, [COCONUT WARS]
    )

    #v(0.2em)

    // COW badge
    #box(
      fill: white,
      radius: 20pt,
      inset: (x: 20pt, y: 6pt),
      text(fill: accent, size: 18pt, weight: "bold", [COW])
    )

    #v(0.6em)

    // Subtitle
    #text(fill: rgb("#C8E6C9"), size: 16pt, weight: "bold",
      [小隊員說明書]
    )

    #v(0.4em)

    // Divider
    #block(width: 200pt, height: 2pt, fill: rgb("#A5D6A7"))

    #v(0.4em)

    // Camp name
    #text(fill: rgb("#E8F5E9"), size: 13pt,
      [NTU CSIE Camp　椰島爭霸]
    )

    #v(0.3em)

    // Time badge
    #box(
      fill: rgb("#1B5E20"),
      radius: 6pt,
      inset: (x: 16pt, y: 8pt),
    )[
      #text(fill: white, size: 12pt, weight: "bold")[
        ⏱　最終大戰　15:10 – 15:45
      ]
    ]

    #v(0.5em)

    // Round info pills
    #grid(
      columns: (auto, auto, auto),
      column-gutter: 12pt,
      ..([3 回合], [× 7 分鐘], [每回合最多 5 操作]).map(t =>
        box(
          fill: rgb("#4CAF50").transparentize(30%),
          radius: 12pt,
          inset: (x: 12pt, y: 5pt),
          text(fill: white, size: 10.5pt, t)
        )
      )
    )

    #v(1fr)

    // Footer
    #text(fill: rgb("#A5D6A7"), size: 9pt)[
      請妥善保管此說明書，弄丟不補發。
    ]
    #v(0.6cm)
  ]
]

// ─── PAGE 2 — 前情提要 & 地圖結構 ────────────────────────────────────────────
#page[

  #section[前情提要]

  #callout(kind: "info")[
    COCONUT WARS（COW）是椰島爭霸的最終決戰。你在冒險累積的兵力與領地，將直接轉換為這場戰爭的起始資源。
  ]

  #v(0.2em)

  #table(
    columns: (auto, 1fr),
    inset: (x: 5pt, y: 3pt),
    stroke: 0.5pt + rgb("#BDBDBD"),
    fill: (col, row) => if row == 0 { accent-bg } else if calc.odd(row) { white } else { neutral-bg },
    table.header(
      text(weight: "bold", fill: accent, [項目]),
      text(weight: "bold", fill: accent, [說明]),
    ),
    [初始兵力], [椰島爭霸期間 4 次世界史更新所累積的兵力總和],
    [初始領地], [椰島爭霸結束時，你的小隊所佔領的所有島嶼。如果佔領複數個島嶼，初始兵力將平均分散在各島嶼上（無法整數分配的餘數將捨去）],
    [無領地者處理], [椰島爭霸結束時沒有領地，自動進駐中立小島出發],
    [每回合操作上限], [每回合最多提交 5 個操作（無效操作不計入上限，但是違規操作會計入）],
    [回合數], [共 3 回合，每回合 7 分鐘，同時提交操作後統一結算],
  )

  #v(0.2em)
  #section[地圖結構]

  #table(
    columns: (auto, auto, 1fr),
    inset: (x: 5pt, y: 3pt),
    stroke: 0.5pt + rgb("#BDBDBD"),
    fill: (col, row) => if row == 0 { accent-bg } else { white },
    table.header(
      text(weight: "bold", fill: accent, [島嶼類型]),
      text(weight: "bold", fill: accent, [數量]),
      text(weight: "bold", fill: accent, [特性]),
    ),
    [椰島],
    [12 座],
    [可被攻佔，每回合產出椰子（椰子依佔領狀況分配）],
    [中立小島 ⭐],
    [1 座],
    [安全區域，不可被攻擊；駐守兵力每回合 ×1.5；無領地隊伍起始點],
    [迷霧島 R1],
    [1 座],
    [第 2 回合起開放；按駐守比例分配 +1000 兵力/回合],
    [金錢島 R2],
    [1 座],
    [第 2 回合起開放；按駐守比例分配 +1000 椰子/回合],
    [漩渦 R3],
    [1 座],
    [第 2 回合起開放；奇數隊→+2000椰子；偶數隊→+2000兵力；4隊→無效果],
  )

  #v(0.15em)
  #text(size: 8pt, fill: mid-gray)[
    ＊資源點開放：R1/R2/R3 第 2 回合起。⭐ 中立小島全程安全。
  ]
]

// ─── PAGE 3 — 名詞對照表 & 操作一、二 ───────────────────────────────────────
#page[
  #section[名詞對照表]

  #table(
    columns: (auto, auto, 1fr),
    inset: (x: 5pt, y: 3pt),
    stroke: 0.5pt + rgb("#BDBDBD"),
    fill: (col, row) => if row == 0 { accent-bg } else if calc.odd(row) { white } else { neutral-bg },
    table.header(
      text(weight: "bold", fill: accent, [中文名詞]),
      text(weight: "bold", fill: accent, [英文／代號]),
      text(weight: "bold", fill: accent, [說明]),
    ),
    [兵力], [Troops], [戰鬥與移動資源，4 次世界史更新累積而來。並在戰爭中變動。],
    [椰子], [Victory Points], [最終排名依據，每回合由佔領島嶼產出],
    [領主], [Island Owner], [正式擁有島嶼的隊伍，椰子大部分歸領主所有],
    [駐守], [Garrison], [透過 union 進駐盟友島嶼的兵力，非領主身份，也可以分配島嶼產出資源。],
    [中立小島], [Neutral Zone], [安全區，不可攻擊，兵力每回合 ×1.5],
    [資源點], [Resource Islands], [R1/R2/R3，第 2 回合起開放的特殊島嶼],
    [操作衝突], [Op. Conflict], [同一地點總兵力需求超過可用量，所有相關操作無效],
    [偽平行], [Pseudo-Parallel], [所有操作以回合開始兵力同時執行，不可鏈式操作],
  )

  #v(0.5em)
  #section[操作一：移動（moving）]

  #op([moving(S, E, n)])　— 將己方 n 兵力從 S 移動到 E

  #v(0.3em)

  #param-table((
    [S], [己方島嶼], [出發地，必須是己方領地、中立小島、或資源點],
    [E], [目的地], [必須是己方領地、中立小島、或資源點；*不可移動至敵方領地*],
    [n], [正整數], [移動的兵力數量，不得超過 S 的可用兵力],
  ))

  #v(0.3em)
  #callout(kind: "warn")[
    *第 1 回合限制*：不可移動至資源點（R1/R2/R3），此操作視為無效，*不計入 5 個操作上限*。
  ]

  #v(0.5em)
  #section[操作二：進攻（attack）]

  #op([attack(S, E, n)])　— 以 n 兵力從 S 進攻敵方島嶼 E

  #v(0.3em)

  #param-table((
    [S], [己方島嶼], [出發地，必須是己方領地、中立小島、或資源點],
    [E], [敵方島嶼], [攻擊目標，必須是敵方（包含無主）島嶼],
    [n], [正整數], [出兵數量，不得超過 S 的可用兵力],
  ))

  #v(0.3em)

  #table(
    columns: (auto, 1fr),
    inset: (x: 5pt, y: 3pt),
    stroke: 0.5pt + rgb("#BDBDBD"),
    fill: (col, row) => if row == 0 { accent-bg } else { white },
    table.header(
      text(weight: "bold", fill: accent, [攻擊目標]),
      text(weight: "bold", fill: accent, [特殊規則]),
    ),
    [一般大島嶼], [正常戰鬥結算],
    [中立小島 ⭐], [操作*有效*（計入 5 個上限），但是違反世界法， n 兵力*立即損失*作為懲罰，不發動戰鬥],
    [資源點 R1/R2/R3], [操作*有效*（計入上限），但是違反世界法，n 兵力*立即損失*作為懲罰，不發動戰鬥],
  )

  #v(0.3em)
  #callout(kind: "warn")[
    *第 1 回合限制*：資源點未開放。攻擊資源點視為無效操作，*不計入 5 個操作上限*，且兵力不損失。
  ]

  #v(0.3em)
  #callout(kind: "neutral")[
    *（→ 參考範例一）*　移動與進攻的詳細範例請見第 6 頁。
  ]
]

// ─── PAGE 4 — 操作三、四 ─────────────────────────────────────────────────────
#page[
  #section[操作三：聯盟（union）]

  #op([union(S, P, E, n)])　— 將 n 兵力從 S 移至盟友 P 的島嶼 E 作為駐守

  #v(0.3em)

  #param-table((
    [S], [出發地], [必須是己方領地（含中立小島、資源點）],
    [P], [盟友小隊], [接收駐守的隊伍代號（例如 B）],
    [E], [目的地], [P 隊的島嶼，駐守兵力將防守此島],
    [n], [正整數], [移動的兵力數量],
  ))

  #v(0.25em)

  #callout(kind: "warn")[
    *聯盟必須雙向匹配*：A 和 B 兩方必須各自提交 union 操作，且 S、E、n 完全相同，P 互相指向對方。只有單方提交者，操作無效。
  ]

  #v(0.2em)

  #block(
    width: 100%,
    fill: accent-bg,
    stroke: 1pt + accent-mid,
    radius: 5pt,
    inset: 8pt,
  )[
    #text(weight: "bold", fill: accent)[聯盟操作格式說明]
    #v(0.15em)
    假設 1小隊 想派兵駐守 2小隊 的椰島B，出發地椰島A，派出 n 兵：
    #v(0.15em)
    #grid(
      columns: (1fr, 1fr),
      column-gutter: 10pt,
      block(
        fill: white, stroke: 1pt + accent, radius: 4pt, inset: (x: 6pt, y: 4pt), width: 100%,
      )[
        #text(weight: "bold", fill: accent)[1小隊 提交]
        #linebreak()
        #op([union(椰島A, 2, 椰島B, n)])
        #linebreak()
        #text(size: 8pt, fill: mid-gray)[P = 2（盟友是 2小隊）]
      ],
      block(
        fill: white, stroke: 1pt + accent, radius: 4pt, inset: (x: 6pt, y: 4pt), width: 100%,
      )[
        #text(weight: "bold", fill: accent)[2小隊 提交]
        #linebreak()
        #op([union(椰島A, 1, 椰島B, n)])
        #linebreak()
        #text(size: 8pt, fill: mid-gray)[P = 1；S、E、n 相同]
      ],
    )
    #v(0.15em)
    #text(size: 8.5pt)[
      ▸ 結果：n 兵力從椰島A 移動至椰島B，以「駐守」身份防守椰島B。
    ]
  ]

  #v(0.2em)
  #callout(kind: "neutral")[
    *（→ 參考範例二）*　聯盟防守的完整範例請見第 6 頁。
  ]

  #v(0.3em)
  #section[操作四：聯合進攻（union_attack）]

  #op([union_attack(S, P, E, n)])　— 聯合盟友 P 共同進攻島嶼 E

  #v(0.2em)

  #param-table((
    [S], [出發地], [己方領地、中立小島、或資源點],
    [P], [盟友列表], [單一盟友如 [B]，多位如 [B, C]；聯合方皆須列出其他所有參與者並以 [] 括號包住，否則視為無效操作。],
    [E], [攻擊目標], [敵方島嶼],
    [n], [正整數], [本隊出兵數量],
  ))

  #v(0.25em)

  #callout(kind: "warn")[
    *最大互信原則*：有效聯合 = 所有成員均在 P 中列出其他所有成員。系統取最大有效聯合；若人數相同，總兵力較多者優先。
  ]

  #v(0.2em)
  #callout(kind: "info")[
    *佔領判定*：聯合進攻勝利後，*出兵最多的隊伍*成為新領主；其餘隊伍以駐守身份留在島上。
  ]

  #v(0.2em)
  #callout(kind: "neutral")[
    *（→ 參考範例三）*　聯合進攻的完整範例請見第 7 頁。
  ]
]

// ─── PAGE 5 — 執行原則 & 回合結算 ────────────────────────────────────────────
#page[
  #section[執行原則]

  #subsection[偽平行（Pseudo-Parallel）]

  所有操作在回合開始時「同時」執行。這意味著：

  #v(0.2em)
  - 你*不能*在同一回合先移動再攻擊（移動後的兵力不能接著攻擊）
  - 所有操作的兵力消耗均以回合開始的兵力為依據。
  #v(0.2em)
  #callout(kind: "info")[
    *Tips*：你可以想像所有兵力同時出發並移動到海上，接著同時抵達目的地（同時戰鬥）。
  ]


  #v(0.25em)
  #subsection[操作衝突（Operation Conflict）]

  若同一地點（S）的多個操作，所需兵力總和超過該地點的可用兵力：

  #table(
    columns: (auto, 1fr),
    inset: (x: 5pt, y: 2.5pt),
    stroke: 0.5pt + rgb("#BDBDBD"),
    fill: (col, row) => if row == 0 { accent-bg } else { white },
    table.header(
      text(weight: "bold", fill: accent, [後果]),
      text(weight: "bold", fill: accent, [說明]),
    ),
    [所有操作無效], [該地點所有相關操作，全部視為無效（不是只有超額部分）],
    [強制移至中立小島], [該地點所有兵力*強制移至中立小島*],
    [不享有 ×1.5 加成], [被強制移至中立的兵力，本回合*不享有* ×1.5 效果],
  )

  #v(0.15em)
  #callout(kind: "neutral")[
    *（→ 參考範例四）*　操作衝突的詳細範例請見第 7 頁。
  ]

  #v(0.3em)
  #section[回合結算順序]

  #subsection[① 戰鬥結算]

  // Battle resolution flowchart
  #let fc-step(n, label, body) = {
    block(
      width: 100%, fill: accent, stroke: 1pt + accent, radius: 4pt,
      inset: (x: 7pt, y: 4pt),
      text(fill: white, size: 8.5pt, weight: "bold")[STEP #n　#label]
    )
    block(
      width: 100%, fill: neutral-bg, stroke: (left: 2pt + accent, bottom: 0.5pt + neutral-brd),
      radius: (bottom-left: 3pt, bottom-right: 3pt),
      inset: (x: 7pt, y: 4pt),
      text(size: 8pt, body)
    )
  }
  #let fc-branch(yes-text, no-text) = {
    v(0.1em)
    grid(
      columns: (1fr, 1fr),
      column-gutter: 5pt,
      block(fill: accent-bg, stroke: 0.5pt + accent, radius: 3pt, inset: (x: 5pt, y: 3pt),
        text(size: 8pt)[#text(fill: accent, weight: "bold")[✓ 是：]#yes-text]),
      block(fill: warn-bg, stroke: 0.5pt + warn-brd, radius: 3pt, inset: (x: 5pt, y: 3pt),
        text(size: 8pt)[#text(fill: rgb("#5D4037"), weight: "bold")[→ 否：]#no-text]),
    )
    v(0.15em)
    align(center)[#text(size: 10pt, fill: rgb("#9E9E9E"))[↓]]
    v(0.05em)
  }

  #fc-step("1", "比較兵力")[
    找出所有參戰單位（各進攻方 + 防守方）中兵力最大值。
  ]
  #fc-branch([最大兵力單位直接獲勝 ✓], [出現平手 → STEP 2])
  #fc-step("2", "守方優先")[
    平手方中，是否包含該島現任*領主*（防守方）？
  ]
  #fc-branch([防守方獲勝（0 兵力亦適用）✓], [無防守方 → STEP 3])
  #fc-step("3", "以少勝多")[
    比較各平手單位的*聯盟規模*（組成隊伍數）：規模最小者獲勝。#linebreak()
    （solo 1隊 ＞ 聯盟 2隊 ＞ 聯盟 3隊…）
  ]
  #fc-branch([規模最小唯一 → 該單位獲勝 ✓], [最小規模仍有複數平手 → STEP 4])
  #fc-step("4", "同歸於盡")[
    並列最小規模的所有單位*同時淘汰*，其兵力計入獎勵池。#linebreak()
    剩餘單位回到 STEP 1 重新裁決，直到唯一勝方。
  ]

  #v(0.15em)
  #callout(kind: "info")[
    *勝利獎勵*：勝方保留自身兵力 + ⌊（所有敗方兵力加總）×20%⌋；聯合進攻中每位成員*各自獨立*獲得此獎勵。*敗方*兵力全數損失。
  ]

  #v(0.2em)
  #subsection[② 椰子產出]

  #table(
    columns: (auto, 1fr),
    inset: (x: 5pt, y: 2.5pt),
    stroke: 0.5pt + rgb("#BDBDBD"),
    fill: (col, row) => if row == 0 { accent-bg } else { white },
    table.header(
      text(weight: "bold", fill: accent, [佔領狀況]),
      text(weight: "bold", fill: accent, [分配方式]),
    ),
    [僅 1小隊佔領], [1小隊獲得該島全部 X 椰子],
    [1小隊（領主）＋ 2小隊（駐守）],
    [1小隊獲得 ½X ＋ ½X×（1小隊兵力比例）；2小隊獲得 ½X×（2小隊兵力比例）],
  )

  #v(0.2em)
  #subsection[③ 中立小島]

  - 中立小島上的所有兵力 × 1.5（四捨五入）
  - 若某隊伍全部兵力歸零，獲得 *+1000 救濟兵力*

  #v(0.2em)
  #subsection[④ 資源點分配]

  - 迷霧島 R1：+1000 兵力，按各隊駐守比例分配
  - 金錢島 R2：+1000 椰子，按各隊駐守比例分配
  - 漩渦 R3：依佔領隊數效果，按各隊駐守比例分配（見地圖說明）
]

// ─── PAGE 6 — 操作範例（1 of 2）────────────────────────────────────────────
#page[
  #section[操作範例（1 / 2）]

  #example-box("一", "移動與進攻")[
    *情境*：1小隊有 500 兵在椰島A（己方）；2小隊有 300 兵在椰島B（己方）。

    *本回合操作*：1小隊：#op([moving(椰島A, 椰島C, 200)])；2小隊：#op([attack(椰島B, 椰島A, 250)])

    *戰鬥*：椰島A — 1小隊防守 500 vs 2小隊攻擊 250 → *1小隊獲勝*（偽平行：1小隊的移動不影響防守，防守仍以 500 計）

    #v(0.1em)
    *結算結果*
    #table(
      columns: (auto, 1fr),
      inset: (x: 5pt, y: 2.5pt),
      stroke: 0.5pt + rgb("#BDBDBD"),
      fill: white,
      [1小隊], [椰島A：500 + ⌊250×20%⌋ = *550 兵*；椰島C：200 兵移入（×1.5 = 300）],
      [2小隊], [進攻失敗，損失 250 兵，剩 50 兵在椰島B],
    )
  ]

  #v(0.2em)

  #example-box("二", "聯盟防守（union）")[
    *情境*：2小隊有 300 兵在椰島B；1小隊有 500 兵在椰島A；3小隊（400 兵）計畫攻打椰島B。1小隊+2小隊 協議聯盟。

    *本回合操作*：
    - 1小隊：#op([union(椰島A, 2, 椰島B, 200)])
    - 2小隊：#op([union(椰島A, 1, 椰島B, 200)])　（S、E、n 相同，P 互指）
    - 3小隊：#op([attack(椰島C, 椰島B, 400)])

    *戰鬥*：椰島B — 3小隊攻 400 vs（2小隊防 300 ＋ 1小隊駐守 200 = *500*）→ 防守方勝利

    #v(0.1em)
    *結算結果*
    #table(
      columns: (auto, 1fr),
      inset: (x: 5pt, y: 2.5pt),
      stroke: 0.5pt + rgb("#BDBDBD"),
      fill: white,
      [2小隊（領主）], [守住椰島B，獲 +80 獎勵兵（⌊400×20%⌋）],
      [1小隊], [200 駐守兵留在椰島B；1小隊自身也獲 +80 獎勵兵（各自獨立）],
      [3小隊], [損失 400 兵，椰島C 歸零 → 獲 +1000 救濟兵力],
    )
  ]
]

// ─── PAGE 7 — 操作範例（2 of 2）& 最終排名 ──────────────────────────────────
#page[
  #section[操作範例（2 / 2）]

  #example-box("三", "聯合進攻（union_attack）")[
    *情境設定*
    #table(
      columns: (auto, auto, 1fr),
      inset: (x: 5pt, y: 2.5pt),
      stroke: 0.5pt + rgb("#BDBDBD"),
      fill: white,
      [隊伍], [位置], [兵力],
      [1小隊], [椰島A（己方）], [400],
      [2小隊], [椰島B（己方）], [300],
      [3小隊], [椰島E（己方）], [500（防守方）],
    )
    #v(0.2em)
    *本回合操作*

    - 1小隊：#op([union_attack(椰島A, [2], 椰島E, 400)])
    - 2小隊：#op([union_attack(椰島B, [1], 椰島E, 300)])

    兩方 P 互相列出對方 → 最大互信聯合 1小隊+2小隊 成立

    #v(0.2em)
    *戰鬥結算*：椰島E：1小隊+2小隊 聯合 700 兵 vs 3小隊防守 500 兵 → 1小隊+2小隊 *獲勝*

    佔領判定：1小隊出兵 400 > 2小隊出兵 300 → *1小隊成為椰島E 新領主*，2小隊以駐守身份留守

    #v(0.15em)
    *結算結果*
    #table(
      columns: (auto, auto, 1fr),
      inset: (x: 5pt, y: 2.5pt),
      stroke: 0.5pt + rgb("#BDBDBD"),
      fill: white,
      [隊伍], [身份], [結果],
      [1小隊], [新領主], [400 + ⌊500×20%⌋ = 400 + 100 = *500 兵*，成為椰島E 領主],
      [2小隊], [駐守], [300 + ⌊500×20%⌋ = 300 + 100 = *400 兵*，駐守椰島E],
      [3小隊], [失敗], [損失 500 兵，椰島E 易主],
    )
  ]

  #v(0.25em)

  #example-box("四", "操作衝突")[
    *情境設定*

    1小隊：椰島A（己方），可用兵力 *200*

    #v(0.2em)
    *本回合操作*

    - 1小隊操作①：#op([moving(椰島A, 椰島C, 150)])　需要 150 兵
    - 1小隊操作②：#op([attack(椰島A, 椰島B, 100)])　需要 100 兵

    總需求：150 + 100 = *250 兵 > 200 可用兵力*　→ *操作衝突！*

    #v(0.2em)
    #callout(kind: "warn")[
      ⚠ 操作衝突時，椰島A 的「全部」操作（包含操作①和操作②）均視為無效。不是只有超額的部分，而是所有操作一起作廢。
    ]

    #v(0.2em)
    *結算結果*
    #table(
      columns: (auto, 1fr),
      inset: (x: 5pt, y: 2.5pt),
      stroke: 0.5pt + rgb("#BDBDBD"),
      fill: white,
      [操作①②], [全部無效，1小隊 的這 2 個操作均不執行],
      [200 兵], [*強制移至中立小島*，且本回合*不享有* ×1.5 加成],
    )
  ]

  #v(0.3em)
  #section[最終排名]

  三回合結束後，累計*椰子（Victory Points）最高*的隊伍獲勝。

  #v(0.2em)
  #table(
    columns: (auto, auto, 1fr),
    inset: (x: 5pt, y: 3pt),
    stroke: 0.5pt + rgb("#BDBDBD"),
    fill: (col, row) => if row == 0 { accent-bg } else if calc.odd(row) { white } else { neutral-bg },
    table.header(
      text(weight: "bold", fill: accent, [排名]),
      text(weight: "bold", fill: accent, [獎懲]),
      text(weight: "bold", fill: accent, [備註]),
    ),
    [🥇 第 1 名], [獲得王冠獎勵], [椰子最高隊伍],
    [🥈 第 2 名], [獲得王冠獎勵], [椰子第二高隊伍],
    [倒數第 2 名], [面臨懲罰], [],
    [倒數第 1 名], [面臨懲罰], [椰子最低隊伍],
  )

  #v(0.25em)
  #callout(kind: "warn")[
    *加油！* COCONUT WARS 從 15:10 開始，在此之前請確認你的小隊策略。一旦回合開始，操作提交後即無法更改。祝旗開得勝！ 🥥
  ]

  #v(0.25em)
  #align(center)[
    #text(fill: rgb("#9E9E9E"), size: 8.5pt)[
      COCONUT WARS 小隊員說明書　｜　NTU CSIE Camp 椰島爭霸　｜　請勿外流
    ]
  ]
]
