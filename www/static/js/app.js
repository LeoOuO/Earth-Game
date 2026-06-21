/* ── Constants ────────────────────────────────────────────────────────────── */
const TEAM_COLORS = {
  '1':'#f85149','2':'#58a6ff','3':'#3fb950','4':'#e3b341','5':'#bc8cff',
  '6':'#39d0d8','7':'#f778ba','8':'#c9d241','9':'#c68642','10':'#7a8ea8',
};

const ALL_TEAMS = ['1','2','3','4','5','6','7','8','9','10'];

const ISLANDS = [
  "人類王國","精靈森域","龍族火山","獸人荒原","巨人山丘","侏儒劇場",
  "狐族賭館","機械王國","布丁狗族","河童國","哥布林族","套娃族",
];
const TERRITORY_DIFF = {
  "人類王國":"★★★★","精靈森域":"★★★","龍族火山":"★★★★★",
  "獸人荒原":"★★","巨人山丘":"★★","侏儒劇場":"★★",
  "狐族賭館":"★★★","機械王國":"★★★★","布丁狗族":"★★★★★",
  "河童國":"★★★★★","哥布林族":"★★★","套娃族":"★★★",
};
const TERRITORY_POWER = {
  "人類王國":900,"精靈森域":700,"龍族火山":1000,"獸人荒原":600,
  "巨人山丘":600,"侏儒劇場":600,"狐族賭館":700,"機械王國":900,
  "布丁狗族":1000,"河童國":1000,"哥布林族":700,"套娃族":700,
};
const SPECIAL_ZONES = [
  {name:"中立小島", note:"中立，兵力×1.5/回合", icon:"🏝", code:"NEU"},
  {name:"迷霧島",   note:"R1：1000兵力/回合（第2回合起）", icon:"🌫", code:"FOG"},
  {name:"金錢島",   note:"R2：1000國力/回合（第2回合起）", icon:"💰", code:"GOLD"},
  {name:"漩渦",     note:"R3：依人數決定（第2回合起）",    icon:"🌀", code:"VORT"},
];

/* Island English codes */
const ISLAND_CODES = {
  "人類王國":"HK","精靈森域":"ELF","龍族火山":"DV","獸人荒原":"ORC",
  "巨人山丘":"GNT","侏儒劇場":"DWF","狐族賭館":"FOX","機械王國":"MK",
  "布丁狗族":"PUD","河童國":"KPA","哥布林族":"GOB","套娃族":"DOLL",
  "中立小島":"NEU","迷霧島":"FOG","金錢島":"GOLD","漩渦":"VORT",
};

/* Island positions on real-mode sea map (% of container width/height) */
const ISLAND_POSITIONS = {
  // Resource row (top)
  "迷霧島":   {l:20, t:9},
  "金錢島":   {l:50, t:9},
  "漩渦":     {l:79, t:9},
  // Main islands row 1
  "人類王國": {l:8,  t:27},
  "精靈森域": {l:32, t:21},
  "龍族火山": {l:60, t:27},
  "獸人荒原": {l:85, t:21},
  // Main islands row 2
  "巨人山丘": {l:16, t:51},
  "侏儒劇場": {l:42, t:46},
  "狐族賭館": {l:67, t:52},
  "機械王國": {l:87, t:46},
  // Main islands row 3
  "布丁狗族": {l:6,  t:72},
  "河童國":   {l:30, t:76},
  "哥布林族": {l:57, t:70},
  "套娃族":   {l:80, t:74},
  // Neutral (bottom)
  "中立小島": {l:47, t:89},
};

/* ── State ────────────────────────────────────────────────────────────────── */
let gameState = null;
let validatedCommands = {};
let execLog = [];
let selectedTeam = '1';
let currentMode = 'analysis';  // 'analysis' | 'real'
let _initialSetupData = null;   // saved at startGame(), used to pre-fill on reset

/* ── Init ─────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  buildSetupScreen();
  fetchState();
});

/* ── Setup screen ─────────────────────────────────────────────────────────── */
function buildSetupScreen() {
  const container = document.getElementById('team-checkboxes');
  ALL_TEAMS.forEach(t => {
    const item = document.createElement('label');
    item.className = 'team-checkbox-item checked';
    item.style.borderColor = (TEAM_COLORS[t] || '#888') + '88';
    item.style.color = TEAM_COLORS[t] || '#888';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = true;
    cb.dataset.team = t;
    cb.addEventListener('change', () => item.classList.toggle('checked', cb.checked));
    item.appendChild(cb);
    item.appendChild(document.createTextNode(`隊 ${t}`));
    container.appendChild(item);
  });

  const tbody = document.getElementById('territory-init-tbody');
  ISLANDS.forEach(zone => {
    const code = ISLAND_CODES[zone] || '';
    const tr = document.createElement('tr');
    let opts = '<option value="">— 無 —</option>';
    ALL_TEAMS.forEach(t => { opts += `<option value="${t}">隊 ${t}</option>`; });
    tr.innerHTML = `
      <td style="font-weight:600">${zone} <span style="font-size:9px;color:var(--accent);font-family:monospace">${code}</span></td>
      <td style="color:var(--text-muted)">${TERRITORY_DIFF[zone]||''}</td>
      <td style="display:flex;align-items:center;gap:6px">
        <select class="setup-input" data-zone-team="${zone}" style="width:75px">${opts}</select>
        <input type="number" min="0" value="" class="setup-input" data-zone-n="${zone}"
               placeholder="兵力" style="width:80px">
      </td>`;
    tbody.appendChild(tr);
  });

  const troopsContainer = document.getElementById('init-troops-rows');
  ALL_TEAMS.forEach(t => {
    const div = document.createElement('div');
    div.style.cssText = 'display:flex;align-items:center;gap:4px;';
    div.innerHTML = `
      <span style="color:${TEAM_COLORS[t]||'#888'};font-weight:700;min-width:22px">隊${t}</span>
      <input type="number" min="0" value="0" class="setup-input init-troops-input"
             style="width:70px" data-troop-team="${t}" placeholder="兵力">`;
    troopsContainer.appendChild(div);
  });
}

