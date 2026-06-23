// 椰島爭霸 小隊員說明書
// NTU CSIE Camp — Typst 0.13.1

// ── Page Setup ──────────────────────────────────────────────────────────────
#set page(
  paper: "a4",
  margin: (top: 1.5cm, bottom: 1cm, left: 1cm, right: 1cm),
  header: context {
    let pg = counter(page).get().first()
    if pg > 1 {
      set text(size: 9pt, fill: rgb("#555555"))
      grid(
        columns: (1fr, auto),
        align: (left, right),
        [椰島爭霸　小隊員說明書],
        [第 #pg 頁],
      )
      line(length: 100%, stroke: 0.5pt + rgb("#CCCCCC"))
    }
  },
)

#set text(
  font: ("PingFang TC", "Helvetica Neue", "Arial"),
  size: 10.5pt,
  lang: "zh",
  region: "TW",
)

#set par(leading: 0.75em, spacing: 0.9em)

// ── Color Palette ────────────────────────────────────────────────────────────
#let c-green      = rgb("#2E7D32")
#let c-green-light = rgb("#E8F5E9")
#let c-green-mid  = rgb("#81C784")
#let c-warn       = rgb("#E65100")
#let c-warn-light = rgb("#FFF3E0")
#let c-info       = rgb("#1565C0")
#let c-info-light = rgb("#E3F2FD")
#let c-row-alt    = rgb("#F1F8E9")
#let c-white      = white
#let c-black      = rgb("#212121")

// ── Heading Styles ───────────────────────────────────────────────────────────
// Level-1: filled green box, white bold text
#show heading.where(level: 1): it => {
  v(0.6em)
  block(
    width: 100%,
    fill: c-green,
    radius: 4pt,
    inset: (x: 10pt, y: 6pt),
    {
      set text(fill: white, weight: "bold", size: 12pt)
      it.body
    },
  )
  v(0.3em)
}

// Level-2: green text with underline
#show heading.where(level: 2): it => {
  v(0.4em)
  {
    set text(fill: c-green, weight: "bold", size: 11pt)
    underline(it.body)
  }
  v(0.2em)
}

// Level-3: bold dark text
#show heading.where(level: 3): it => {
  v(0.3em)
  {
    set text(weight: "bold", size: 10.5pt)
    it.body
  }
  v(0.15em)
}

// ── Callout Boxes ────────────────────────────────────────────────────────────
#let note-box(body) = block(
  width: 100%,
  fill: c-info-light,
  stroke: (left: 3pt + c-info),
  radius: (right: 4pt),
  inset: (x: 10pt, y: 7pt),
  body,
)

#let warn-box(body) = block(
  width: 100%,
  fill: c-warn-light,
  stroke: (left: 3pt + c-warn),
  radius: (right: 4pt),
  inset: (x: 10pt, y: 7pt),
  body,
)

#let rule-box(body) = block(
  width: 100%,
  fill: c-green-light,
  stroke: (left: 3pt + c-green),
  radius: (right: 4pt),
  inset: (x: 10pt, y: 7pt),
  body,
)

// ── Table Helper ─────────────────────────────────────────────────────────────
// Standard table styling: green header, alternating rows
#let styled-table(..args) = {
  set table(
    stroke: (x, y) => (
      bottom: 0.5pt + rgb("#BDBDBD"),
      right: if x > 0 { 0.5pt + rgb("#E0E0E0") } else { none },
    ),
    fill: (x, y) => if y == 0 { c-green } else if calc.odd(y) { c-row-alt } else { white },
    inset: (x: 8pt, y: 6pt),
  )
  set text(size: 10pt)
  show table.cell.where(y: 0): set text(fill: white, weight: "bold")
  table(..args)
}

// ── Divider ──────────────────────────────────────────────────────────────────
#let divider = {
  v(0.3em)
  line(length: 100%, stroke: 0.5pt + c-green-mid)
  v(0.3em)
}

// ════════════════════════════════════════════════════════════════════════════
// PAGE 1 — COVER
// ════════════════════════════════════════════════════════════════════════════
#set page(numbering: none)

#v(3cm)

// Main title block
#block(
  width: 100%,
  fill: c-green,
  radius: 8pt,
  inset: (x: 20pt, y: 24pt),
  {
    set align(center)
    set text(fill: white)
    text(size: 36pt, weight: "bold")[椰島爭霸]
    linebreak()
    v(4pt)
    text(size: 16pt)[COCONUT ISLAND OVERLORD]
  },
)