function openSetup() { document.getElementById('setup-screen').classList.add('show'); }
function closeSetup() { document.getElementById('setup-screen').classList.remove('show'); }

async function startGame() {
  const rounds = parseInt(document.getElementById('setup-rounds').value) || 3;

  const teams = [];
  document.querySelectorAll('#team-checkboxes input[type=checkbox]').forEach(cb => {
    if (cb.checked) teams.push(cb.dataset.team);
  });
  if (teams.length < 2) { alert('至少選擇 2 支隊伍'); return; }

  const territories = {};
  document.querySelectorAll('[data-zone-team]').forEach(sel => {
    const zone = sel.dataset.zoneTeam;
    const team = sel.value;
    if (!team) return;
    const nInp = document.querySelector(`[data-zone-n="${zone}"]`);
    const n = parseInt(nInp?.value) || 0;
    if (n > 0) territories[zone] = {[team]: n};
  });

  const initTroops = {};
  document.querySelectorAll('[data-troop-team]').forEach(input => {
    const team = input.dataset.troopTeam;
    const n = parseInt(input.value) || 0;
    if (n > 0) initTroops[team] = n;
  });
  if (Object.keys(initTroops).length) {
    territories['中立小島'] = territories['中立小島'] || {};
    Object.entries(initTroops).forEach(([t, n]) => {
      territories['中立小島'][t] = (territories['中立小島'][t] || 0) + n;
    });
  }

  // Save setup data for pre-filling on future reset
  _initialSetupData = {
    teams: [...teams],
    max_rounds: rounds,
    zoneData: {},    // zone → {team, n}
    troopTexts: {},  // troop-team → value
  };
  document.querySelectorAll('[data-zone-team]').forEach(sel => {
    const zone = sel.dataset.zoneTeam;
    const nInp = document.querySelector(`[data-zone-n="${zone}"]`);
    _initialSetupData.zoneData[zone] = {team: sel.value, n: nInp?.value || ''};
  });
  document.querySelectorAll('[data-troop-team]').forEach(inp => {
    _initialSetupData.troopTexts[inp.dataset.troopTeam] = inp.value;
  });

  const res = await fetch('/api/setup', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({teams, max_rounds: rounds, territories}),
  });
  const data = await res.json();
  if (!data.ok) { alert(data.error); return; }
  closeSetup();
  applyState(data.state, {}, []);
}

/* ── Fetch state ─────────────────────────────────────────────────────────── */
async function fetchState() {
  const res = await fetch('/api/state');
  const data = await res.json();
  applyState(data.state, data.validated_commands, data.log);
  document.getElementById('btn-undo').disabled = !data.can_undo;
  document.getElementById('btn-redo').disabled = !data.can_redo;
}

function applyState(state, vcmds, log) {
  gameState = state;
  validatedCommands = vcmds || {};
  execLog = log || [];

  if (!state || state.phase === 'setup') {
    openSetup();
    return;
  }

  updateHeader();
  renderMap();
  renderScoreboard();
  renderCommandLog();
  populateTeamSelect();
  updateCmdCountHint();
}

/* ── Mode toggle ─────────────────────────────────────────────────────────── */
function toggleMode() {
  currentMode = currentMode === 'analysis' ? 'real' : 'analysis';
  const btn = document.getElementById('btn-mode');
  const analysisView = document.getElementById('analysis-view');
  const realMap = document.getElementById('real-map');
  if (currentMode === 'real') {
    btn.textContent = '📊 分析模式';
    btn.classList.add('active');
    analysisView.style.display = 'none';
    realMap.classList.add('show');
    renderRealMap();
  } else {
    btn.textContent = '🗺 真實模式';
    btn.classList.remove('active');
    analysisView.style.display = '';
    realMap.classList.remove('show');
  }
}

/* ── Header ──────────────────────────────────────────────────────────────── */
function updateHeader() {
  const s = gameState;
  const sub = s.sub_round || 0;
  const roundStr = sub > 0
    ? `回合 ${s.round}.${sub}`
    : `回合 ${s.round} / ${s.max_rounds}`;
  document.getElementById('round-info').textContent = roundStr;

  const banner = document.getElementById('phase-banner');
  if (s.phase === 'done') {
    banner.textContent = '🏆 遊戲結束！按「🏆 結算」查看最終排名。';
    banner.className = 'phase-banner show done';
    document.getElementById('btn-execute').disabled = true;
  } else {
    banner.className = 'phase-banner';
    document.getElementById('btn-execute').disabled = false;
  }
}

/* ── Analysis map ─────────────────────────────────────────────────────────── */
function renderMap() {
  renderIslands();
  renderSpecialZones();
  if (currentMode === 'real') renderRealMap();
}

function renderIslands() {
  const grid = document.getElementById('map-grid');
  grid.innerHTML = '';
  ISLANDS.forEach(zone => {
    const zdata = gameState.zones[zone] || {troops:{}, total:0, owner:null};
    grid.appendChild(makeZoneCard(zone, zdata, TERRITORY_POWER[zone]));
  });
}

function renderSpecialZones() {
  const container = document.getElementById('special-zones');
  container.innerHTML = '';
  const round = gameState.round;
  SPECIAL_ZONES.forEach(({name, note, icon, code}) => {
    const zdata = gameState.zones[name] || {troops:{}, total:0, owner:null};
    const locked = (name !== '中立小島') && (round < 2);
    const card = document.createElement('div');
    card.className = 'special-card territory-card' + (locked ? ' locked' : '');
    const owner = zdata.owner;
    const ownerColor = owner ? (TEAM_COLORS[owner] || '#888') : 'var(--border)';
    card.innerHTML = `
      <div class="territory-owner-bar" style="background:${ownerColor}"></div>
      <div class="territory-name">
        ${icon}
        <span>${name}</span>
        <span class="territory-code-badge">${code}</span>
        ${locked ? '<span class="lock-icon">🔒R2+</span>' : ''}
      </div>
      <div class="territory-breakdown" style="font-size:10px;color:var(--text-muted)">${note}</div>
      ${zdata.total > 0 ? renderTroopsBreakdown(zdata) : ''}
    `;
    container.appendChild(card);
  });
}

function makeZoneCard(zone, zdata, powerX) {
  const card = document.createElement('div');
  const owner = zdata.owner;
  const ownerColor = owner ? (TEAM_COLORS[owner] || '#888') : 'var(--border)';
  const isContested = Object.keys(zdata.troops).length > 1;
  const code = ISLAND_CODES[zone] || '';
  card.className = 'territory-card' + (isContested ? ' contested' : '');
  if (owner) card.style.borderTopColor = ownerColor;
  card.innerHTML = `
    <div class="territory-owner-bar" style="background:${ownerColor}"></div>
    <div class="territory-name">
      <span>${zone}</span>
      <span class="territory-code-badge">${code}</span>
      <span style="font-size:9px;color:var(--text-muted)">${TERRITORY_DIFF[zone]||''}</span>
    </div>
    <div class="territory-power-badge">${powerX}💎</div>
    <div class="territory-troops" style="color:${ownerColor}">${zdata.total || 0}</div>
    ${renderTroopsBreakdown(zdata)}
  `;
  return card;
}

function renderTroopsBreakdown(zdata) {
  const troops = zdata.troops || {};
  const entries = Object.entries(troops).sort((a,b) => b[1]-a[1]);
  if (!entries.length) return '<div class="territory-breakdown">（無人）</div>';
  const parts = entries.map(([t, n]) =>
    `<span style="color:${TEAM_COLORS[t]||'#888'}">${t}:${n}</span>`
  );
  return `<div class="territory-breakdown">${parts.join('  ')}</div>`;
}

/* ── Real mode map ────────────────────────────────────────────────────────── */
function renderRealMap() {
  const map = document.getElementById('real-map');
  // Remove old island elements (but keep anim-overlay)
  map.querySelectorAll('.real-island').forEach(el => el.remove());

  if (!gameState) return;
  const round = gameState.round;

  const allZones = [
    ...ISLANDS,
    "中立小島",
    "迷霧島", "金錢島", "漩渦",
  ];

  allZones.forEach(zone => {
    const pos = ISLAND_POSITIONS[zone];
    if (!pos) return;
    const zdata = gameState.zones[zone] || {troops:{}, total:0, owner:null};
    const owner = zdata.owner;
    const ownerColor = owner ? (TEAM_COLORS[owner] || null) : null;
    const isContested = Object.keys(zdata.troops || {}).length > 1;
    const code = ISLAND_CODES[zone] || zone;
    const isResource = ["迷霧島","金錢島","漩渦"].includes(zone);
    const isNeutral = zone === "中立小島";
    const locked = isResource && round < 2;

    const el = document.createElement('div');
    el.className = 'real-island' +
      (isResource ? ' resource' : '') +
      (isNeutral ? ' neutral' : '') +
      (owner ? ' has-owner' : '') +
      (isContested ? ' contested' : '');
    el.id = `ri-${code}`;
    el.style.left = pos.l + '%';
    el.style.top = pos.t + '%';
    if (ownerColor) el.style.setProperty('--island-color', ownerColor);

    // Troop breakdown
    const troops = zdata.troops || {};
    const troopEntries = Object.entries(troops).sort((a,b) => b[1]-a[1]);
    const breakdownHtml = troopEntries.length > 0
      ? troopEntries.map(([t,n]) =>
          `<span style="color:${TEAM_COLORS[t]||'#888'}">${t}:${n}</span>`
        ).join(' ')
      : '';

    const imgFile = `island_${code}_fake.png`;

    el.innerHTML = `
      <div class="ri-img-wrap">
        <img src="/static/assets/${imgFile}" alt="${code}" onerror="this.style.opacity='0.3'">
        ${owner ? `<div class="ri-owner-dot" style="background:${ownerColor}"></div>` : ''}
        ${locked ? '<div class="ri-lock">🔒</div>' : ''}
      </div>
      <div class="ri-label">
        <div class="ri-code">${code}</div>
        <div class="ri-name">${zone}</div>
        ${zdata.total > 0 ? `<div class="ri-troops">${zdata.total}⚔</div>` : ''}
        ${breakdownHtml ? `<div class="ri-breakdown">${breakdownHtml}</div>` : ''}
      </div>
    `;
    map.appendChild(el);
  });
}