#v(1.2cm)

// Subtitle band
#block(
  width: 100%,
  fill: c-green-light,
  stroke: 1pt + c-green,
  radius: 6pt,
  inset: (x: 16pt, y: 14pt),
  {
    set align(center)
    set text(fill: c-green, weight: "bold", size: 18pt)
    [小隊員說明書]
  },
)

#v(1.2cm)

#align(center)[
  #set text(size: 13pt, fill: rgb("#444444"))
  *NTU CSIE CAMP*
  #linebreak()
  #v(4pt)
  #set text(size: 11pt)
  椰島爭霸　#h(1em) 13:00 – 15:45
]

#v(1.4cm)

// Coconut island illustration (text art)
#align(center)[
  #block(
    fill: c-green-light,
    radius: 50%,
    width: 7cm,
    height: 7cm,
    inset: 0pt,
    {
      set align(center + horizon)
      text(size: 60pt)[🌴]
    },
  )
]

#v(1.4cm)

// Quote
#align(center)[
  #block(
    width: 80%,
    stroke: (left: 4pt + c-green, right: 4pt + c-green),
    inset: (x: 16pt, y: 10pt),
    {
      set text(size: 10.5pt, style: "italic", fill: rgb("#555555"))
      [「海潮退去之後，只剩下椰島——還有那些渴望統治它們的意志。」]
    },
  )
]

#v(0.5cm)
#align(center)[
  #set text(size: 9pt, fill: rgb("#888888"))
  Made by OuO
]

// ════════════════════════════════════════════════════════════════════════════
// PAGE 2 — 世界觀背景 + 名詞對照表
// ════════════════════════════════════════════════════════════════════════════
#pagebreak()
#set page(numbering: "1")
#counter(page).update(2)

= 世界觀背景

#v(0.2em)

在古老傳說中，椰子樹並非普通植物——它們是連結天地的「*聖椰*」，由椰子樹之神 *可可納（Kokona）* 守護了千萬年。

然而人類的戰爭把砲火打進了聖椰林，同時工業的廢水也毒害著大海。

海神 *帝亞瑪（Tiama）* 與可可納相遇，沒有多說一句話——他們聯手召喚了一道巨大海嘯，舊世界的文明在一個下午內全部沉入了海底。

浪平之後，可可納從海底撈起 *12 顆聖椰種子*，親手種入洋面。每顆種子落處，大地隆起，不同的聖椰魔法重塑著環境並孕育出新的文明——這便是 *12 座椰島*，新世界僅有的土地。海嘯退去時，舊世界的珍稀礦石被衝上沙灘，人們稱之為「*海石*」，成為椰島通行的貨幣。

為了避免歷史重演，兩神需要一個代理人來管理世界，於是共同創造了 *10 個 AI Agent*，並將從中選出最聰明、最強大的 Agent 作為世界代理人，而決勝的課題即是：

#align(center)[
  #block(
    fill: c-green-light,
    stroke: 1pt + c-green,
    radius: 6pt,
    inset: (x: 14pt, y: 10pt),
    {
      set text(weight: "bold", size: 11pt, fill: c-green)
      [征服椰島，成為唯一的椰島霸主。]
    },
  )
]

#v(0.4em)

你的小隊，就是其中一個 *AI Agent*。去不同的椰島冒險並壯大你們的勢力吧！

在漫長的征途之後，所有 Agent 將在 *COCONUT WARS*（簡稱 *COW*）這場最終決戰中，以兵力廝殺，搶奪最多的「椰子」，在可可納面前證明自己才是這片海洋的主宰。

#divider

= 名詞對照表

#v(0.3em)

#styled-table(
  columns: (auto, 1fr, auto),
  align: (center, left, center),
  table.header(
    [術語], [意義說明], [備註],
  ),
  [小隊], [你的隊伍（1小～10小）], [基本單位],
  [小組], [一小隊分成兩組(1a、1b～10a、10b)], [各約6人],
  [領地/椰島], [各個椰島教室（共12間）], [可佔領],
  [旗子], [佔領領地的標記物], [有小隊顏色之分],
  [海石], [遊戲中的主要貨幣], [用於中央市集購買],
  [兵力], [COCONUT WARS 的戰鬥資源], [由冒險與佔領椰島累積],
  [椰子], [COCONUT WARS 的勝利分數], [在 COW 中獲取],
  [椰島矩陣], [每個椰島內的旗子佔領棋盤], [插旗區域],
  [世界核心], [大廳公佈欄，顯示即時領地狀態], [賽況追蹤],
  [世界史更新], [每隔約25分鐘一次的全局結算（共4次）], [U1–U4],
  [中央市集], [103 教室，購買道具卡的地方], [用海石消費],
  [COCONUT WARS / COW], [15:10 開始的最終決戰棋盤階段], [全員集合103],
)