/* ── Scoreboard ──────────────────────────────────────────────────────────── */
function renderScoreboard() {
  const list = document.getElementById('score-list');
  list.innerHTML = '';
  const np = gameState.national_power || {};
  const teams = gameState.teams || [];
  const sorted = [...teams].sort((a,b) => (np[b]||0) - (np[a]||0));
  sorted.forEach(team => {
    const item = document.createElement('div');
    item.className = 'score-item';
    const totalTroops = Object.values(gameState.zones || {})
      .reduce((s, z) => s + ((z.troops||{})[team] || 0), 0);
    item.innerHTML = `
      <div class="score-dot" style="background:${TEAM_COLORS[team]||'#888'}"></div>
      <span style="font-weight:700;color:${TEAM_COLORS[team]||'#888'}">隊${team}</span>
      <span class="score-val">${np[team]||0}<span style="font-size:9px">💎</span></span>
      <span class="score-troops">${totalTroops}⚔</span>
    `;
    list.appendChild(item);
  });
}

/* ── Command log ─────────────────────────────────────────────────────────── */
function renderCommandLog() {
  const container = document.getElementById('cmd-entries');
  container.innerHTML = '';
  const teams = gameState.teams || [];
  let hasAny = false;

  teams.forEach(team => {
    const cmds = validatedCommands[team];
    if (!cmds || !cmds.length) return;
    hasAny = true;
    const group = document.createElement('div');
    group.className = 'team-group';
    group.innerHTML = `
      <div class="team-group-header">
        <div class="team-group-dot" style="background:${TEAM_COLORS[team]||'#888'}"></div>
        <span style="color:${TEAM_COLORS[team]||'#888'};font-weight:700">隊 ${team}</span>
        <span style="color:var(--text-muted)">${cmds.length} 條指令</span>
      </div>`;
    cmds.forEach(c => group.appendChild(makeCmdEntry(c, team)));
    container.appendChild(group);
  });

  // Also render ADMIN (set) commands
  const adminCmds = validatedCommands['ADMIN'];
  if (adminCmds && adminCmds.length) {
    hasAny = true;
    const group = document.createElement('div');
    group.className = 'team-group';
    group.innerHTML = `
      <div class="team-group-header">
        <div class="team-group-dot" style="background:var(--text-muted)"></div>
        <span style="color:var(--text-muted);font-weight:700">管理員</span>
        <span style="color:var(--text-muted)">${adminCmds.length} 條 set 指令</span>
      </div>`;
    adminCmds.forEach(c => group.appendChild(makeCmdEntry(c, 'ADMIN')));
    container.appendChild(group);
  }

  if (!hasAny) {
    container.innerHTML = '<div class="empty-log">尚未輸入任何指令</div>';
  }
}

function makeCmdEntry(c, team) {
  const div = document.createElement('div');
  let entryClass = 'cmd-entry';
  let statusIcon = '';
  let reasonText = '';
  let reasonClass = '';

  if (!c.parse_ok) {
    entryClass += ' invalid';
    statusIcon = '✗';
    reasonText = c.reason;
    reasonClass = 'error';
  } else if (!c.valid) {
    entryClass += ' invalid';
    statusIcon = '✗';
    reasonText = c.reason;
    reasonClass = 'error';
  } else if (c.op === 'union') {
    if (c.union_status === 'confirmed') {
      entryClass += ' confirmed';
      statusIcon = '🤝';
      reasonText = `聯盟成立（與隊 ${c.union_partner}，${c.union_role === 'requesting' ? '己方出兵' : '接受駐守'}）`;
      reasonClass = 'union-ok';
    } else {
      entryClass += ' pending';
      statusIcon = '⏳';
      reasonText = `等待隊 ${c.nation || '?'} 確認（尚未提交對應 union）`;
      reasonClass = 'union-pending';
    }
  } else if (c.op === 'union_attack') {
    statusIcon = '✓';
    if (c.effective_allies && c.effective_allies.length > 0) {
      reasonText = `聯盟：隊 ${c.effective_allies.join('+')} 共同進攻`;
      reasonClass = 'union-ok';
    } else {
      reasonText = '獨立進攻（無有效聯盟）';
    }
    if (c.warning) { reasonText += `  ⚠ ${c.warning}`; reasonClass = 'cmd-warn'; }
  } else {
    statusIcon = '✓';
    if (c.warning) { reasonText = `⚠ ${c.warning}`; reasonClass = 'cmd-warn'; }
  }

  div.className = entryClass;
  div.innerHTML = `
    <div class="cmd-badge" style="background:${TEAM_COLORS[team]||'#555'}22;color:${TEAM_COLORS[team]||'#888'}">${team}</div>
    <div class="cmd-content">
      <div class="cmd-raw">${escHtml(c.raw)}</div>
      ${reasonText ? `<div class="cmd-reason ${reasonClass}">${escHtml(reasonText)}</div>` : ''}
    </div>
    <div class="cmd-actions">
      <button class="cmd-action-btn edit" title="編輯" onclick="editCmd('${escHtml(team)}','${escHtml(c.raw.replace(/'/g,"\\'"))}')">✏</button>
      <button class="cmd-action-btn del" title="刪除" onclick="deleteCmd('${escHtml(team)}','${escHtml(c.raw.replace(/'/g,"\\'"))}')">✕</button>
    </div>
    <div class="cmd-status-icon">${statusIcon}</div>
  `;
  return div;
}

/* ── Team select (with bug fix) ──────────────────────────────────────────── */
function populateTeamSelect() {
  const sel = document.getElementById('team-select');
  const current = selectedTeam;  // save before clearing
  sel.innerHTML = '';
  (gameState.teams || []).forEach(t => {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = `隊 ${t}`;
    opt.style.color = TEAM_COLORS[t] || '#888';
    sel.appendChild(opt);
  });
  const adminOpt = document.createElement('option');
  adminOpt.value = 'ADMIN';
  adminOpt.textContent = '管理員（set 指令）';
  sel.appendChild(adminOpt);

  // Restore selection; fall back to first option if previous no longer valid
  const validValues = [...sel.options].map(o => o.value);
  sel.value = validValues.includes(current) ? current : (validValues[0] || '');
  selectedTeam = sel.value;
  updateCmdCountHint();
}

function onTeamSelectChange() {
  selectedTeam = document.getElementById('team-select').value;
  updateCmdCountHint();
}

function updateCmdCountHint() {
  const hint = document.getElementById('cmd-count-hint');
  if (!gameState || selectedTeam === 'ADMIN') { hint.textContent = ''; return; }
  const cmds = validatedCommands[selectedTeam] || [];
  const validOps = cmds.filter(c => c.valid && c.op !== 'set').length;
  hint.textContent = `目前 ${validOps}/5 個有效操作`;
}

/* ── Submit commands ─────────────────────────────────────────────────────── */
async function submitCommands() {
  const team = document.getElementById('team-select').value;
  const text = document.getElementById('cmd-textarea').value.trim();
  if (!text) return;

  const res = await fetch(`/api/commands/${team}`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({text}),
  });
  const data = await res.json();
  if (data.error) { alert(data.error); return; }

  validatedCommands = data.validated_commands || {};
  document.getElementById('cmd-textarea').value = '';
  renderCommandLog();
  updateCmdCountHint();
}

async function clearTeamCommands() {
  const team = document.getElementById('team-select').value;
  const res = await fetch(`/api/commands/${team}`, {method:'DELETE'});
  const data = await res.json();
  validatedCommands = data.validated_commands || {};
  renderCommandLog();
  updateCmdCountHint();
}

/* ── Execute round ───────────────────────────────────────────────────────── */
async function executeRound() {
  if (!confirm('確認執行本回合所有指令？')) return;

  const res = await fetch('/api/execute', {method:'POST'});
  const data = await res.json();
  if (data.error) { alert(data.error); return; }

  document.getElementById('btn-undo').disabled = false;
  document.getElementById('btn-redo').disabled = true;  // new execute clears redo

  if (currentMode === 'real' && (data.animation_events || []).length > 0) {
    await playAnimations(data.animation_events);
  }

  applyState(data.state, {}, data.log);
  showExecModal(data.log);
}

/* ── Animations (real mode) ─────────────────────────────────────────────── */

/* Live troop state: updated as boats depart/arrive during animation */
let _liveZT = null;

function startLiveState() {
  _liveZT = {};
  for (const [zone, zdata] of Object.entries(gameState.zones || {})) {
    _liveZT[zone] = {...(zdata.troops || {})};
  }
}

function liveDeduct(zone, team, n) {
  if (!_liveZT) return;
  if (!_liveZT[zone]) _liveZT[zone] = {};
  _liveZT[zone][team] = Math.max(0, (_liveZT[zone][team] || 0) - n);
  _refreshRI(zone);
}

function liveAdd(zone, team, n) {
  if (!_liveZT) return;
  if (!_liveZT[zone]) _liveZT[zone] = {};
  _liveZT[zone][team] = (_liveZT[zone][team] || 0) + n;
  _refreshRI(zone);
}

function _refreshRI(zone) {
  const code = ISLAND_CODES[zone];
  if (!code) return;
  const el = document.getElementById(`ri-${code}`);
  if (!el) return;
  const troops = _liveZT[zone] || {};
  const entries = Object.entries(troops).filter(([,n]) => n > 0).sort((a,b) => b[1]-a[1]);
  const total = entries.reduce((s,[,n]) => s + n, 0);
  const riTroops = el.querySelector('.ri-troops');
  if (riTroops) riTroops.textContent = total > 0 ? total + '⚔' : '';
  const riBreakdown = el.querySelector('.ri-breakdown');
  if (riBreakdown) {
    riBreakdown.innerHTML = entries.map(([t,n]) =>
      `<span style="color:${TEAM_COLORS[t]||'#888'}">${t}:${n}</span>`
    ).join(' ');
  }
}

/* Convert zone name to pixel center position within the map container */
function getIslandCenter(map, zone) {
  const pos = ISLAND_POSITIONS[zone];
  if (!pos) return null;
  return {
    x: map.offsetWidth  * pos.l / 100,
    y: map.offsetHeight * pos.t / 100,
  };
}

/* Boat element helpers */
const BW = 17, BH = 20; // half-dimensions for center-offset positioning

function _boatEmoji(kind) {
  if (kind === 'penalty') return '💣';
  if (kind === 'attack' || kind === 'union_attack') return '⚔️';
  if (kind === 'union') return '🛡';
  return '⛵';
}

function _makeBoat(map, ev, pos) {
  const color = TEAM_COLORS[ev.team] || '#888';
  const boat = document.createElement('div');
  boat.className = 'boat';
  boat.style.cssText = `left:${pos.x-BW}px;top:${pos.y-BH}px;background:${color}22;border-color:${color};color:${color};transition:none;`;
  boat.innerHTML = `<div class="boat-icon">${_boatEmoji(ev.kind)}</div><div class="boat-n">${ev.n}</div>`;
  map.appendChild(boat);
  return boat;
}