#note-box[
  *提示：* 不確定某座椰島（某間教室）的規則？直接問該椰島的島主（關主）！路上也會有漂流的椰人（NPC）可能會帶來意外的收穫喔！
]

// ════════════════════════════════════════════════════════════════════════════
// PAGE 3 — 遊戲概覽 + 規則 A & B
// ════════════════════════════════════════════════════════════════════════════
#pagebreak()

= 遊戲概覽

#v(0.4em)

// Flowchart using boxes and arrows
#let flow-box(label, sublabel: none, fill: c-green, text-color: white) = {
  block(
    fill: fill,
    stroke: 1pt + c-green,
    radius: 6pt,
    inset: (x: 10pt, y: 8pt),
    {
      set align(center)
      set text(fill: text-color, weight: "bold", size: 10pt)
      label
      if sublabel != none {
        set text(weight: "regular", size: 8.5pt)
        linebreak()
        sublabel
      }
    },
  )
}

#let arrow = align(center)[
  #text(size: 14pt, fill: c-green)[↓]
]

#grid(
  columns: (1fr, auto, 1fr, auto, 1fr),
  column-gutter: 4pt,
  align: center + horizon,
  flow-box[13:00 \ 活動開始],
  text(size: 14pt, fill: c-green)[→],
  flow-box[分組出發 \ A1 ／ A2],
  text(size: 14pt, fill: c-green)[→],
  flow-box[自由探索 \ 12 個椰島],
)

#v(0.5em)
#align(center)[#text(size: 14pt, fill: c-green)[↓]]
#v(0.3em)

#grid(
  columns: (1fr, auto, 1fr, auto, 1fr),
  column-gutter: 4pt,
  align: center + horizon,
  flow-box(fill: c-green-light, text-color: c-black)[插旗佔領 \ 每次通關後],
  text(size: 14pt, fill: c-green)[⇄],
  flow-box(fill: c-green-light, text-color: c-black)[中央市集 \ 購買道具卡],
  text(size: 14pt, fill: c-green)[←],
  flow-box(fill: c-green-light, text-color: c-black)[世界史更新 \ U1 → U2 → U3 → U4],
)

#v(0.5em)
#align(center)[#text(size: 14pt, fill: c-green)[↓]]
#v(0.3em)

#align(center)[
  #block(
    fill: c-warn,
    stroke: 1pt + c-warn,
    radius: 6pt,
    inset: (x: 16pt, y: 10pt),
    {
      set text(fill: white, weight: "bold", size: 11pt)
      [15:10　COCONUT WARS（COW）最終決戰]
    },
  )
]

#divider

= 規則說明

== A．分組出發

#v(0.2em)

活動開始後，每支小隊將分為 *1a* 與 *1b* 兩組，各約 6 人。

#rule-box[
  - 兩組可以*自由選擇*要前往哪座椰島（教室），不需要依照固定路線。
  - 兩組可以*隨時會合*，共同行動或拆開行動皆可。
  - 各小組到達椰島後，向島主報到，即可開始挑戰。
]

#v(0.3em)

== B．闖關冒險

#v(0.2em)

每座椰島（教室）都設有關卡挑戰，完成後可獲得獎勵。*無論通關或失敗，都有獎勵！*

#styled-table(
  columns: (auto, 1fr, 1fr, 1fr),
  align: (center, left, center, center),
  table.header(
    [結果], [說明], [旗子數], [海石數],
  ),
  [✅ 通關], [成功完成關卡挑戰], [較多（如 3–5 面）], [較多（如 50–80）],
  [❌ 失敗], [未能完成，但仍有基本獎勵], [較少（如 1–2 面）], [較少（如 20–40）],
)

#note-box[
  *注意：* 不同椰島的難度與確切獎勵數量可能不同，並且可能拿到其他隊的旗子，請以島主現場說明為準。上表為大致範圍參考。
]

#warn-box[
  *重要：* 只有*通關*的小組才能在該領地插旗！失敗者拿到海石跟旗子後即須離開，無法插旗。詳見規則 C。
]
#warn-box[
  *重要：* 旗子可以保留在手上，在其他椰島挑戰成功後使用。
]