function _boatTo(boat, pos, dur = 0.8, ease = 'ease-in-out') {
  boat.style.transition = `left ${dur}s ${ease}, top ${dur}s ${ease}, opacity 0.3s`;
  boat.style.left = `${pos.x - BW}px`;
  boat.style.top  = `${pos.y - BH}px`;
}

/* Compute coalition ID from event (no backend change needed) */
function _coalitionId(ev) {
  if (!ev.allies || !ev.allies.length) return null;
  return [...ev.allies, ev.team].sort().join('_') + '__' + ev.to;
}

/* Single boat animation — deducts source immediately, optionally adds to dest */
function _animateSolo(map, ev, callback) {
  const src = getIslandCenter(map, ev.from);
  const tgt = getIslandCenter(map, ev.to);
  if (!src || !tgt) { callback(); return; }

  liveDeduct(ev.from, ev.team, ev.n);
  const boat = _makeBoat(map, ev, src);

  requestAnimationFrame(() => requestAnimationFrame(() => _boatTo(boat, tgt)));

  setTimeout(() => {
    if (ev.kind === 'penalty') {
      boat.querySelector('.boat-icon').textContent = '💀';
      boat.querySelector('.boat-n').textContent = '';
      boat.style.transition = 'opacity 0.5s';
      setTimeout(() => { boat.classList.add('fading'); setTimeout(() => { boat.remove(); callback(); }, 500); }, 400);
    } else {
      if (ev.kind === 'moving' || ev.kind === 'union') liveAdd(ev.to, ev.team, ev.n);
      boat.classList.add('fading');
      setTimeout(() => { boat.remove(); callback(); }, 350);
    }
  }, 880);
}

/* union_attack group animation: rally → sum popup → charge */
async function _animateGroup(map, boats) {
  if (boats.length === 1) {
    return new Promise(r => _animateSolo(map, boats[0], r));
  }

  const target = boats[0].to;
  const tgtPos = getIslandCenter(map, target);
  if (!tgtPos) return;

  const srcPosArr = boats.map(b => getIslandCenter(map, b.from)).filter(Boolean);
  const avgSrc = srcPosArr.reduce(
    (a, p) => ({x: a.x + p.x / srcPosArr.length, y: a.y + p.y / srcPosArr.length}),
    {x: 0, y: 0}
  );

  const dx = tgtPos.x - avgSrc.x, dy = tgtPos.y - avgSrc.y;
  const dist = Math.sqrt(dx*dx + dy*dy) || 1;
  const nx = dx/dist, ny = dy/dist;
  const px = -ny,    py =  nx;  // perpendicular

  const RALLY_OFFSET = Math.min(68, dist * 0.28);
  const rally = { x: tgtPos.x - nx * RALLY_OFFSET, y: tgtPos.y - ny * RALLY_OFFSET };

  // Phase 1: deduct sources, move boats to staggered rally positions
  const SPACING = 36;
  const boatEls = [];
  boats.forEach((ev, i) => {
    const src = getIslandCenter(map, ev.from);
    if (!src) return;

    liveDeduct(ev.from, ev.team, ev.n);

    const offset = (i - (boats.length - 1) / 2) * SPACING;
    const stagePos = { x: rally.x + px * offset, y: rally.y + py * offset };
    const el = _makeBoat(map, ev, src);

    setTimeout(() => requestAnimationFrame(() => requestAnimationFrame(() =>
      _boatTo(el, stagePos)
    )), i * 80);

    boatEls.push({ el, ev, stagePos });
  });

  await delay(920 + (boats.length - 1) * 80);

  // Phase 2: sum popup
  const totalN = boats.reduce((s, b) => s + b.n, 0);
  const parts = boats.map(b =>
    `<span style="color:${TEAM_COLORS[b.team]||'#888'}">+${b.n}</span>`
  ).join(' ');
  const popup = document.createElement('div');
  popup.className = 'union-sum-popup';
  popup.innerHTML = `${parts}<span class="sum-equals">= ${totalN}</span>`;
  popup.style.cssText = `left:${rally.x}px;top:${rally.y}px;`;
  map.appendChild(popup);
  await delay(40);
  popup.classList.add('show');
  await delay(950);
  popup.classList.remove('show');
  await delay(280);
  popup.remove();

  // Phase 3: charge to target
  boatEls.forEach(({ el }) => _boatTo(el, tgtPos, 0.5, 'ease-in'));
  await delay(560);
  boatEls.forEach(({ el }) => { el.classList.add('fading'); setTimeout(() => el.remove(), 350); });
}

async function playAnimations(events) {
  const map = document.getElementById('real-map');
  if (!map) return;
  const overlay = document.getElementById('anim-overlay');
  overlay.classList.add('show');

  startLiveState();

  const moves   = events.filter(e => e.type === 'move');
  const battles = events.filter(e => e.type === 'battle');

  // Separate union_attack coalitions (≥2 boats) from solo moves
  const groups = {};
  const solo   = [];
  for (const ev of moves) {
    const cid = _coalitionId(ev);
    if (cid) {
      (groups[cid] = groups[cid] || []).push(ev);
    } else {
      solo.push(ev);
    }
  }

  // Run solo moves (staggered) + coalition groups in parallel
  try {
    const soloPromises = solo.map((ev, i) =>
      new Promise(r => setTimeout(() => _animateSolo(map, ev, r), i * 100))
    );
    const groupPromises = Object.values(groups).map(g => _animateGroup(map, g));

    await Promise.all([...soloPromises, ...groupPromises]);
    await delay(200);

    for (const battle of battles) {
      await showBattleEffect(map, battle);
      await delay(300);
    }
  } finally {
    overlay.classList.remove('show');
  }
}

async function showBattleEffect(map, battle) {
  const center = getIslandCenter(map, battle.zone);
  if (!center) return;

  // Fight pulse ring
  const ring = document.createElement('div');
  ring.className = 'fight-pulse';
  ring.style.cssText = `left:${center.x}px;top:${center.y}px;`;
  map.appendChild(ring);

  // Fight emoji burst
  const effect = document.createElement('div');
  effect.className = 'fight-effect';
  effect.style.cssText = `left:${center.x}px;top:${center.y}px;`;
  effect.textContent = '⚔️';
  map.appendChild(effect);

  await delay(600);
  ring.remove();
  effect.remove();

  // Winner announcement
  const winnerTeam = battle.winner_teams[0];
  const winnerColor = TEAM_COLORS[winnerTeam] || '#888';
  const code = ISLAND_CODES[battle.zone] || battle.zone;
  const announce = document.createElement('div');
  announce.className = 'winner-announce';
  announce.style.cssText = `left:${center.x}px;top:${center.y - 55}px;color:${winnerColor};border-color:${winnerColor};`;
  announce.innerHTML = `
    <div class="announce-zone">${code} ${battle.zone}</div>
    <div class="announce-winner">隊 ${battle.winner_teams.join('+')} 勝利！</div>
    <div class="announce-detail">+${battle.bonus} 獎勵 | 敗方：隊${battle.loser_teams.join(',')}</div>
  `;
  map.appendChild(announce);

  await delay(1800);
  announce.classList.add('fading');
  await delay(400);
  announce.remove();
}

function delay(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

/* ── Exec modal ──────────────────────────────────────────────────────────── */
function showExecModal(log) {
  const listEl = document.getElementById('exec-log-list');
  listEl.innerHTML = '';
  (log || []).forEach(line => {
    const div = document.createElement('div');
    let cls = '';
    if (line.startsWith('[戰鬥]')) cls = 'log-battle';
    else if (line.startsWith('[國力]')) cls = 'log-power';
    else if (line.startsWith('[中立]') || line.startsWith('[救濟]')) cls = 'log-neutral';
    else if (line.startsWith('[迷霧') || line.startsWith('[金錢') || line.startsWith('[漩渦')) cls = 'log-resource';
    else if (line.startsWith('[衝突') || line.startsWith('[懲罰')) cls = 'log-penalty';
    else if (line.startsWith('[管理員]')) cls = 'log-admin';
    div.className = cls;
    div.textContent = line;
    listEl.appendChild(div);
  });
  document.getElementById('exec-overlay').classList.add('show');
}

function closeExecModal(e) {
  if (e && e.target !== document.getElementById('exec-overlay')) return;
  document.getElementById('exec-overlay').classList.remove('show');
}

/* ── Undo ────────────────────────────────────────────────────────────────── */
async function undoRound() {
  if (!confirm('回到上一回合？這將撤銷已執行的結算。')) return;
  const res = await fetch('/api/undo', {method:'POST'});
  const data = await res.json();
  if (data.error) { alert(data.error); return; }
  document.getElementById('btn-redo').disabled = !data.can_redo;
  applyState(data.state, {}, []);
  await fetchState();
}

/* ── Redo ────────────────────────────────────────────────────────────────── */
async function redoRound() {
  const res = await fetch('/api/redo', {method:'POST'});
  const data = await res.json();
  if (data.error) { alert(data.error); return; }
  document.getElementById('btn-undo').disabled = !data.can_undo;
  document.getElementById('btn-redo').disabled = !data.can_redo;
  applyState(data.state, {}, []);
  await fetchState();
}

/* ── Command templates ───────────────────────────────────────────────────── */
function insertTemplate(text) {
  const ta = document.getElementById('cmd-textarea');
  const start = ta.selectionStart;
  const end = ta.selectionEnd;
  const before = ta.value.slice(0, start);
  const after = ta.value.slice(end);
  // Insert on a new line if there's already content
  const prefix = (before && !before.endsWith('\n')) ? '\n' : '';
  ta.value = before + prefix + text + after;
  const cursor = before.length + prefix.length + text.length;
  ta.selectionStart = ta.selectionEnd = cursor;
  ta.focus();
}

/* ── Per-command edit / delete ───────────────────────────────────────────── */
async function deleteCmd(team, rawText) {
  // Get current raw lines for this team, filter out the deleted one
  const cmds = validatedCommands[team] || [];
  const remaining = cmds
    .map(c => c.raw)
    .filter(r => r !== rawText)
    .join('\n');

  const res = await fetch(`/api/commands/${team}`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({text: remaining}),
  });
  const data = await res.json();
  if (data.error) { alert(data.error); return; }
  validatedCommands = data.validated_commands || {};
  renderCommandLog();
  updateCmdCountHint();
}

async function editCmd(team, _rawText) {
  // Collect ALL commands for this team, put them in the textarea, then clear the log
  const cmds = validatedCommands[team] || [];
  const allText = cmds.map(c => c.raw).join('\n');

  const sel = document.getElementById('team-select');
  sel.value = team;
  selectedTeam = team;
  updateCmdCountHint();
  document.getElementById('cmd-textarea').value = allText;

  // Clear the team's commands from the log
  const res = await fetch(`/api/commands/${team}`, {method:'DELETE'});
  const data = await res.json();
  if (data.error) { alert(data.error); return; }
  validatedCommands = data.validated_commands || {};
  renderCommandLog();
  updateCmdCountHint();
  document.getElementById('cmd-textarea').focus();
}