// ════════════════════════════════════════════════════════════════════════════
// PAGE 4 — 規則 C & D
// ════════════════════════════════════════════════════════════════════════════
#pagebreak()

== C．插旗佔領

#v(0.2em)

成功通關的小組，可以在該領地的 *矩陣*（4x4 or nxn）上插旗，宣示佔領。

#rule-box[
  *插旗規則：*
  + *只有通關* 的小組才能插旗。
  + 插旗必須在*離開領地前*完成，不可事後補插。
  + 可插*任意顏色*的旗子（己方旗 or 其他隊的旗），策略由你們決定。
  + 每座領地的*佔領判定規則各不相同*（例如：最長直線、最大連通區域、角落控制…），請向該教室的島主確認。
  + 同一個格子若已有旗子，不可以*覆蓋*插上新旗。除非該椰島有特殊規則。
]

#note-box[
  *小技巧：* 出發前先記下各領地的佔領規則，可以讓插旗策略更有效率！世界核心（大廳公佈欄）有各領地當前狀態可供參考。
]

#v(0.4em)

== D．兵力結算（世界史更新）

#v(0.2em)

每隔約 25 分鐘，兩神會進行一次 *世界史更新*（U1 ～ U4），對所有椰島的佔領狀態進行結算。

#v(0.4em)

*計算邏輯：*
依照各椰島的佔領規則以及佔領獎勵給於兵力。

#v(0.4em)

#rule-box[
  *兵力總計 = U1 + U2 + U3 + U4 四次結算的兵力加總*

  這個總兵力將是你進入 COCONUT WARS 的*初始兵力*，非常重要！
]

// ════════════════════════════════════════════════════════════════════════════
// PAGE 5 — 世界史更新時程 + 中央市集
// ════════════════════════════════════════════════════════════════════════════


= 世界史更新時程

#v(0.3em)

#styled-table(
  columns: (auto, auto, 1fr),
  align: (center, center, left),
  table.header(
    [代號], [時間], [說明],
  ),
  [*U0*], [13:00], [規則講解跟遊戲開始。],
  [*U1*], [13:30], [第一次全島結算，中央市集同時開放。],
  [*U2*], [13:55], [第二次結算 + 特殊事件。],
  [*U3*], [14:20], [第三次結算 +  特殊事件 + 公布 COW 說明書。],
  [*U4*], [14:45], [第四次結算 + 特殊事件。],
  [*COW*], [15:10], [全員集合 103 教室，COCONUT WARS 最終決戰開始！],
)

#note-box[
  U1 ～ U4 結算時，活動人員會到處通知，請注意聽；也可隨時至大廳查看世界核心公佈欄的即時戰況。
]
#note-box[
  COW 有合作與競爭的元素，可以利用冒險期間與其他小隊建立合作關係、討論戰術，也可以在 COW 中背刺他們。請小心選擇你的盟友與敵人！任何口頭合作都不算數，只有 COW 中的行動才是最終結果。
]

#divider

#pagebreak()

= 中央市集

#v(0.2em)

*地點：103 教室*　#h(1em) 開放時間：U1 結算後（約 13:30）~ 15:10 前

在中央市集，你可以用 *海石* 消費，抽取或直接購買 *道具卡*，為你的策略加分！

== 抽卡牌池

#styled-table(
  columns: (auto, auto, 1fr, auto),
  align: (center, center, left, center),
  table.header(
    [牌池], [費用], [可能出現的稀有度], [建議時機],
  ),
  [初級牌池], [30 海石], [N（普通）～ R（稀有）], [資源不多時],
  [中級牌池], [50 海石], [N ～ SR（超稀有）], [穩定收益後],
  [高級牌池], [100 海石], [R ～ SSR（最高稀有）], [衝高端道具時],
)

== 直購價格

#styled-table(
  columns: (auto, auto, 1fr),
  align: (center, center, left),
  table.header(
    [稀有度], [直購費用], [特性],
  ),
  [N　普通], [30 海石], [效果基本，適合補充用],
  [R　稀有], [50 海石], [效果明顯，CP 值高],
  [SR　超稀有], [100 海石], [強效，影響單場結算],
  [SSR　最高稀有], [200 海石], [遊戲改變者，全場最強效果],
)

== 道具卡範例

#v(0.2em)

以下為部分道具卡示意，實際牌池由工作人員決定：