/* ── Settlement screen ───────────────────────────────────────────────────── */
function openSettlement() {
  if (!gameState) return;
  const np = gameState.national_power || {};
  const teams = gameState.teams || [];
  const sorted = [...teams].sort((a, b) => (np[b] || 0) - (np[a] || 0));

  const MEDALS = ['🥇', '🥈', '🥉'];
  const list = document.getElementById('settlement-list');
  list.innerHTML = '';

  sorted.forEach((team, i) => {
    const power = np[team] || 0;
    const troops = Object.values(gameState.zones || {})
      .reduce((s, z) => s + ((z.troops || {})[team] || 0), 0);
    const zoneCount = Object.values(gameState.zones || {})
      .filter(z => z.owner === team).length;
    const color = TEAM_COLORS[team] || '#888';
    const medal = i < 3 ? MEDALS[i] : `${i + 1}`;

    const row = document.createElement('div');
    row.className = `settle-row${i < 3 ? ` rank-${i + 1}` : ''}`;
    row.innerHTML = `
      <div class="settle-rank">${medal}</div>
      <div class="settle-dot" style="background:${color}"></div>
      <div class="settle-name" style="color:${color}">隊 ${team}</div>
      <div class="settle-stat">${zoneCount} 領地</div>
      <div class="settle-stat">${troops}<span style="font-size:9px">⚔</span></div>
      <div class="settle-power">${power}<span style="font-size:10px;opacity:.7">💎</span></div>
    `;
    list.appendChild(row);
  });

  document.getElementById('settlement-overlay').classList.add('show');
}

function closeSettlement() {
  document.getElementById('settlement-overlay').classList.remove('show');
}

/* ── Confirm reset ───────────────────────────────────────────────────────── */
function confirmReset() {
  if (!confirm('確定要重新設定？目前的對局進度將結束。')) return;
  closeSettlement();
  openSetupWithPrefill();
}

function openSetupWithPrefill() {
  if (_initialSetupData) {
    // Restore team checkboxes
    document.querySelectorAll('#team-checkboxes input[type=checkbox]').forEach(cb => {
      const checked = _initialSetupData.teams.includes(cb.dataset.team);
      cb.checked = checked;
      cb.closest('label').classList.toggle('checked', checked);
    });
    // Restore round count
    document.getElementById('setup-rounds').value = _initialSetupData.max_rounds;
    // Restore territory inputs
    document.querySelectorAll('[data-zone-team]').forEach(sel => {
      const zone = sel.dataset.zoneTeam;
      const d = _initialSetupData.zoneData?.[zone] || {};
      sel.value = d.team || '';
      const nInp = document.querySelector(`[data-zone-n="${zone}"]`);
      if (nInp) nInp.value = d.n || '';
    });
    // Restore troop inputs
    document.querySelectorAll('[data-troop-team]').forEach(inp => {
      inp.value = _initialSetupData.troopTexts[inp.dataset.troopTeam] || '0';
    });
  }
  openSetup();
}

/* ── Quick init ──────────────────────────────────────────────────────────── */

// 測試用一鍵初始化: 4 teams, pre-set territories and troops for quick testing
function testInit() {
  // Set rounds to 3
  document.getElementById('setup-rounds').value = 3;

  // Check all 10 teams
  document.querySelectorAll('#team-checkboxes input[type=checkbox]').forEach(cb => {
    cb.checked = true;
    cb.closest('label').classList.add('checked');
  });

  // Clear all territory inputs
  document.querySelectorAll('[data-zone-team]').forEach(sel => { sel.value = ''; });
  document.querySelectorAll('[data-zone-n]').forEach(inp => { inp.value = ''; });

  // Set initial territories for teams 1–4 only
  const territories = {
    '人類王國': {team: '1', n: '500'},
    '精靈森域': {team: '2', n: '400'},
    '龍族火山': {team: '3', n: '300'},
    '獸人荒原': {team: '4', n: '200'},
  };
  Object.entries(territories).forEach(([zone, d]) => {
    const sel = document.querySelector(`[data-zone-team="${zone}"]`);
    const nInp = document.querySelector(`[data-zone-n="${zone}"]`);
    if (sel) sel.value = d.team;
    if (nInp) nInp.value = d.n;
  });

  // Set init troops for all 10 teams
  const troops = {'1':300,'2':250,'3':200,'4':150};
  document.querySelectorAll('[data-troop-team]').forEach(inp => {
    inp.value = troops[inp.dataset.troopTeam] || 0;
  });
}

// 一鍵初始化: all 10 teams × all islands + neutral island each get n troops
function uniformInit() {
  const n = parseInt(document.getElementById('uniform-init-n').value) || 0;
  if (n <= 0) { alert('請輸入正整數 n'); return; }

  // Check all 10 teams first
  document.querySelectorAll('#team-checkboxes input[type=checkbox]').forEach(cb => {
    cb.checked = true;
    cb.closest('label').classList.add('checked');
  });

  // All teams
  const activeTeams = ALL_TEAMS.slice();

  // Distribute 12 territories round-robin among 10 teams with n troops each
  document.querySelectorAll('[data-zone-team]').forEach((sel, i) => {
    sel.value = ALL_TEAMS[i % ALL_TEAMS.length];
  });
  document.querySelectorAll('[data-zone-n]').forEach(inp => { inp.value = n; });

  // Set init troops (neutral island) for all 10 teams
  document.querySelectorAll('[data-troop-team]').forEach(inp => { inp.value = n; });
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function escHtml(s) {
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