#styled-table(
  columns: (auto, auto, 1fr),
  align: (center, center, left),
  table.header(
    [卡名], [稀有度], [效果說明],
  ),
  [延時沙漏], [N], [本次關卡挑戰時間延長 +120 秒（僅限一次使用）。],
  [煉金術], [R], [下一次通關所獲得的海石 +50%。],
  [事半功倍], [R], [下次世界史更新中，若你佔領某領地，該領地兵力獎勵 ×1.5。],
  [台灣巴菲特], [SSR], [將你目前持有的所有海石兌換為兵力（1 海石 = 200 兵力）。],
)

#rule-box[
  *使用道具卡：* 使用前請先告知島主或是工作人員，確認生效。卡片為一次性使用。卡片效果請仔細閱讀卡面說明。
]

// ════════════════════════════════════════════════════════════════════════════
// PAGE 6 — COCONUT WARS + 最終排名
// ════════════════════════════════════════════════════════════════════════════
#pagebreak()

= 前往 COCONUT WARS

#v(0.3em)

*15:10 整，全員集合 103 教室——最終決戰正式開始！*

#v(0.3em)

== 進場資源

#styled-table(
  columns: (auto, 1fr),
  align: (left, left),
  table.header(
    [項目], [說明],
  ),
  [*初始兵力*], [U1 + U2 + U3 + U4 四次世界史更新兵力的加總（可為負值）。],
  [*初始領地*], [15:10 時，你的旗子在哪些椰島達成佔領條件，那些椰島就是你的初始領地。],
  [*無領地者*], [15:10 時沒有任何佔領領地的隊伍，將從中立島出發。],
  [*決戰目標*], [3 個回合結束後，擁有最多「椰子」的小隊即為椰島霸主！],
)

#v(0.4em)

#warn-box[
  ⚠️ *重要提醒：*

  冒險階段（13:00–15:10）的表現*直接影響*你進入 COW 的兵力和領地。
  不要小看冒險的積累——它決定了你在最終決戰的起點！
]

#v(0.5em)

== COW 操作指令

COCONUT WARS 是一個策略型的多回合戰略階段，共進行 *3 回合*，每回合 *7 分鐘*。

你將使用以下四種操作指令來控制你的 Agent：

#block(
  width: 100%,
  fill: c-green-light,
  stroke: 1.5pt + c-green,
  radius: 6pt,
  inset: (x: 14pt, y: 12pt),
  {
    set text(size: 10.5pt)
    grid(
      columns: (auto, 1fr),
      column-gutter: 12pt,
      row-gutter: 8pt,
      align: (left, left),
      {set text(weight: "bold", fill: c-green); [`moving()`]},
      [將你的兵力移動至相鄰領地。],
      {set text(weight: "bold", fill: c-green); [`attack()`]},
      [以兵力攻擊相鄰的敵方領地，消滅敵方守備兵力後奪取該地。],
      {set text(weight: "bold", fill: c-green); [`union()`]},
      [與相鄰友方領地進行兵力合流。],
      {set text(weight: "bold", fill: c-green); [`union_attack()`]},
      [聯合相鄰友方共同發動進攻。],
    )
  },
)

#v(0.4em)

#note-box[
  COW 的詳細規則、操作格式與戰場地圖，將在 U3 後公告，並在 15:10 前做戰前說明，請勿錯過！
  #align(center)[
    #text(weight: "bold", size: 11pt, fill: c-info)[《COCONUT WARS 決戰手冊》]
  ]

]

#divider

= 最終排名與獎懲

#v(0em)

COW 三回合結束後，依照各隊累積的 *椰子* 排名：

#styled-table(
  columns: (auto, auto, 1fr),
  align: (center, center, left),
  table.header(
    [排名], [稱號], [獎懲說明],
  ),
  [🏆 第 1 名], [*椰島霸主*], [頒發王冠！全場最強 AI Agent。],
  [🥈 第 2 名], [*守護者*], [頒發王冠，同為強者。],
  [⋯], [其他名次], [光榮完賽。],
  [🐔 倒數第 1&2 名], [敗軍之將], [登台接受處罰！],
)

#v(0.4em)

#rule-box[
  *記住：椰島霸主，不只靠蠻力——也靠智慧、合作、與背刺。*

  祝各位 AI Agent 旗開得勝，願最強者統治椰島！🌴
]

#v(1fr)

#align(center)[
  #set text(size: 8.5pt, fill: rgb("#999999"))
  NTU CSIE Camp 活動組　製作　｜　椰島爭霸 小隊員說明書　｜　如有疑問請洽工作人員
]
