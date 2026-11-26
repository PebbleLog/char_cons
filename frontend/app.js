/* ============================================================
   Character Consistency Studio · UI prototype interactions
   All analysis and generation states are simulated locally.
   ============================================================ */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const DEMO_SHOTS = [
  {
    id: 'S1',
    image: 'assets/shot-1.jpg',
    file: 'alan_shot_01.png',
    quality: 'ok',
    qualityLabel: '可用 · 正面半身',
    note: '咖啡馆正面半身，吊坠完整可见',
  },
  {
    id: 'S2',
    image: 'assets/shot-2.jpg',
    file: 'alan_shot_02.png',
    quality: 'warn',
    qualityLabel: '可用 · 侧身半身',
    note: '窗边侧身，外套受冷光影响',
  },
  {
    id: 'S3',
    image: 'assets/shot-3.jpg',
    file: 'alan_shot_03.png',
    quality: 'ok',
    qualityLabel: '可用 · 正面半身',
    note: '桌面正面半身，吊坠细节清晰',
  },
];

const OBSERVATIONS = {
  S1: [
    { name: '发型', observed: '低侧发髻', visibility: '完整可见', evidence: '深棕长发在右后侧挽成低髻，侧分刘海轮廓清晰', verdict: 'consistent' },
    { name: '发色', observed: '深棕', visibility: '完整可见', evidence: '发丝呈深棕色，与设定一致', verdict: 'consistent' },
    { name: '上装款式', observed: '亚麻西装外套', visibility: '完整可见', evidence: '翻领亚麻西装，版型与设定一致', verdict: 'consistent' },
    { name: '上装颜色', observed: '浅米色', visibility: '完整可见', evidence: '外套主体为浅暖米色', verdict: 'consistent' },
    { name: '上装图案', observed: '纯色', visibility: '完整可见', evidence: '外套为纯色亚麻织物，未见图案；设定未定义，仅记录', verdict: 'neutral' },
    { name: '下装款式', observed: null, visibility: '不可见', evidence: '画面仅至胸口，下装未入画', verdict: 'unknown' },
    { name: '下装颜色', observed: null, visibility: '不可见', evidence: '画面仅至胸口，无法判断下装颜色', verdict: 'unknown' },
    { name: '下装图案', observed: null, visibility: '不可见', evidence: '画面仅至胸口，无法判断下装图案', verdict: 'unknown' },
    { name: '配饰', observed: '蓝紫四瓣吊坠', visibility: '完整可见', evidence: '圆形吊坠项链完整可见，内部为蓝紫四瓣花', verdict: 'consistent' },
    { name: '鞋履', observed: null, visibility: '不可见', evidence: '画面仅至胸口，鞋履未入画', verdict: 'unknown' },
    { name: '道具', observed: '咖啡杯', visibility: '完整可见', evidence: '画面下方可见咖啡杯；设定未定义，仅记录', verdict: 'neutral' },
  ],
  S2: [
    { name: '发型', observed: '低侧发髻', visibility: '完整可见', evidence: '低侧发髻轮廓与 S1 一致', verdict: 'consistent' },
    { name: '发色', observed: '深棕', visibility: '完整可见', evidence: '发色仍为深棕，与 S1 一致', verdict: 'consistent' },
    { name: '上装款式', observed: '亚麻西装外套', visibility: '完整可见', evidence: '侧身仍可辨认同一翻领亚麻西装', verdict: 'consistent' },
    { name: '上装颜色', observed: '冷灰米色', visibility: '完整可见', evidence: '外套在窗边冷光下明显偏冷灰，暖调不足，与 S1/S3 的浅暖米色不一致', verdict: 'inconsistent' },
    { name: '上装图案', observed: '纯色', visibility: '完整可见', evidence: '外套仍为纯色织物，未出现图案；设定未定义，仅记录', verdict: 'neutral' },
    { name: '下装款式', observed: null, visibility: '不可见', evidence: '画面仅至腰部，下装未入画', verdict: 'unknown' },
    { name: '下装颜色', observed: null, visibility: '不可见', evidence: '画面仅至腰部，无法判断下装颜色', verdict: 'unknown' },
    { name: '下装图案', observed: null, visibility: '不可见', evidence: '画面仅至腰部，无法判断下装图案', verdict: 'unknown' },
    { name: '配饰', observed: null, visibility: '角度遮挡', evidence: '侧身角度下胸前被衣领遮挡，无法确认项链是否存在', verdict: 'unknown' },
    { name: '鞋履', observed: null, visibility: '不可见', evidence: '画面仅至腰部，鞋履未入画', verdict: 'unknown' },
    { name: '道具', observed: null, visibility: '不可见', evidence: '画面未包含道具；设定未定义，无法判断', verdict: 'unknown' },
  ],
  S3: [
    { name: '发型', observed: '低侧发髻', visibility: '完整可见', evidence: '低侧发髻轮廓与 S1 一致', verdict: 'consistent' },
    { name: '发色', observed: '深棕', visibility: '完整可见', evidence: '头顶与发髻部分可见，发色为深棕', verdict: 'consistent' },
    { name: '上装款式', observed: '亚麻西装外套', visibility: '完整可见', evidence: '翻领亚麻西装，与设定一致', verdict: 'consistent' },
    { name: '上装颜色', observed: '浅米色', visibility: '完整可见', evidence: '外套主体为浅暖米色，与 S1 一致', verdict: 'consistent' },
    { name: '上装图案', observed: '纯色', visibility: '完整可见', evidence: '外套为纯色亚麻织物，未见图案；设定未定义，仅记录', verdict: 'neutral' },
    { name: '下装款式', observed: null, visibility: '不可见', evidence: '下半身被桌沿遮挡', verdict: 'unknown' },
    { name: '下装颜色', observed: null, visibility: '不可见', evidence: '下半身被桌沿遮挡，无法判断下装颜色', verdict: 'unknown' },
    { name: '下装图案', observed: null, visibility: '不可见', evidence: '下半身被桌沿遮挡，无法判断下装图案', verdict: 'unknown' },
    { name: '配饰', observed: '红橙五瓣吊坠', visibility: '完整可见', evidence: '吊坠轮廓与 S1 相同，但内部图案为红橙五瓣花，与设定的蓝紫四瓣不符', verdict: 'inconsistent' },
    { name: '鞋履', observed: null, visibility: '不可见', evidence: '下半身被桌沿遮挡，鞋履未入画', verdict: 'unknown' },
    { name: '道具', observed: '咖啡杯', visibility: '完整可见', evidence: '画面下方可见咖啡杯；设定未定义，仅记录', verdict: 'neutral' },
  ],
};

const STATE = {
  screen: 'home',
  shots: [],
  attributes: [],
  issues: [],
  unknowns: [],
  selectedShot: null,
  selectedIssue: null,
  resultTab: 'matrix',
  galleryFilter: 'all',
  historyFilter: 'all',
  analysis: {
    started: false,
    complete: false,
    phase: 'idle',
    timers: [],
    current: 0,
    viewIndex: 0,
    progress: 0,
    stage: 0,
    statuses: [],
    observedCounts: [],
    verdictCounts: {},
    issueCount: 0,
    unknownCount: 0,
    taskName: '',
    characterName: '',
    realMode: false,
    modeNote: '演示视图',
    stageName: '',
    stageNames: null,
    etaSeconds: null,
    suggestionReady: 0,
    suggestionTotal: 0,
    startedAt: null,
    endedAt: null,
    connectionLost: false,
    shotErrors: {},
    subjects: {},
  },
  opt: {
    shot: 'S3',
    selected: null,
    status: 'complete',
    /* Per-shot adoption: shotId -> adopted candidateId. Switching shots never
       clears another shot's adopted state. */
    adopted: {},
    precheck: 'done',
  },
  batch: 4,
};

const OPTIMIZER_DATA = {
  S3: {
    issueId: 'ISS-002',
    title: '优化 S3 · 本镜头 1 个问题',
    subtitle: '把红橙五瓣吊坠修回设定中的蓝紫四瓣花，并保留低侧发髻与浅米色外套。',
    contextTitle: 'ISS-002 · S3 · 配饰',
    contextCopy: '设定期望：蓝紫四瓣花吊坠 / 实际观察：红橙五瓣花吊坠 / 吊坠轮廓一致，图案不符，置信度高。',
    prompt: '阿岚，深棕长发低侧发髻（与 S1 一致），浅米色亚麻西装外套，黑色丝质衬衫，紫色口袋巾，圆形吊坠项链（蓝紫四瓣花，与 S1 相同），正面半身，暖调咖啡馆光线，保持与 S1 相同的角色特征与配饰细节。',
    negative: '红橙吊坠，五瓣花，星形吊坠，项链缺失，短发，高马尾，围巾，冷灰外套，大图案。',
    keypoints: ['锁定圆形吊坠与蓝紫四瓣花图案', '引用 S1 作为配饰参考', '保留低侧发髻与浅米色外套'],
    cardplan: '每批 4 张 · 参考 S1 · 优先还原吊坠图案',
    diff: '吊坠图案：红橙五瓣 → 蓝紫四瓣',
    candidates: [
      {
        id: 'C-001', img: 'assets/candidate-3-1.jpg', fullImg: 'assets/shot-3-corrected.jpg',
        overall: 'pass', label: '建议采用', state: '预检通过',
        summary: '吊坠图案与 S1 一致',
        checks: [
          { name: '吊坠为蓝紫四瓣花', pass: true, evidence: '吊坠内部图案已恢复为蓝紫四瓣。' },
          { name: '项链位置与链长一致', pass: true, evidence: '圆形吊坠位置、链长与 S1 接近。' },
          { name: '构图与相邻镜头连贯', pass: true, evidence: '正面半身景别与 S1 / S3 接近。' },
        ],
      },
      {
        id: 'C-002', img: 'assets/shot-3-close.jpg', overall: 'fail', label: '不建议', state: '未通过',
        summary: '吊坠仍为红橙五瓣',
        checks: [
          { name: '吊坠为蓝紫四瓣花', pass: false, evidence: '吊坠内部仍为红橙五瓣花，图案未修正。' },
          { name: '项链位置与链长一致', pass: true, evidence: '圆形吊坠位置、链长接近。' },
          { name: '构图与相邻镜头连贯', pass: true, evidence: '正面半身景别一致。' },
        ],
      },
      {
        id: 'C-003', img: 'assets/candidate-3-3.jpg', overall: 'partial', label: '部分符合', state: '部分符合',
        summary: '图案正确，构图偏紧',
        checks: [
          { name: '吊坠为蓝紫四瓣花', pass: true, evidence: '吊坠已恢复蓝紫四瓣图案。' },
          { name: '项链位置与链长一致', pass: true, evidence: '圆形吊坠位置、链长接近。' },
          { name: '构图与相邻镜头连贯', pass: null, evidence: '景别偏紧，需人工确认。' },
        ],
      },
      {
        id: 'C-004', img: 'assets/candidate-3-4.jpg', overall: 'unknown', label: '预检失败', state: '无结论',
        summary: '吊坠细节模糊',
        precheckFailed: true,
        checks: [],
      },
    ],
  },
  S2: {
    issueId: 'ISS-001',
    title: '优化 S2 · 本镜头 1 个问题',
    subtitle: '把冷灰米色外套调回设定中的浅暖米色，并保留低侧发髻与紫色口袋巾。',
    contextTitle: 'ISS-001 · S2 · 上装颜色',
    contextCopy: '设定期望：浅米色（暖调） / 实际观察：冷灰米色 / 色差完整可见，置信度高。',
    prompt: '阿岚，深棕长发低侧发髻（与 S1 一致），浅暖米色亚麻西装外套（与 S1 相同），黑色丝质衬衫，紫色口袋巾，圆形吊坠项链（蓝紫四瓣花），窗边半身，暖调自然光，保持与 S1 相同的角色特征与服装颜色。',
    negative: '冷灰外套，灰白西装，冷光，蓝色滤镜，短发，高马尾，无口袋巾，围巾，大图案。',
    keypoints: ['锁定外套为浅暖米色', '引用 S1 校准主色与色温', '保留低侧发髻与紫色口袋巾'],
    cardplan: '每批 4 张 · 参考 S1 · 优先校准外套主色与色温',
    diff: '外套主色：冷灰米色 → 浅暖米色',
    candidates: [
      {
        id: 'C-001', img: 'assets/candidate-2-1.jpg', fullImg: 'assets/shot-2-corrected.jpg',
        overall: 'pass', label: '建议采用', state: '预检通过',
        summary: '外套恢复浅暖米色',
        checks: [
          { name: '外套主色为浅暖米色', pass: true, evidence: '外套呈浅暖米色，与 S1 接近。' },
          { name: '发型轮廓与 S1 一致', pass: true, evidence: '低侧发髻轮廓接近。' },
          { name: '构图与相邻镜头连贯', pass: true, evidence: '侧身半身景别保持不变。' },
        ],
      },
      {
        id: 'C-002', img: 'assets/shot-2-close.jpg', overall: 'fail', label: '不建议', state: '未通过',
        summary: '外套仍偏冷灰',
        checks: [
          { name: '外套主色为浅暖米色', pass: false, evidence: '外套仍呈冷灰米色，色温未修正。' },
          { name: '发型轮廓与 S1 一致', pass: true, evidence: '低侧发髻轮廓接近。' },
          { name: '构图与相邻镜头连贯', pass: true, evidence: '侧身半身景别保持不变。' },
        ],
      },
      {
        id: 'C-003', img: 'assets/candidate-2-3.jpg', overall: 'partial', label: '部分符合', state: '部分符合',
        summary: '颜色正确，构图变化',
        checks: [
          { name: '外套主色为浅暖米色', pass: true, evidence: '外套已恢复浅暖米色。' },
          { name: '发型轮廓与 S1 一致', pass: true, evidence: '低侧发髻轮廓接近。' },
          { name: '构图与相邻镜头连贯', pass: null, evidence: '景别更近，背景占比变化，需人工确认。' },
        ],
      },
      {
        id: 'C-004', img: 'assets/candidate-2-4-close.jpg', overall: 'unknown', label: '预检失败', state: '无结论',
        summary: '画面模糊',
        precheckFailed: true,
        checks: [],
      },
    ],
  },
};

const MATRIX = [
  { key: '发型', code: 'hair_style', expected: '低侧发髻', cells: {
    S1: { status: 'ok', value: '低侧发髻' }, S2: { status: 'ok', value: '低侧发髻' }, S3: { status: 'ok', value: '低侧发髻' },
  } },
  { key: '发色', code: 'hair_color', expected: '深棕', cells: {
    S1: { status: 'ok', value: '深棕' }, S2: { status: 'ok', value: '深棕' }, S3: { status: 'ok', value: '深棕' },
  } },
  { key: '上装款式', code: 'top_style', expected: '亚麻西装外套', cells: {
    S1: { status: 'ok', value: '亚麻西装外套' }, S2: { status: 'ok', value: '亚麻西装外套', note: '侧身' }, S3: { status: 'ok', value: '亚麻西装外套' },
  } },
  { key: '上装颜色', code: 'top_color', expected: '浅米色', cells: {
    S1: { status: 'ok', value: '浅米色' }, S2: { status: 'alert', value: '冷灰米色', issue: 'ISS-001' }, S3: { status: 'ok', value: '浅米色' },
  } },
  { key: '上装图案', code: 'top_pattern', expected: '设定未定义', cells: {
    S1: { status: 'observed', value: '纯色' }, S2: { status: 'observed', value: '纯色' }, S3: { status: 'observed', value: '纯色' },
  } },
  { key: '下装款式', code: 'bottom_style', expected: '设定未定义', cells: {
    S1: { status: 'muted', value: '未入画', note: 'UNK-001' }, S2: { status: 'muted', value: '未入画', note: 'UNK-002' }, S3: { status: 'muted', value: '被遮挡', note: 'UNK-004' },
  } },
  { key: '下装颜色', code: 'bottom_color', expected: '设定未定义', cells: {
    S1: { status: 'muted', value: '未入画', note: 'UNK-005' }, S2: { status: 'muted', value: '未入画', note: 'UNK-006' }, S3: { status: 'muted', value: '被遮挡', note: 'UNK-007' },
  } },
  { key: '下装图案', code: 'bottom_pattern', expected: '设定未定义', cells: {
    S1: { status: 'muted', value: '未入画', note: 'UNK-011' }, S2: { status: 'muted', value: '未入画', note: 'UNK-012' }, S3: { status: 'muted', value: '被遮挡', note: 'UNK-013' },
  } },
  { key: '配饰', code: 'accessories', expected: '圆形吊坠项链', cells: {
    S1: { status: 'ok', value: '蓝紫四瓣吊坠' }, S2: { status: 'muted', value: '不可见', note: '角度遮挡' }, S3: { status: 'alert', value: '红橙五瓣吊坠', issue: 'ISS-002' },
  } },
  { key: '鞋履', code: 'shoes', expected: '设定未定义', cells: {
    S1: { status: 'muted', value: '未入画', note: 'UNK-008' }, S2: { status: 'muted', value: '未入画', note: 'UNK-009' }, S3: { status: 'muted', value: '被遮挡', note: 'UNK-010' },
  } },
  { key: '道具', code: 'props', expected: '设定未定义', cells: {
    S1: { status: 'observed', value: '咖啡杯' }, S2: { status: 'muted', value: '—', note: 'UNK-014' }, S3: { status: 'observed', value: '咖啡杯' },
  } },
];

const DEMO_ISSUES = JSON.parse(JSON.stringify(STATE.issues));
const DEMO_UNKNOWNS = JSON.parse(JSON.stringify(STATE.unknowns));
const MATRIX_ORIGINAL = JSON.parse(JSON.stringify(MATRIX));

function resetDemoData() {
  STATE.shots = DEMO_SHOTS.map((s) => ({ ...s }));
  STATE.issues = JSON.parse(JSON.stringify(DEMO_ISSUES));
  STATE.unknowns = JSON.parse(JSON.stringify(DEMO_UNKNOWNS));
  STATE.selectedShot = 'S3';
  STATE.selectedIssue = 'ISS-002';
  STATE.resultTab = 'matrix';
  STATE.galleryFilter = 'all';
  STATE.analysis = {
    started: false, complete: false, phase: 'idle', timers: [], current: 0, viewIndex: 0,
    progress: 0, stage: 0,
    statuses: STATE.shots.map(() => 'pending'),
    observedCounts: STATE.shots.map(() => 0),
    verdictCounts: {}, issueCount: 0, unknownCount: 0,
    taskName: '', characterName: '', realMode: false, modeNote: '演示视图',
    stageName: '', stageNames: null, etaSeconds: null,
    suggestionReady: 0, suggestionTotal: 0,
    startedAt: null, endedAt: null, connectionLost: false,
    shotErrors: {}, subjects: {},
  };
  STATE.opt = { shot: 'S3', selected: null, status: 'complete', adopted: {}, precheck: 'done' };
  MATRIX.forEach((row, i) => { row.cells = JSON.parse(JSON.stringify(MATRIX_ORIGINAL[i].cells)); });
}

const SUGGESTIONS = [
  {
    id: 'SUG-001', issueId: 'ISS-001', shot: 'S2', title: '校准外套主色与色温',
    prompt: OPTIMIZER_DATA.S2.prompt,
    refs: '参考 S1',
  },
  {
    id: 'SUG-002', issueId: 'ISS-002', shot: 'S3', title: '还原蓝紫四瓣吊坠',
    prompt: OPTIMIZER_DATA.S3.prompt,
    refs: '参考 S1',
  },
];

const ANALYSIS_STAGES = [
  { name: '素材校验', hint: '正在检查镜头素材的格式、清晰度与可用性' },
  { name: '设定解析', hint: '正在提取角色设定中的固定外观要素' },
  { name: '剧本解析', hint: '正在核对镜头说明与允许的局部变化' },
  { name: '逐镜头观察', hint: '正在逐镜头观察角色的固定外观要素' },
  { name: '一致性判定', hint: '正在比对设定并记录不一致项' },
  { name: '生成建议', hint: '正在为不一致项整理修正提示词与抽卡方案' },
];

/* ---------------- utilities ---------------- */

function icon(name, cls = '') {
  return `<svg class="icon ${cls}"><use href="#i-${name}"/></svg>`;
}

function statusIcon(status, name) {
  const map = {
    ok: ['is-ok', 'check'], alert: ['is-alert', 'alert'], muted: ['is-muted', 'help'],
    info: ['is-info', 'info'], warn: ['is-warn', 'alert'], live: ['is-info', 'refresh'],
    issue: ['is-alert', 'alert'], consistent: ['is-ok', 'check'], inconsistent: ['is-alert', 'alert'],
    unknown: ['is-muted', 'help'], observed: ['is-muted', 'minus'],
  };
  const [cls, ic] = map[status] || map.info;
  return `<span class="status-icon ${cls}">${icon(ic || name || 'info')}</span>`;
}

function pill(text, kind = 'neutral', dot = true) {
  return `<span class="status-pill is-${kind}">${dot ? '<i></i>' : ''}${text}</span>`;
}

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (s) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s]));
}

let toastTimer;
function toast(message) {
  const el = $('#toast');
  $('#toast-text').textContent = message;
  el.classList.add('is-visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('is-visible'), 2600);
}

function copyText(text, message = '已复制到剪贴板') {
  const done = () => toast(message);
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
  } else {
    fallbackCopy(text, done);
  }
}
function fallbackCopy(text, done) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); done(); } catch { toast('复制失败，请手动选择文本'); }
  document.body.removeChild(ta);
}

function downloadFile(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 600);
}

function currentDateStamp() {
  return new Date().toISOString().slice(0, 16).replace('T', ' ');
}

/* ---------------- navigation ---------------- */

const SCREEN_META = {
  home: { title: '工作台', eyebrow: 'WORKSPACE', sub: '检查角色在连续镜头中的形象一致性' },
  create: { title: '新建检测任务', eyebrow: 'TASK / NEW', sub: '录入角色设定、剧本说明与连续镜头' },
  analysis: { title: '检测任务', eyebrow: 'TASK / ANALYZING', sub: '逐镜头观察、判定并建立证据链' },
  results: { title: '检测结果', eyebrow: 'REPORT / 001', sub: '阿岚 · 第一幕 · 3 个镜头' },
  optimizer: { title: '优化提示词', eyebrow: 'OPTIMIZER / S3', sub: '修正提示词、生成候选图并按标准预检' },
  history: { title: '历史报告', eyebrow: 'LIBRARY / REPORTS', sub: '本地保存的检测任务与报告' },
  settings: { title: '设置', eyebrow: 'SETTINGS / LOCAL', sub: '服务连接、生成参数与本地数据' },
};

function setPageEyebrow(text) {
  const el = $('#page-eyebrow');
  if (!el) return;
  const [root, node] = text.split(' / ');
  el.setAttribute('aria-label', text);
  el.innerHTML = node
    ? `<span class="eb-root">${root}</span><span class="eb-sep" aria-hidden="true"></span><span class="eb-node">${node}</span>`
    : `<span class="eb-root">${root}</span>`;
}

function playHeaderIn() {
  const el = $('#topbar-title');
  if (!el) return;
  el.classList.remove('is-enter');
  void el.offsetWidth;
  el.classList.add('is-enter');
}

/* 分析页会把镜头换成服务端模型（没有本地文件）；刷新后回到新建页时清掉这些
   无法再次提交的镜头，避免界面显示图片、开始检查却提示“没有真实图片”。 */
function pruneServerShots() {
  const stale = (shot) => shot.shotId && !shot.nativeFile;
  if (!STATE.shots.some(stale)) return;
  STATE.shots = STATE.shots.filter((shot) => !stale(shot));
  STATE.shots.forEach((shot, index) => { shot.id = `S${index + 1}`; });
  renderShots();
  updateCreateValidation();
}

function showScreen(name) {
  if (!SCREEN_META[name]) return;
  if (name === 'create') pruneServerShots();
  STATE.screen = name;
  $$('.screen').forEach((s) => s.classList.toggle('is-active', s.id === `screen-${name}`));
  const navKey = name === 'results' || name === 'optimizer' ? 'analysis' : name;
  $$('.nav-item[data-nav]').forEach((b) => b.classList.toggle('is-active', b.dataset.nav === navKey));
  const meta = SCREEN_META[name];
  // 页面可把自己的副标题写回 data-subtitle（如真实报告的任务名与镜头数），
  // 优先生效；没有动态值时退回导航配置里的默认文案。
  const screenEl = document.getElementById(`screen-${name}`);
  $('#page-title').textContent = meta.title;
  setPageEyebrow(meta.eyebrow);
  $('#page-subtitle').textContent = screenEl?.dataset.subtitle || meta.sub;
  playHeaderIn();
  updateTopbarStatus(name);
  if (window.location.hash !== `#${name}`) {
    try { history.replaceState(null, '', `#${name}`); } catch { window.location.hash = name; }
  }
  $('#notify-popover').hidden = true;
  $('#notify-btn').setAttribute('aria-expanded', 'false');
  window.scrollTo({ top: 0, behavior: 'auto' });
  if (name === 'results') renderResults();
  if (name === 'optimizer') renderOptimizer();
  if (name === 'analysis') renderAnalysisScreen();
  if (name === 'history') filterHistory();
}

function updateTopbarStatus(name) {
  const el = $('#task-status-pill');
  el.hidden = false;
  el.className = 'status-pill is-idle';
  if (name === 'analysis') {
    const [cls, text] = analysisPhasePill();
    setStatusPill(el, cls, text);
    const chip = $('#current-task-name');
    if (chip && STATE.analysis.taskName && chip.textContent !== STATE.analysis.taskName) {
      chip.textContent = STATE.analysis.taskName;
    }
  } else if (name === 'results') {
    el.className = 'status-pill is-ok';
    el.innerHTML = '<i></i>已完成';
  } else if (name === 'optimizer') {
    el.className = 'status-pill is-live';
    el.innerHTML = `<i></i>${adoptedCandidateId() ? '已采用' : '优化中'}`;
  } else if (name === 'settings') {
    el.className = 'status-pill is-neutral';
    el.innerHTML = '<i></i>单机模式';
  } else {
    // 工作台、新建任务、历史报告等页面不显示任务状态标签
    el.hidden = true;
    el.innerHTML = '';
  }
}

function navigate(name) {
  if (name === 'analysis') {
    if (STATE.analysis.complete) { showScreen('results'); return; }
    if (STATE.analysis.realMode) { showScreen('analysis'); return; }
    if (!STATE.shots.length) { showScreen('analysis'); return; }
    showScreen('analysis');
    if (!STATE.analysis.started) startAnalysis();
    return;
  }
  if (name === 'results') {
    if (!STATE.analysis.complete && STATE.analysis.started) {
      /* allow preview of the built-in demo report */
    }
  }
  showScreen(name);
}

/* ---------------- create screen ---------------- */

function parseCharacter(text) {
  const attrs = [];
  const nameMatch = text.match(/^\s*([^，,。\s]{1,12})[，,]/);
  const name = nameMatch ? nameMatch[1] : (text.trim() ? '阿岚' : '未命名');

  const colors = [
    '浅米色', '米色', '米白', '杏色', '香槟色', '黄色', '金黄', '金色',
    '浅蓝色', '蓝色', '深蓝色', '深蓝', '藏青', '天蓝', '牛仔蓝', '雾霾蓝',
    '浅粉色', '浅粉', '粉色', '红色', '酒红色', '酒红', '橙色',
    '黑色', '白色', '浅灰色', '浅灰', '灰色', '深灰色', '深灰', '银灰', '银白',
    '绿色', '墨绿', '军绿', '紫色', '浅紫', '棕色', '深棕色', '深棕', '浅棕色',
    '栗色', '咖啡色', '巧克力色', '卡其色',
  ];
  /* 颜色/图案只在同一短句内与服装要素关联，避免邻近句子的颜色串位 */
  const clauseRange = (index) => {
    let start = 0;
    let end = text.length;
    for (let i = index - 1; i >= 0; i -= 1) {
      if ('，,。；;！!？?\n'.includes(text[i])) { start = i + 1; break; }
    }
    for (let i = index; i < text.length; i += 1) {
      if ('，,。；;！!？?\n'.includes(text[i])) { end = i; break; }
    }
    return [start, end];
  };
  const nearestColor = (pattern, maxDistance = 12) => {
    const match = pattern.exec(text);
    if (!match) return null;
    const target = match.index + match[0].length / 2;
    const [clauseStart, clauseEnd] = clauseRange(Math.round(target));
    const matches = [];
    colors.forEach((color) => {
      let at = text.indexOf(color);
      while (at !== -1) {
        if (at >= clauseStart && at + color.length <= clauseEnd) {
          matches.push({ color, at, end: at + color.length });
        }
        at = text.indexOf(color, at + 1);
      }
    });
    /* Drop shorter matches contained in a longer color, e.g. 米色 inside 浅米色 */
    const filtered = matches.filter((item) => !matches.some((other) => (
      other !== item
      && other.color.length > item.color.length
      && other.at <= item.at
      && other.end >= item.end
    )));
    let best = null;
    let bestDistance = Infinity;
    filtered.forEach((item) => {
      const distance = Math.abs(item.at + item.color.length / 2 - target);
      if (distance < bestDistance) { bestDistance = distance; best = item.color; }
    });
    return bestDistance <= maxDistance ? best : null;
  };

  /* 同义词归一：命中更具体的写法优先，面板显示统一口径 */
  const firstMatch = (rules) => {
    for (const [value, pattern] of rules) {
      if (pattern.test(text)) return value;
    }
    return null;
  };
  const collectMatches = (rules, source = text) => {
    const values = [];
    rules.forEach(([value, pattern]) => {
      if (pattern.test(source) && !values.includes(value)) values.push(value);
    });
    return values;
  };

  const hair = firstMatch([
    ['低侧发髻', /低侧发髻|低髻|侧发髻/],
    ['高马尾', /高马尾/],
    ['低马尾', /低马尾/],
    ['马尾', /马尾/],
    ['丸子头', /丸子头|盘发|发髻/],
    ['齐肩发', /齐肩/],
    ['波波头', /波波头|bob头/i],
    ['黑长直', /黑长直/],
    ['中长发', /中长发/],
    ['卷发', /卷发|大波浪|波浪卷/],
    ['短发', /短发|寸头/],
    ['长发', /长发/],
  ]);
  attrs.push({ label: '发型', value: hair, defined: !!hair });

  const hairAnchor = /头发|发色|发丝|发梢|刘海|短发|中长发|长发|齐肩|马尾|丸子头|发髻|盘发|波波头|卷发/;
  const hairColorAliases = {
    棕色: '深棕', 深棕色: '深棕', 浅棕色: '深棕', 栗色: '深棕',
    咖啡色: '深棕', 巧克力色: '深棕', 金黄: '金色', 银色: '灰色',
    银灰: '灰色', 银白: '白色',
  };
  const explicitHairColor = firstMatch([
    ['黑色', /黑发|乌黑|黑色头发/],
    ['金色', /金发|金色头发|金棕发/],
    ['灰色', /银发|灰发|银灰发/],
    ['红色', /红发|酒红发/],
    ['白色', /白发|银白发/],
    ['深棕', /深棕发|棕发|栗发|栗色头发/],
  ]);
  const nearbyHairColor = explicitHairColor ? null : nearestColor(hairAnchor, 6);
  const hairColor = explicitHairColor
    || (nearbyHairColor ? hairColorAliases[nearbyHairColor] || nearbyHairColor : null);
  attrs.push({ label: '发色', value: hairColor, defined: !!hairColor });

  const patternTokens = [
    ['纯色', ['纯色', '素色']],
    ['条纹', ['条纹']],
    ['格纹', ['格纹', '格子']],
    ['印花', ['印花']],
    ['波点', ['波点', '圆点']],
    ['碎花', ['碎花']],
    ['蕾丝', ['蕾丝']],
    ['logo', ['logo', 'LOGO', 'Logo']],
  ];
  const nearestPattern = (pattern) => {
    const match = pattern.exec(text);
    if (!match) return null;
    const target = match.index + match[0].length / 2;
    const [clauseStart, clauseEnd] = clauseRange(Math.round(target));
    let best = null;
    let bestDistance = Infinity;
    patternTokens.forEach(([value, words]) => {
      words.forEach((word) => {
        let at = text.indexOf(word);
        while (at !== -1) {
          if (at >= clauseStart && at + word.length <= clauseEnd) {
            const distance = Math.abs(at + word.length / 2 - target);
            if (distance < bestDistance) { bestDistance = distance; best = value; }
          }
          at = text.indexOf(word, at + 1);
        }
      });
    });
    return bestDistance <= 12 ? best : null;
  };

  const TOP_GARMENT_RULES = [
    ['亚麻西装外套', /亚麻(?:西装|西服)(?:外套)?/],
    ['西装外套', /(?:西装|西服)(?:外套)?/],
    ['风衣', /风衣/],
    ['大衣', /大衣/],
    ['皮衣', /皮衣|机车服/],
    ['夹克', /夹克/],
    ['卫衣', /卫衣/],
    ['衬衫', /衬衫|衬衣/],
    ['T恤', /t恤|体恤|文化衫/i],
    ['POLO衫', /polo衫/i],
    ['毛衣', /毛衣|羊毛衫/],
    ['针织衫', /针织衫/],
    ['连衣裙', /连衣裙|连身裙/],
    ['背心', /背心|吊带(?:衫|背心)?/],
    ['制服', /制服/],
    ['校服', /校服/],
    ['运动服', /运动服|运动套装/],
    ['上衣', /上衣|上装/],
  ];
  const topGarmentPattern = new RegExp(
    TOP_GARMENT_RULES.map(([, pattern]) => pattern.source).join('|'),
    'i',
  );
  const topPattern = nearestPattern(topGarmentPattern);
  const style = firstMatch(TOP_GARMENT_RULES);
  const topColor = nearestColor(topGarmentPattern);
  attrs.push({ label: '上装款式', value: style, defined: !!style });
  attrs.push({ label: '上装颜色', value: topColor, defined: !!topColor });
  attrs.push({ label: '上装图案', value: topPattern, defined: !!topPattern });

  const BOTTOM_GARMENT_RULES = [
    ['背带裤', /背带裤/],
    ['阔腿裤', /阔腿裤/],
    ['工装裤', /工装裤/],
    ['牛仔裤', /牛仔裤/],
    ['打底裤', /打底裤|紧身裤|瑜伽裤/],
    ['短裤', /短裤/],
    ['长裤', /长裤|西裤|休闲裤/],
    ['百褶裙', /百褶(?:短|长)?裙/],
    ['短裙', /短裙/],
    ['半身裙', /半身裙/],
    ['长裙', /长裙/],
    ['裙子', /(?<!连衣)裙/],
  ];
  const bottomGarmentPattern = new RegExp(
    BOTTOM_GARMENT_RULES.map(([, pattern]) => pattern.source).join('|'),
  );
  const bottomStyle = firstMatch(BOTTOM_GARMENT_RULES);
  const bottomColor = nearestColor(bottomGarmentPattern);
  const bottomPattern = nearestPattern(bottomGarmentPattern);
  attrs.push({ label: '下装款式', value: bottomStyle, defined: !!bottomStyle });
  attrs.push({ label: '下装颜色', value: bottomColor, defined: !!bottomColor });
  attrs.push({ label: '下装图案', value: bottomPattern, defined: !!bottomPattern });

  const ACCESSORY_RULES = [
    ['围巾', /围巾|丝巾|披肩/],
    ['眼镜', /眼镜|墨镜|太阳镜/],
    ['项链', /项链|吊坠|颈链/],
    ['耳饰', /耳环|耳钉|耳饰/],
    ['帽子', /帽子|贝雷帽|棒球帽|渔夫帽|鸭舌帽/],
    ['手套', /手套/],
    ['手表', /手表|腕表/],
    ['领带', /领带|领结/],
    ['手链', /手链|手镯/],
    ['发饰', /发带|发夹|发箍/],
  ];
  const noScarf = /无围巾|不戴围巾|没有围巾/.test(text);
  const accessories = collectMatches(
    ACCESSORY_RULES,
    text.replace(/无围巾|不戴围巾|没有围巾/g, ''),
  );
  if (!accessories.length && noScarf) accessories.push('无围巾');
  attrs.push({
    label: '配饰',
    value: accessories.length ? accessories.join('、') : null,
    defined: accessories.length > 0,
  });

  const SHOE_RULES = [
    ['高跟鞋', /高跟鞋/],
    ['运动鞋', /运动鞋|跑鞋|球鞋/],
    ['板鞋', /板鞋|滑板鞋/],
    ['帆布鞋', /帆布鞋/],
    ['乐福鞋', /乐福鞋/],
    ['马丁靴', /马丁靴/],
    ['雪地靴', /雪地靴/],
    ['短靴', /短靴/],
    ['长靴', /长靴|过膝靴/],
    ['靴子', /靴子|靴/],
    ['皮鞋', /皮鞋/],
    ['平底鞋', /平底鞋|单鞋/],
    ['凉鞋', /凉鞋/],
    ['拖鞋', /拖鞋/],
  ];
  const shoePattern = new RegExp(SHOE_RULES.map(([, pattern]) => pattern.source).join('|'));
  const shoeStyle = firstMatch(SHOE_RULES);
  const shoeColor = nearestColor(shoePattern);
  attrs.push({ label: '鞋履', value: shoeStyle ? (shoeColor ? `${shoeColor}${shoeStyle}` : shoeStyle) : null, defined: !!shoeStyle });

  const props = collectMatches([
    ['咖啡杯', /咖啡杯|马克杯/],
    ['水杯', /水杯|保温杯/],
    ['雨伞', /雨伞|遮阳伞/],
    ['书本', /书本|书籍|图书|小说/],
    ['武器', /刀|剑|枪|匕首/],
    ['手机', /手机/],
    ['背包', /背包|双肩包|书包/],
    ['手提包', /手提包|手袋|挎包|单肩包/],
    ['相机', /相机|单反/],
    ['花束', /花束|鲜花/],
    ['钥匙', /钥匙/],
    ['扇子', /扇子|折扇|团扇/],
    ['手杖', /手杖|拐杖/],
  ]);
  attrs.push({ label: '道具', value: props.length ? props.join('、') : null, defined: props.length > 0 });

  return { name, attrs };
}

function renderParsedAttributes() {
  const text = $('#character-input').value;
  const { attrs } = parseCharacter(text);
  STATE.attributes = attrs;
  $('#parsed-attributes').innerHTML = attrs.map((a) => `
    <div class="parsed-row ${a.defined ? '' : 'is-undef'}">
      <span class="dot"></span>
      <b>${a.label}</b>
      <span>${a.defined ? escapeHtml(a.value) : '设定未定义'}</span>
      <small>${a.defined ? '已明确' : '不参与违反设定判定'}</small>
    </div>`).join('');
  const taskChip = $('#current-task-name');
  if (taskChip) taskChip.textContent = `${parseCharacter(text).name} · 第一幕`;
  updateCreateValidation();
}

const SCRIPT_RULE_ITEMS = [
  { label: '发型', id: 'hair_style' },
  { label: '发色', id: 'hair_color' },
  { label: '上装款式', id: 'top_style' },
  { label: '上装颜色', id: 'top_color' },
  { label: '上装图案', id: 'top_pattern' },
  { label: '下装款式', id: 'bottom_style' },
  { label: '下装颜色', id: 'bottom_color' },
  { label: '下装图案', id: 'bottom_pattern' },
  { label: '配饰', id: 'accessories' },
  { label: '鞋履', id: 'shoes' },
  { label: '道具', id: 'props' },
];

const SCRIPT_TEMPLATES = {
  none: '所有镜头之间为同一场戏的连续动作，无换装情节。',
  change: '',
};

let scriptLocked = true;

function setScriptLock(locked) {
  scriptLocked = locked;
  const input = $('#script-input');
  if (!input) return;
  input.readOnly = locked;
  input.classList.toggle('is-readonly', locked);
  input.setAttribute('aria-readonly', String(locked));
  const hint = $('#script-input-hint');
  if (hint) hint.hidden = locked;
}

const CHANGE_WORDS = /换装|换成|换为|改为|改成|变为|变成|改穿|更换|换上|换下|染成|摘下|戴上|取下|摘掉|剪成|剪短|脱下|穿上|换穿|允许变化|可变化|可变|可调整|允许调整|允许变动|不做限制|不限制|豁免|换(?=发型|发色|配饰|道具|上装|下装|鞋)/;
const CHANGE_WORDS_G = new RegExp(CHANGE_WORDS.source, 'g');
const NO_CHANGE_WORDS = /(?:无|没有|不|未)(?:换装|更换)/;
const ALL_ATTRIBUTE_WORDS = /所有要素|全部要素|所有外观要素|全部外观要素|所有外观|全部外观/;
const CLOTHING_IDS = [
  'top_style', 'top_color', 'top_pattern',
  'bottom_style', 'bottom_color', 'bottom_pattern', 'shoes',
];
const ALL_ATTRIBUTE_IDS = SCRIPT_RULE_ITEMS.map((item) => item.id);
const SCRIPT_ATTRIBUTE_KEYWORDS = [
  ['上装款式', ['top_style']],
  ['上装颜色', ['top_color']],
  ['上装图案', ['top_pattern']],
  ['上装花纹', ['top_pattern']],
  ['外套款式', ['top_style']],
  ['外套颜色', ['top_color']],
  ['外套图案', ['top_pattern']],
  ['上衣款式', ['top_style']],
  ['上衣颜色', ['top_color']],
  ['上衣图案', ['top_pattern']],
  ['下装款式', ['bottom_style']],
  ['下装颜色', ['bottom_color']],
  ['下装图案', ['bottom_pattern']],
  ['下装花纹', ['bottom_pattern']],
  ['裤子款式', ['bottom_style']],
  ['裤子颜色', ['bottom_color']],
  ['裤子图案', ['bottom_pattern']],
  ['裙子款式', ['bottom_style']],
  ['裙子颜色', ['bottom_color']],
  ['裙子图案', ['bottom_pattern']],
  ['上装', ['top_style', 'top_color', 'top_pattern']],
  ['下装', ['bottom_style', 'bottom_color', 'bottom_pattern']],
  ['鞋履', ['shoes']],
  ['鞋子', ['shoes']],
  ['发色', ['hair_color']],
  ['头发颜色', ['hair_color']],
  ['头发', ['hair_style', 'hair_color']],
  ['发型', ['hair_style']],
  ['配饰', ['accessories']],
  ['项链', ['accessories']],
  ['吊坠', ['accessories']],
  ['颈链', ['accessories']],
  ['耳环', ['accessories']],
  ['耳饰', ['accessories']],
  ['耳钉', ['accessories']],
  ['手链', ['accessories']],
  ['手镯', ['accessories']],
  ['戒指', ['accessories']],
  ['帽子', ['accessories']],
  ['围巾', ['accessories']],
  ['围脖', ['accessories']],
  ['手套', ['accessories']],
  ['眼镜', ['accessories']],
  ['墨镜', ['accessories']],
  ['太阳镜', ['accessories']],
  ['领带', ['accessories']],
  ['领结', ['accessories']],
  ['手表', ['accessories']],
  ['腕表', ['accessories']],
  ['发带', ['accessories']],
  ['发夹', ['accessories']],
  ['发箍', ['accessories']],
  ['道具', ['props']],
].sort((a, b) => b[0].length - a[0].length);
const VERB_NEGATION = /(?:不|未|别|勿|不要|没有|无需)[^，。；]{0,3}$/;
const CN_NUMBERS = {
  一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6,
  七: 7, 八: 8, 九: 9, 十: 10, 十一: 11, 十二: 12,
};

function shotNumber(token) {
  if (/^\d+$/.test(token)) return Number(token);
  return CN_NUMBERS[token] || null;
}

function shotCodesIn(sentence) {
  const refs = new Set();
  const patterns = [
    /[Ss]\s*(\d+)/g,
    /第\s*([0-9一二三四五六七八九十]+)\s*(?:个)?镜头/g,
    /镜头\s*(\d+)/g,
  ];
  patterns.forEach((pattern) => {
    for (const match of sentence.matchAll(pattern)) {
      const num = shotNumber(match[1]);
      if (num && num >= 1 && num <= 999) refs.add(`S${num}`);
    }
  });
  return [...refs].sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
}

function hasChangeVerb(fragment) {
  for (const match of fragment.matchAll(CHANGE_WORDS_G)) {
    if (VERB_NEGATION.test(fragment.slice(0, match.index))) continue;
    return true;
  }
  return false;
}

// 取所在分句；顿号不切分，便于「发型、发色、配饰允许变化」这种列写
function clauseAt(sentence, position) {
  let start = 0;
  let end = sentence.length;
  for (const match of sentence.matchAll(/[，,。；;]/g)) {
    if (match.index < position) start = match.index + 1;
    else if (end === sentence.length) end = match.index;
  }
  return sentence.slice(start, end);
}

// 整句存在未被否定的变化词；「没有变为红色」不算变化描述
function hasPositiveChange(sentence) {
  for (const match of sentence.matchAll(CHANGE_WORDS_G)) {
    if (VERB_NEGATION.test(sentence.slice(0, match.index))) continue;
    return true;
  }
  return false;
}

// 与后端 script_parser._named_attributes 同口径：要素名附近有变化词才算写明
function namedChangeAttributes(sentence) {
  const hits = [];
  const found = new Set();
  SCRIPT_ATTRIBUTE_KEYWORDS.forEach(([keyword, ids]) => {
    let from = 0;
    for (;;) {
      const index = sentence.indexOf(keyword, from);
      if (index < 0) return;
      const end = index + keyword.length;
      const overlaps = hits.some(([hitStart, hitEnd]) => index < hitEnd && end > hitStart);
      const direct = index > 0 && sentence[index - 1] === '换';
      if (!overlaps && (direct || hasChangeVerb(clauseAt(sentence, index)))) {
        hits.push([index, end]);
        ids.forEach((id) => found.add(id));
      }
      from = end;
    }
  });
  return found;
}

// 与后端一致：按句判断变化描述，再在句内定位镜头号与要素
function parseChangePlan(text) {
  const byShot = new Map();
  const unlocated = [];
  const noElement = [];
  let mentionsChange = false;
  text.split(/[。；;\n]+/).forEach((raw) => {
    const sentence = raw.trim();
    if (!sentence || NO_CHANGE_WORDS.test(sentence) || !hasPositiveChange(sentence)) return;
    mentionsChange = true;
    const codes = shotCodesIn(sentence);
    if (!codes.length) {
      unlocated.push(sentence);
      return;
    }
    const named = namedChangeAttributes(sentence);
    const attributes = new Set(named);
    if (ALL_ATTRIBUTE_WORDS.test(sentence)) {
      ALL_ATTRIBUTE_IDS.forEach((id) => attributes.add(id));
    }
    if (!attributes.size) {
      // 只写「换装」不写要素：不建立任何豁免
      noElement.push(sentence);
      return;
    }
    codes.forEach((code) => {
      const current = byShot.get(code) || new Set();
      attributes.forEach((id) => current.add(id));
      byShot.set(code, current);
    });
  });
  return { byShot, unlocated, noElement, mentionsChange };
}

function changeSummary(plan) {
  // 把豁免范围完全相同的镜头合并成一条，避免逐镜头重复
  const groups = new Map();
  [...plan.byShot.entries()]
    .sort((a, b) => Number(a[0].slice(1)) - Number(b[0].slice(1)))
    .forEach(([code, ids]) => {
      const key = [...ids].sort().join('|');
      const group = groups.get(key) || { shots: [], ids };
      group.shots.push(code);
      groups.set(key, group);
    });
  return [...groups.values()]
    .sort((a, b) => Number(a.shots[0].slice(1)) - Number(b.shots[0].slice(1)))
    .map(({ shots, ids }) => {
      const allClothing = CLOTHING_IDS.every((id) => ids.has(id));
      const extras = SCRIPT_RULE_ITEMS
        .filter((item) => !CLOTHING_IDS.includes(item.id) && ids.has(item.id))
        .map((item) => item.label);
      let text;
      if (allClothing) {
        text = '上装、下装与鞋履';
        if (extras.length) text += `，以及${extras.join('、')}`;
      } else {
        text = SCRIPT_RULE_ITEMS
          .filter((item) => ids.has(item.id))
          .map((item) => item.label)
          .join('、');
      }
      return `${shots.join('、')} ${text}`;
    })
    .join('；');
}

function renderScriptRules(mode, plan) {
  const defined = new Map((STATE.attributes || []).map((a) => [a.label, a.defined]));
  $('#script-rule-grid').innerHTML = SCRIPT_RULE_ITEMS.map((item) => {
    if (defined.get(item.label) === false) {
      return `<div class="rule-item is-undef"><span>${icon('minus')}<b>${item.label}</b></span><span class="rule-state">设定未定义 · 不比对</span></div>`;
    }
    const shots = mode === 'change'
      ? [...plan.byShot.entries()].filter(([, ids]) => ids.has(item.id)).map(([code]) => code)
      : [];
    if (shots.length) {
      return `<div class="rule-item is-open"><span>${icon('check')}<b>${item.label}</b></span><span class="rule-state">${shots.join('、')} 允许变化</span></div>`;
    }
    return `<div class="rule-item is-locked"><span>${icon('lock')}<b>${item.label}</b></span><span class="rule-state">不允许变化</span></div>`;
  }).join('');
}

function syncScriptChips(mode) {
  const active = scriptLocked ? 'none' : mode === 'change' ? 'change' : '';
  $$('.template-row .chip').forEach((chip) => {
    const on = chip.dataset.template === active;
    chip.classList.toggle('is-active', on);
    chip.setAttribute('aria-pressed', String(on));
  });
}

function parseScript() {
  const raw = $('#script-input').value;
  const text = raw.trim();
  const noChange = NO_CHANGE_WORDS.test(text);
  const plan = parseChangePlan(text);
  const targets = [...plan.byShot.keys()]
    .sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));

  const mode = !text
    ? 'empty'
    : noChange
      ? 'none'
      : targets.length
        ? 'change'
        : plan.unlocated.length
          ? 'unlocated'
          : plan.noElement.length
            ? 'noElement'
            : plan.mentionsChange
              ? 'unlocated'
              : 'strict';

  const badge = $('#script-mode');
  const tone = mode === 'change'
    ? 'is-allow'
    : mode === 'unlocated' || mode === 'noElement' || mode === 'empty'
      ? 'is-warn'
      : 'is-strict';
  badge.className = `rule-badge ${tone}`;
  badge.textContent = mode === 'change'
    ? '局部豁免 · 其余严格'
    : mode === 'unlocated'
      ? '待定位 · 暂不豁免'
      : mode === 'empty'
        ? '待填写 · 暂不豁免'
        : '严格比对 · 无豁免';

  const summary = changeSummary(plan);
  const notes = {
    none: '剧情未允许变化：以下要素在全部镜头中按角色设定严格比对。',
    change: `已识别允许变化：${summary}。其余要素仍严格比对。`,
    unlocated: '描述中写有变化，但没有写明镜头号，无法建立豁免：以下要素暂按不允许变化处理。',
    noElement: '已定位到镜头，但没有写明具体变化要素，不建立任何豁免。',
    empty: '剧本说明为空：填写前以下要素全部按严格比对处理。',
    strict: '未检测到可定位到镜头的变化描述：以下要素在全部镜头中按角色设定严格比对。',
  };
  const foots = {
    none: '',
    change: '豁免只作用于写明的镜头与要素；未写明的要素仍逐镜头比对。',
    unlocated: '补充镜头号与要素（如「S2 发色变为红褐色」）后才能建立局部豁免。',
    noElement: '只写「换装」不会豁免任何要素；请写明如「S3 上装款式改为黑色高领毛衣」。',
    empty: '请先填写剧本说明；只有写明镜头与要素的变化才会建立局部豁免。',
    strict: '光线、角度与场景切换不构成豁免；只有写明镜头与要素的变化才允许局部变化。',
  };

  $('#script-rule-note').textContent = notes[mode];
  const footEl = $('#script-rule-foot');
  footEl.textContent = foots[mode];
  footEl.hidden = !foots[mode];
  $('#script-warning').hidden = !(mode === 'unlocated' || mode === 'noElement');
  const warningTitle = $('#script-warning-title');
  if (warningTitle) {
    warningTitle.textContent = mode === 'noElement'
      ? '已定位镜头，但未写明变化要素'
      : '变化描述尚未定位到镜头';
  }
  const warningNote = $('#script-warning-note');
  if (warningNote) {
    warningNote.textContent = mode === 'noElement'
      ? '当前不建立任何豁免。请写明具体要素，如「S3 上装款式改为黑色高领毛衣」。'
      : '当前不建立任何豁免，全部要素按不允许变化处理。请补充镜头号与具体要素（如「S2 发色变为红褐色」）后再开始检查。';
  }
  renderScriptRules(mode, plan);
  syncScriptChips(mode);
  // 剧本说明变化同样影响「开始检查」的可用状态，不能只在上传/角色设定变更时刷新
  updateCreateValidation();
}

function renderShots() {
  const list = $('#shot-list');
  list.innerHTML = STATE.shots.map((shot, i) => `
    <article class="shot-card" data-shot-card="${shot.id}" draggable="true">
      <div class="shot-image">
        <img src="${shot.image}" alt="${shot.id} 镜头预览">
        <span class="shot-index">${shot.id}</span>
        <button class="shot-remove" data-remove-shot="${shot.id}" aria-label="删除 ${shot.id}">${icon('close')}</button>
      </div>
      <div class="shot-body">
        <div class="shot-file"><b>${escapeHtml(shot.file)}</b><span>${escapeHtml(shot.note)}</span></div>
        <div class="shot-move">
          <button data-move-shot="${shot.id}" data-dir="-1" aria-label="上移 ${shot.id}" ${i === 0 ? 'disabled' : ''}>${icon('up')}</button>
          <button data-move-shot="${shot.id}" data-dir="1" aria-label="下移 ${shot.id}" ${i === STATE.shots.length - 1 ? 'disabled' : ''}>${icon('down')}</button>
        </div>
      </div>
      <div class="shot-quality ${shot.quality === 'ok' ? 'is-ok' : shot.quality === 'warn' ? 'is-warn' : 'is-err'}">
        ${icon(shot.quality === 'ok' ? 'check' : 'alert')} ${escapeHtml(shot.qualityLabel)}
      </div>
      <div class="shot-progress"><i style="width:${shot.progress ?? 100}%"></i></div>
    </article>`).join('');
  $('#shot-count-pill').textContent = `${STATE.shots.length} 个镜头`;
  $('#estimate-time').textContent = STATE.shots.length
    ? `${STATE.shots.length} 张 · 约 ${Math.max(20, STATE.shots.length * 15)} 秒`
    : '等待上传镜头';
  updateCreateValidation();
}

function updateCreateValidation() {
  const charOk = $('#character-input').value.trim().length > 0;
  const scriptOk = $('#script-input').value.trim().length > 0;
  // 只统计真实文件就绪的镜头，与提交时的校验口径一致。
  const readyShots = STATE.shots.filter((shot) => shot.nativeFile);
  const shotsOk = readyShots.length > 0;
  $('#check-character').className = `check-item ${charOk ? 'is-done' : 'is-missing'}`;
  $('#check-script').className = `check-item ${scriptOk ? 'is-done' : 'is-missing'}`;
  $('#check-shots').className = `check-item ${shotsOk ? 'is-done' : 'is-missing'}`;
  $('#check-shots-text').textContent = `${readyShots.length} 张镜头`;
  const btn = $('#start-analysis');
  btn.disabled = !(charOk && scriptOk && shotsOk);
  btn.title = btn.disabled ? '角色设定、剧本说明与至少 1 张镜头齐全后才能开始' : '';
}

function addFiles(files) {
  const imageFiles = [...files].filter((f) => f.type.startsWith('image/'));
  if (!imageFiles.length) { toast('请选择 JPG / PNG / WebP 图片'); return; }
  const startIndex = STATE.shots.length;
  const added = [];
  imageFiles.forEach((file, idx) => {
    const id = `S${startIndex + idx + 1}`;
    const image = URL.createObjectURL(file);
    const shot = { id, image, file: file.name, nativeFile: file, quality: 'warn', qualityLabel: '读取中 · 校验中', note: '待填写镜头备注', progress: 22 };
    STATE.shots.push(shot);
    added.push(shot);
  });
  renderShots();
  toast(`正在读取 ${imageFiles.length} 张镜头`);
  setTimeout(() => {
    added.forEach((s) => { s.progress = 100; s.quality = 'ok'; s.qualityLabel = '可用 · 校验通过'; });
    renderShots();
    toast(`已添加 ${imageFiles.length} 张镜头`);
  }, 850);
}

/* ---------------- analysis ---------------- */

function clearAnalysisTimers() {
  STATE.analysis.timers.forEach((t) => clearTimeout(t));
  STATE.analysis.timers = [];
}

function analysisPhasePill() {
  const phase = STATE.analysis.phase || 'idle';
  return {
    idle: ['is-idle', '待开始'],
    running: ['is-live', '分析中'],
    retrying: ['is-live', '重新观察中'],
    paused: ['is-partial', '已暂停'],
    complete: ['is-ok', '已完成'],
    partial: ['is-partial', '部分完成'],
    failed: ['is-failed', '分析失败'],
  }[phase] || ['is-idle', '待开始'];
}

function setStatusPill(el, cls, text) {
  if (!el) return;
  const next = `status-pill ${cls}`;
  if (el.className !== next) el.className = next;
  const icon = el.querySelector('i');
  const label = icon ? icon.nextSibling : null;
  if (!icon) {
    el.textContent = '';
    const dot = document.createElement('i');
    el.append(dot, document.createTextNode(text));
  } else if (!label || label.nodeType !== Node.TEXT_NODE || label.nodeValue !== text) {
    if (label && label.nodeType === Node.TEXT_NODE) label.nodeValue = text;
    else el.append(document.createTextNode(text));
  }
}

function updateTaskPill() {
  if (STATE.screen !== 'analysis') return;
  const el = $('#task-status-pill');
  if (!el) return;
  const [cls, text] = analysisPhasePill();
  setStatusPill(el, cls, text);
  const chip = $('#current-task-name');
  const name = STATE.analysis.taskName;
  if (chip && name && chip.textContent !== name) chip.textContent = name;
}

function padStage(n) {
  return String(n).padStart(2, '0');
}

function analysisCharacterName() {
  const a = STATE.analysis || {};
  if (a.characterName) return a.characterName;
  const input = $('#character-input');
  return parseCharacter(input ? input.value : '').name;
}

function analysisTaskName() {
  const a = STATE.analysis || {};
  const chip = $('#current-task-name');
  return a.taskName || (chip ? chip.textContent : '') || analysisCharacterName();
}

function analysisStageNames() {
  const a = STATE.analysis || {};
  return Array.isArray(a.stageNames) && a.stageNames.length
    ? a.stageNames
    : ANALYSIS_STAGES.map((stage) => stage.name);
}

function analysisElapsedSeconds() {
  const a = STATE.analysis || {};
  if (!a.startedAt) return null;
  const start = Date.parse(a.startedAt);
  if (Number.isNaN(start)) return null;
  const end = a.endedAt ? Date.parse(a.endedAt) : Date.now();
  if (Number.isNaN(end)) return null;
  return Math.max(0, Math.floor((end - start) / 1000));
}

function formatElapsed(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const value = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(value / 60);
  const rest = value % 60;
  if (minutes >= 60) {
    return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
  }
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
}

function elapsedMarkup() {
  return `<span class="mono analysis-elapsed" id="analysis-elapsed" aria-live="off">${formatElapsed(analysisElapsedSeconds())}</span>`;
}

/* 只更新计时节点，避免整行重建与滚动位置跳动。 */
function updateAnalysisClock() {
  const el = $('#analysis-elapsed');
  if (!el) return;
  const next = formatElapsed(analysisElapsedSeconds());
  if (el.textContent !== next) el.textContent = next;
}

function setSubline(html, key) {
  const el = $('#analysis-subline');
  if (!el) return;
  if (!key || el.dataset.sublineKey !== key) {
    el.dataset.sublineKey = key || '';
    el.innerHTML = html;
  }
  updateAnalysisClock();
}

function shotObservationStats(shotId) {
  const list = observationsFor(shotId);
  const live = STATE.analysis?.verdictCounts?.[shotId];
  return {
    total: list.length,
    unknown: live ? live.unknown : list.filter((item) => item.verdict === 'unknown').length,
    inconsistent: live ? live.inconsistent : list.filter((item) => item.verdict === 'inconsistent').length,
    judged: Boolean(live?.judged) || list.some((item) => item.verdict),
  };
}

function analysisTotals() {
  const a = STATE.analysis || {};
  return {
    issues: Number.isFinite(a.issueCount) ? a.issueCount : STATE.issues.length,
    unknowns: Number.isFinite(a.unknownCount) ? a.unknownCount : STATE.unknowns.length,
  };
}

/* 演示与真实模式共用：只统计当前已揭示/已落库的观察，避免提前显示全量结论。 */
function visibleVerdictTotals() {
  let inconsistent = 0;
  let unknown = 0;
  STATE.shots.forEach((shot, index) => {
    const visible = observationsFor(shot.id).slice(0, visibleObservationCount(index));
    for (const item of visible) {
      if (item.verdict === 'inconsistent') inconsistent += 1;
      else if (item.verdict === 'unknown') unknown += 1;
    }
  });
  return { inconsistent, unknown };
}

function visibleObservationCount(index) {
  const shot = STATE.shots[index];
  const total = observationsFor(shot?.id).length;
  const status = STATE.analysis.statuses[index] || 'pending';
  if (status === 'pending') return 0;
  if (status === 'analyzing') return Math.min(total, Math.max(3, STATE.analysis.observedCounts[index] || 0));
  return total;
}

function analyzingBadgeNote() {
  return '正在观察画面要素';
}

function shotErrorText(shotId) {
  const error = STATE.analysis?.shotErrors?.[shotId];
  if (!error) return '观察失败 · 可单独重新观察';
  if (error.message) return error.message;
  return {
    provider_timeout: '模型服务响应超时',
    file_unavailable: '镜头文件不可用',
    auth_failed: '分析服务鉴权失败',
    quota_exceeded: '分析服务额度不足',
    content_filter: '画面未通过内容安全校验',
  }[error.code] || `观察失败（${error.code || '未知原因'}）`;
}

function observationsFor(shotId) {
  return (STATE.realObservations && STATE.realObservations[shotId])
    || OBSERVATIONS[shotId]
    || [];
}

function shotStateMeta(status, shotId) {
  if (status === 'ok' || status === 'issue') {
    const { inconsistent, judged } = shotObservationStats(shotId);
    if (!judged) return { label: '待判定', cls: 'is-idle', icon: 'clock' };
    return inconsistent
      ? { label: `${inconsistent} 处不一致`, cls: 'is-alert', icon: 'alert' }
      : { label: '全部一致', cls: 'is-ok', icon: 'check' };
  }
  return {
    pending: { label: '待观察', cls: 'is-idle', icon: 'clock' },
    analyzing: { label: '观察中', cls: 'is-live', icon: 'refresh' },
    failed: { label: '观察失败', cls: 'is-alert', icon: 'alert' },
  }[status] || { label: '待观察', cls: 'is-idle', icon: 'clock' };
}

function pendingShotNote() {
  return '等待逐镜头观察开始';
}

function shotDetailText(status, shotId) {
  const stats = shotObservationStats(shotId);
  if (status === 'pending') {
    return STATE.analysis.phase === 'paused' ? '观察已中断' : '等待观察';
  }
  if (status === 'analyzing') return '观察中 · 结果返回后显示';
  if (status === 'failed') return shotErrorText(shotId);
  if (!stats.judged) return '观察完成 · 待判定';
  return `${stats.unknown} 项无法判断`;
}

function updateAnalysisHeader() {
  const a = STATE.analysis;
  const shots = STATE.shots;
  const total = shots.length;
  const totals = analysisTotals();
  const character = analysisCharacterName();
  const stageNames = analysisStageNames();
  const stageCount = stageNames.length;
  const stageIndex = Math.max(0, Math.min(a.stage || 0, Math.max(0, stageCount - 1)));
  const stageName = a.stageName || stageNames[stageIndex] || '素材校验';
  const done = a.statuses.filter((status) => status === 'ok' || status === 'issue').length;
  const failedIdx = a.statuses.indexOf('failed');
  const failedShot = failedIdx >= 0 ? shots[failedIdx] : null;
  const observedTotal = shots.reduce(
    (sum, shot, index) => sum + observationsFor(shot.id).slice(0, visibleObservationCount(index)).length,
    0,
  );
  const paused = a.phase === 'paused';
  const failed = a.phase === 'failed';
  const partial = a.phase === 'partial' || Boolean(a.partial);
  const elapsed = elapsedMarkup();

  const titleEl = $('#analysis-current-title');
  const title = paused
    ? `${character} · 分析暂停`
    : failed
      ? `${character} · 分析失败`
      : a.complete
        ? `${character} · ${partial ? '分析部分完成' : '分析完成'}`
        : a.started && total
          ? `正在分析${character}的连续镜头`
          : '检测任务';
  if (titleEl && titleEl.textContent !== title) titleEl.textContent = title;

  const kicker = $('#analysis-kicker');
  if (kicker) {
    const kickerText = paused
      ? 'ANALYSIS PAUSED'
      : failed
        ? 'ANALYSIS FAILED'
        : a.complete
          ? 'ANALYSIS COMPLETE'
          : 'LIVE ANALYSIS';
    if (kicker.textContent !== kickerText) kicker.textContent = kickerText;
  }
  if (STATE.screen === 'analysis') {
    const eyebrow = paused
      ? 'TASK / PAUSED'
      : failed
        ? 'TASK / FAILED'
        : a.complete
          ? 'TASK / COMPLETED'
          : a.phase === 'retrying'
            ? 'TASK / RETRYING'
            : 'TASK / ANALYZING';
    // 以 DOM 当前值为准，避免 showScreen 改写后缓存导致眉标与实际状态不一致。
    const eyebrowEl = $('#page-eyebrow');
    if (eyebrowEl && eyebrowEl.getAttribute('aria-label') !== eyebrow) {
      setPageEyebrow(eyebrow);
    }
  }

  const progress = Math.max(0, Math.min(100, Number(a.progress) || 0));
  const progressBar = $('#analysis-progress');
  if (progressBar) {
    const width = `${progress}%`;
    if (progressBar.style.width !== width) progressBar.style.width = width;
    const track = progressBar.parentElement;
    if (track && track.getAttribute('aria-valuenow') !== String(progress)) {
      track.setAttribute('aria-valuenow', String(progress));
    }
  }
  const progressText = $('#analysis-progress-text');
  const progressLabel = `${Math.round(progress)}%`;
  if (progressText && progressText.textContent !== progressLabel) {
    progressText.textContent = progressLabel;
  }

  let subline;
  let sublineKey;
  if (a.connectionLost) {
    subline = `与本地服务连接中断 · 正在自动重试 · 已用时 ${elapsed}`;
    sublineKey = 'connection-lost';
  } else if (paused) {
    const reason = failedShot
      ? `${escapeHtml(failedShot.id)} 观察失败`
      : '观察已中断';
    subline = `分析暂停 · ${reason} · 其他镜头结果已保留 · 已用时 ${elapsed}`;
    sublineKey = `paused|${failedShot ? failedShot.id : 'interrupted'}`;
  } else if (failed) {
    const message = escapeHtml(a.errorMessage || '分析失败，可稍后在历史报告重试');
    subline = `${message} · 已用时 ${elapsed}`;
    sublineKey = `failed|${message}`;
  } else if (a.phase === 'retrying') {
    const shot = shots[a.viewIndex];
    const shotLabel = shot ? escapeHtml(shot.id) : '当前镜头';
    subline = `重新观察 ${shotLabel} · 其他镜头结果保留 · 已用时 ${elapsed}`;
    sublineKey = `retrying|${shot ? shot.id : ''}`;
  } else if (a.complete) {
    subline = `分析${partial ? '部分完成' : '完成'} · ${totals.issues} 处确定不一致 · ${totals.unknowns} 项无法判断 · 用时 ${elapsed}`;
    sublineKey = `complete|${partial}|${totals.issues}|${totals.unknowns}`;
  } else if (!a.started) {
    subline = total ? `等待开始分析 · 已录入 ${total} 个镜头` : '正在连接分析任务…';
    sublineKey = `idle|${total}`;
  } else if (stageIndex === 0) {
    subline = `素材校验 · 正在检查 ${total} 张镜头的格式、清晰度与可用性 · 已用时 ${elapsed}`;
    sublineKey = `stage-0|${total}`;
  } else if (stageIndex === 1) {
    subline = `设定解析 · 正在提取${escapeHtml(character)}的固定外观设定 · 已用时 ${elapsed}`;
    sublineKey = `stage-1|${character}`;
  } else if (stageIndex === 2) {
    subline = `剧本解析 · 正在核对镜头说明与允许的局部变化 · 已用时 ${elapsed}`;
    sublineKey = 'stage-2';
  } else if (stageIndex === 3) {
    subline = `逐镜头观察 · 已完成 ${done} / ${total} · 已记录 ${observedTotal} 项观察 · 已用时 ${elapsed}`;
    sublineKey = `stage-3|${done}|${total}|${observedTotal}`;
  } else if (stageIndex === 4) {
    subline = `一致性判定 · 已比对 ${observedTotal} 项观察记录 · 已用时 ${elapsed}`;
    sublineKey = `stage-4|${observedTotal}`;
  } else {
    const ready = a.suggestionReady || 0;
    const suggestionTotal = a.suggestionTotal || 0;
    const demoIssues = a.realMode ? totals.issues : visibleVerdictTotals().inconsistent;
    if (suggestionTotal) {
      subline = `生成建议 · 已整理 ${ready} / ${suggestionTotal} 条修正建议 · 已用时 ${elapsed}`;
      sublineKey = `stage-5|${ready}|${suggestionTotal}`;
    } else if (demoIssues) {
      subline = `生成建议 · 正在为 ${demoIssues} 处不一致整理修正方案 · 已用时 ${elapsed}`;
      sublineKey = `stage-5-demo|${demoIssues}`;
    } else {
      subline = `生成建议 · 当前没有需要修正的问题 · 已用时 ${elapsed}`;
      sublineKey = 'stage-5-empty';
    }
  }
  setSubline(subline, sublineKey);

  const stagePill = $('#analysis-stage-pill');
  if (stagePill) {
    const idle = !(a.started && total);
    const cls = `status-pill ${
      a.complete ? 'is-ok' : failed ? 'is-failed' : paused ? 'is-partial' : idle ? 'is-idle' : 'is-live'
    }`;
    if (stagePill.className !== cls) stagePill.className = cls;
  }
  const stageLabel = $('#analysis-stage-label');
  const stageText = a.started && total
    ? `${padStage(stageIndex + 1)} / ${padStage(stageCount)} · ${stageName}`
    : '— / — · 等待开始';
  if (stageLabel && stageLabel.textContent !== stageText) stageLabel.textContent = stageText;

  // 运行状态卡只保留一份状态与一份进度：空闲、完成、失败、暂停时标题与阶段标签
  // 已说明状态，卡片直接收起，不再切换「任务状态」「建议进度」等重复文案。
  const runCard = $('#analysis-run-card');
  const runHidden = !a.started || a.complete || failed || paused;
  if (runCard && runCard.hidden !== runHidden) runCard.hidden = runHidden;

  const statusPill = $('#analysis-status-pill');
  const statusText = $('#analysis-status-text');
  if (statusPill && statusText) {
    const mode = String(a.modeNote || '真实任务').split(' · ')[0];
    const stateText = a.connectionLost
      ? '连接中断'
      : a.phase === 'retrying'
        ? '重试中'
        : '分析中';
    const label = `${mode} · ${stateText}`;
    if (statusText.textContent !== label) statusText.textContent = label;
    const pillClass = `status-pill ${a.connectionLost ? 'is-warn' : 'is-live'}`;
    if (statusPill.className !== pillClass) statusPill.className = pillClass;
  }

  const demoBtn = $('[data-action="simulate-partial"]');
  const cancelBtn = $('[data-action="cancel-analysis"]');
  const demoHidden = Boolean(a.complete || a.realMode || failed || !a.started);
  if (demoBtn && demoBtn.hidden !== demoHidden) demoBtn.hidden = demoHidden;
  // paused（服务重启）走后端空操作，隐藏按钮避免“取消成功”的假象。
  const cancelHidden = Boolean(a.complete || failed || paused || !a.started);
  if (cancelBtn && cancelBtn.hidden !== cancelHidden) cancelBtn.hidden = cancelHidden;

  const pipelineStatus = $('#pipeline-status');
  const pipelineText = a.started && total
    ? paused
      ? `已暂停在 ${padStage(stageIndex + 1)} / ${padStage(stageCount)} · ${stageName}`
      : failed
        ? `分析失败于 ${padStage(stageIndex + 1)} / ${padStage(stageCount)} · ${stageName}`
        : `已完成 ${a.complete ? stageCount : stageIndex} / ${stageCount} 个阶段`
    : '等待开始';
  if (pipelineStatus && pipelineStatus.textContent !== pipelineText) {
    pipelineStatus.textContent = pipelineText;
  }

  const scanning = a.phase === 'running' && stageIndex >= 3 && stageIndex <= 4;
  const scan = $('#analysis-scan');
  if (scan && scan.classList.contains('is-running') !== scanning) {
    scan.classList.toggle('is-running', scanning);
  }
  updateTaskPill();
}

function setAnalysisProgress(progress, stage, eta) {
  const a = STATE.analysis;
  const previousStage = a.stage;
  a.progress = Math.max(Number(a.progress) || 0, Math.min(100, Number(progress) || 0));
  a.stage = stage;
  if (typeof eta === 'number') {
    a.etaSeconds = eta;
  } else if (typeof eta === 'string') {
    const match = eta.match(/(\d+)/);
    a.etaSeconds = match ? Number(match[1]) : null;
  }
  updateAnalysisHeader();
  renderPipeline();
  if (stage !== previousStage) {
    const label = $('#analysis-stage-label');
    label.classList.remove('is-flash');
    void label.offsetWidth;
    label.classList.add('is-flash');
  }
}

function startObservationReveal(index) {
  const a = STATE.analysis;
  const total = observationsFor(STATE.shots[index]?.id).length;
  a.observedCounts[index] = Math.min(3, total);
  for (let count = 4; count <= total; count += 1) {
    STATE.analysis.timers.push(setTimeout(() => {
      if (STATE.analysis.statuses[index] !== 'analyzing') return;
      STATE.analysis.observedCounts[index] = count;
      if (STATE.screen === 'analysis' && STATE.analysis.viewIndex === index) {
        // 只有用户停留在底部时才跟随；上翻阅读时不打断。
        const body = $('.analysis-insights .insight-body');
        const follow = body
          ? body.scrollHeight - body.scrollTop - body.clientHeight < 32
          : false;
        renderInsights(index);
        if (follow && body) body.scrollTop = body.scrollHeight;
        const badgeNote = $('#analysis-badge small');
        if (badgeNote) badgeNote.textContent = analyzingBadgeNote();
      }
    }, (count - 3) * 300));
  }
}

function startAnalysis() {
  clearAnalysisTimers();
  const a = STATE.analysis;
  // 没有镜头时不得启动演示（直接打开 #analysis 不应伪造一段 0/0 的分析）。
  if (!STATE.shots.length) {
    a.started = false;
    renderAnalysisScreen();
    return;
  }
  a.started = true;
  a.complete = false;
  a.partial = false;
  a.phase = 'running';
  a.current = 0;
  a.viewIndex = 0;
  a.stage = 0;
  a.progress = 0;
  a.statuses = STATE.shots.map(() => 'pending');
  a.observedCounts = STATE.shots.map(() => 0);
  a.verdictCounts = {};
  a.issueCount = 0;
  a.unknownCount = 0;
  a.realMode = false;
  a.modeNote = '演示视图';
  a.characterName = parseCharacter($('#character-input').value).name;
  a.taskName = `${a.characterName} · 第一幕`;
  a.stageName = '';
  a.stageNames = null;
  a.etaSeconds = 18;
  a.suggestionReady = 0;
  a.suggestionTotal = 0;
  a.startedAt = new Date().toISOString();
  a.endedAt = null;
  a.connectionLost = false;
  a.shotErrors = {};
  a.subjects = {};
  resetAnalysisView();
  STATE.selectedShot = STATE.shots[0]?.id || 'S1';
  showScreen('analysis');
  setAnalysisProgress(3, 0, '约 18 秒');
  renderAnalysisScreen();
  updateTaskPill();

  const T = (delay, fn) => STATE.analysis.timers.push(setTimeout(fn, delay));

  T(900, () => setAnalysisProgress(10, 1, '约 16 秒'));
  T(2100, () => setAnalysisProgress(19, 2, '约 15 秒'));
  T(3500, () => {
    a.statuses = STATE.shots.map((_, i) => (i === 0 ? 'analyzing' : 'pending'));
    a.current = 0;
    a.viewIndex = 0;
    startObservationReveal(0);
    setAnalysisProgress(30, 3, '约 13 秒');
    renderAnalysisScreen();
  });
  T(6100, () => {
    a.statuses = STATE.shots.map((_, i) => (i === 0 ? 'ok' : i === 1 ? 'analyzing' : 'pending'));
    a.current = 1;
    a.viewIndex = 1;
    STATE.selectedShot = 'S2';
    startObservationReveal(1);
    setAnalysisProgress(45, 3, '约 11 秒');
    renderAnalysisScreen();
  });
  T(8900, () => {
    a.statuses = STATE.shots.map((_, i) => (i < 2 ? (i === 0 ? 'ok' : 'issue') : 'analyzing'));
    a.current = 2;
    a.viewIndex = 2;
    STATE.selectedShot = 'S3';
    startObservationReveal(2);
    setAnalysisProgress(60, 3, '约 8 秒');
    renderAnalysisScreen();
  });
  T(11700, () => {
    a.statuses = STATE.shots.map((_, i) => (i === 0 ? 'ok' : 'issue'));
    a.current = 2;
    setAnalysisProgress(76, 4, '约 5 秒');
    renderAnalysisScreen();
  });
  T(13500, () => setAnalysisProgress(88, 5, '约 3 秒'));
  T(15500, () => setAnalysisProgress(96, 5, '约 2 秒'));
  T(17000, () => {
    const totals = visibleVerdictTotals();
    a.complete = true;
    a.phase = 'complete';
    a.statuses = STATE.shots.map((_, i) => (i === 0 ? 'ok' : 'issue'));
    a.issueCount = totals.inconsistent;
    a.unknownCount = totals.unknown;
    a.endedAt = new Date().toISOString();
    setAnalysisProgress(100, 5, 'done');
    renderAnalysisScreen();
    updateTaskPill();
    toast(`分析完成 · ${totals.inconsistent} 处确定不一致 · ${totals.unknown} 项无法判断`);
  });
}

function simulatePartialFailure() {
  if (!STATE.analysis.started) { toast('请先开始分析，再演示异常状态'); return; }
  clearAnalysisTimers();
  const a = STATE.analysis;
  const failedIndex = Math.min(1, STATE.shots.length - 1);
  a.complete = false;
  a.phase = 'paused';
  a.statuses = STATE.shots.map((_, i) => (i === failedIndex ? 'failed' : a.statuses[i] === 'pending' ? 'ok' : a.statuses[i]));
  a.current = failedIndex;
  a.viewIndex = failedIndex;
  a.endedAt = new Date().toISOString();
  STATE.selectedShot = STATE.shots[failedIndex]?.id || 'S1';
  setAnalysisProgress(74, 3, 'paused');
  renderAnalysisScreen();
  updateTaskPill();
  toast(`演示状态：${STATE.shots[failedIndex]?.id || '当前镜头'} 观察失败，可单独重新观察`);
}

function retryShot() {
  const a = STATE.analysis;
  const i = a.viewIndex;
  const shot = STATE.shots[i];
  if (!shot) return;
  a.phase = 'retrying';
  a.complete = false;
  a.endedAt = null;
  a.statuses[i] = 'analyzing';
  startObservationReveal(i);
  setAnalysisProgress(84, 3, '约 3 秒');
  renderAnalysisScreen();
  updateTaskPill();
  a.timers.push(setTimeout(() => {
    a.statuses[i] = shotObservationStats(shot.id).inconsistent ? 'issue' : 'ok';
    a.statuses = a.statuses.map((status) => (status === 'pending' || status === 'analyzing' ? 'pending' : status));
    const fullyDone = a.statuses.every((status) => status === 'ok' || status === 'issue');
    a.complete = fullyDone;
    a.phase = fullyDone ? 'complete' : 'running';
    if (fullyDone) {
      const totals = visibleVerdictTotals();
      a.issueCount = totals.inconsistent;
      a.unknownCount = totals.unknown;
      a.endedAt = new Date().toISOString();
    }
    setAnalysisProgress(fullyDone ? 100 : 88, fullyDone ? 5 : 4, fullyDone ? 'done' : '约 3 秒');
    renderAnalysisScreen();
    updateTaskPill();
    toast(`${shot.id} 重新观察完成 · 其他镜头未重跑`);
  }, 2600));
}

function cancelAnalysis() {
  clearAnalysisTimers();
  const a = STATE.analysis;
  a.started = false;
  a.complete = false;
  a.partial = false;
  a.phase = 'idle';
  a.stage = 0;
  a.progress = 0;
  a.statuses = STATE.shots.map(() => 'pending');
  a.observedCounts = STATE.shots.map(() => 0);
  a.verdictCounts = {};
  a.issueCount = 0;
  a.unknownCount = 0;
  a.etaSeconds = null;
  a.startedAt = null;
  a.endedAt = null;
  a.connectionLost = false;
  $('#analysis-result-cta').hidden = true;
  $('#analysis-scan').classList.remove('is-running');
  setAnalysisProgress(0, 0, '—');
  showScreen('create');
  toast('已取消分析，已录入的素材保留');
}

let insightScrollShot = null;
const insightScrollByShot = new Map();

function resetInsightScrollMemory() {
  insightScrollShot = null;
  insightScrollByShot.clear();
}

/* 切换镜头前先记录离开位置（必须在 DOM 重建之前）；轮询更新绝不改写滚动位置。 */
function captureInsightScroll(nextShotId) {
  const body = $('.analysis-insights .insight-body');
  if (!body || !insightScrollShot || insightScrollShot === nextShotId) return;
  insightScrollByShot.set(insightScrollShot, body.scrollTop);
}

function syncInsightScroll(shotId) {
  const body = $('.analysis-insights .insight-body');
  if (!body) return;
  if (insightScrollShot === shotId) return;
  insightScrollShot = shotId;
  body.scrollTop = insightScrollByShot.get(shotId) || 0;
}

function renderAnalysisBadge(status, shot) {
  const stats = shotObservationStats(shot.id);
  let cls = 'is-idle';
  let orb = `<span class="badge-glyph">${icon('clock')}</span>`;
  let title = '待观察';
  let note = STATE.analysis.phase === 'paused' ? '观察已中断' : '镜头观察即将开始';
  if (status === 'analyzing') {
    cls = 'is-live';
    orb = '<span class="scan-spinner"></span>';
    title = '观察中';
    note = analyzingBadgeNote();
  } else if (status === 'failed') {
    cls = 'is-alert';
    orb = `<span class="badge-glyph">${icon('alert')}</span>`;
    title = '观察失败';
    note = shotErrorText(shot.id);
  } else if (status === 'ok' || status === 'issue') {
    if (!stats.judged) {
      cls = 'is-idle';
      orb = `<span class="badge-glyph">${icon('clock')}</span>`;
      title = '观察完成';
      note = '等待一致性判定';
    } else {
      const issue = stats.inconsistent > 0;
      cls = issue ? 'is-alert' : 'is-done';
      orb = `<span class="badge-glyph">${icon(issue ? 'alert' : 'check')}</span>`;
      title = issue ? `${stats.inconsistent} 处不一致` : '全部一致';
      note = `${stats.unknown} 项无法判断 · 证据已记录`;
    }
  }
  const badge = $('#analysis-badge');
  if (!badge) return;
  const badgeCls = `preview-analysis-badge ${cls}`;
  if (badge.className !== badgeCls) badge.className = badgeCls;
  const orbEl = badge.querySelector('.badge-orb');
  const orbKey = status === 'analyzing' ? 'spinner' : `${cls}|${title}`;
  if (orbEl && orbEl.dataset.key !== orbKey) {
    orbEl.dataset.key = orbKey;
    orbEl.innerHTML = orb;
  }
  const titleEl = badge.querySelector('b');
  if (titleEl && titleEl.textContent !== title) titleEl.textContent = title;
  const noteEl = badge.querySelector('small');
  if (noteEl && noteEl.textContent !== note) noteEl.textContent = note;
}

function renderAnalysisChip(status) {
  const [cls, text] = {
    pending: ['is-idle', '证据链 · 待建立'],
    analyzing: ['is-live', '证据链 · 采集中'],
    ok: ['is-ok', '证据链 · 已建立'],
    issue: ['is-ok', '证据链 · 已建立'],
    failed: ['is-alert', '证据链 · 未建立'],
  }[status] || ['is-idle', '证据链 · 待建立'];
  const chip = $('#analysis-preview-chip');
  if (chip) {
    const next = `preview-chip ${cls}`;
    if (chip.className !== next) chip.className = next;
  }
  const textEl = $('#preview-chip-text');
  if (textEl && textEl.textContent !== text) textEl.textContent = text;
}

function updateInsightPill(status, shotId) {
  const meta = shotStateMeta(status, shotId);
  setStatusPill($('#insight-state-pill'), meta.cls, meta.label);
}

function updateResultCta() {
  const cta = $('#analysis-result-cta');
  if (!cta) return;
  if (!STATE.analysis.complete) {
    if (!cta.hidden) cta.hidden = true;
    return;
  }
  const totals = analysisTotals();
  const partial = STATE.analysis.phase === 'partial' || Boolean(STATE.analysis.partial);
  const title = $('#analysis-result-title');
  const titleText = partial ? '分析部分完成' : '分析完成';
  if (title && title.textContent !== titleText) title.textContent = titleText;
  const text = partial
    ? `${totals.issues} 处确定不一致，${totals.unknowns} 项无法判断。部分镜头观察失败，报告覆盖其余镜头。`
    : `${totals.issues} 处确定不一致，${totals.unknowns} 项无法判断。`;
  const textEl = $('#analysis-result-text');
  if (textEl && textEl.textContent !== text) textEl.textContent = text;
  if (cta.hidden) cta.hidden = false;
}

function setText(selector, text) {
  const el = typeof selector === 'string' ? $(selector) : selector;
  if (el && el.textContent !== text) el.textContent = text;
}

function renderAnalysisScreen() {
  const order = STATE.shots;
  const a = STATE.analysis;
  if (!order.length) {
    renderAnalysisEmpty();
    return;
  }
  const idx = Math.max(0, Math.min(a.viewIndex ?? 0, order.length - 1));
  const shot = order[idx];
  const status = a.statuses[idx] || 'pending';

  renderShotRail(order, a, idx);
  renderPreview(shot, status);
  captureInsightScroll(shot.id);
  renderInsights(idx);
  syncInsightScroll(shot.id);
  renderPipeline();
  updateAnalysisHeader();
  updateResultCta();
}

/* 首帧或切换任务时使用中性占位，避免沿用上一任务或写死数字。 */
function renderAnalysisEmpty() {
  const rail = $('#analysis-shot-list');
  if (rail && rail.dataset.signature !== 'empty') {
    rail.dataset.signature = 'empty';
    rail.innerHTML = '<div class="insight-stage" style="padding:18px 6px">正在载入镜头…</div>';
  }
  setText('#rail-count', '已完成 — / —');
  setText('#analysis-shot-tag', '— / 当前镜头');
  const img = $('#analysis-preview-img');
  if (img) {
    delete img.dataset.shotImage;
    img.alt = '当前观察镜头';
    if (!img.src.startsWith('data:image/svg+xml')) {
      img.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1600' height='1000'%3E%3Crect width='100%25' height='100%25' fill='%2307111c'/%3E%3C/svg%3E";
    }
  }
  const chip = $('#analysis-preview-chip');
  if (chip && chip.className !== 'preview-chip is-idle') chip.className = 'preview-chip is-idle';
  setText('#preview-chip-text', '证据链 · 待建立');
  const badge = $('#analysis-badge');
  if (badge) {
    badge.className = 'preview-analysis-badge is-idle';
    const orb = badge.querySelector('.badge-orb');
    if (orb && orb.dataset.key !== 'idle') {
      orb.dataset.key = 'idle';
      orb.innerHTML = `<span class="badge-glyph">${icon('clock')}</span>`;
    }
    setText(badge.querySelector('b'), '连接中');
    setText(badge.querySelector('small'), '正在读取任务状态');
  }
  setStatusPill($('#insight-state-pill'), 'is-idle', '等待开始');
  const insights = $('#analysis-insights');
  if (insights && insights.dataset.viewKey !== 'empty') {
    insights.dataset.viewKey = 'empty';
    insights.innerHTML = '<div class="insight-stage">正在载入任务数据…</div>';
  }
  const pipeline = $('#analysis-pipeline');
  if (pipeline && pipeline.dataset.signature !== 'empty') {
    pipeline.dataset.signature = 'empty';
    pipeline.innerHTML = '';
  }
  updateAnalysisHeader();
  updateResultCta();
}

function renderShotRail(order, a, idx) {
  const rail = $('#analysis-shot-list');
  if (!rail) return;
  const signature = order.map((shot) => `${shot.id}|${shot.image}`).join(';');
  if (rail.dataset.signature !== signature) {
    rail.dataset.signature = signature;
    rail.innerHTML = order.map((shot, i) => `
      <button class="rail-item" data-analysis-shot="${i}" aria-current="false">
        <span class="rail-thumb"><img src="${escapeHtml(shot.image)}" alt="" loading="lazy"></span>
        <span class="rail-copy">
          <b>${escapeHtml(shot.id)}</b>
          <span class="rail-detail"></span>
          <span class="rail-state"></span>
        </span>
      </button>`).join('');
  }
  const items = rail.querySelectorAll('[data-analysis-shot]');
  order.forEach((shot, i) => {
    const node = items[i];
    if (!node) return;
    const st = a.statuses[i] || 'pending';
    const meta = shotStateMeta(st, shot.id);
    const classes = [
      'rail-item',
      i === idx ? 'is-active' : '',
      st === 'analyzing' ? 'is-analyzing' : '',
      st === 'issue' ? 'is-issue' : '',
    ].filter(Boolean).join(' ');
    if (node.className !== classes) node.className = classes;
    const current = i === idx ? 'true' : 'false';
    if (node.getAttribute('aria-current') !== current) node.setAttribute('aria-current', current);
    setText(node.querySelector('.rail-detail'), shotDetailText(st, shot.id));
    const stateEl = node.querySelector('.rail-state');
    if (stateEl) {
      const stateCls = `rail-state ${meta.cls}`;
      if (stateEl.className !== stateCls) stateEl.className = stateCls;
      const stateKey = `${meta.icon}|${meta.label}`;
      if (stateEl.dataset.key !== stateKey) {
        stateEl.dataset.key = stateKey;
        stateEl.innerHTML = `${icon(meta.icon)}${meta.label}`;
      }
    }
    const img = node.querySelector('img');
    if (img && img.getAttribute('src') !== shot.image) img.setAttribute('src', shot.image);
  });
  const done = a.statuses.filter((st) => st === 'ok' || st === 'issue').length;
  setText('#rail-count', `已完成 ${a.started ? done : 0} / ${order.length}`);
}

function renderPreview(shot, status) {
  const img = $('#analysis-preview-img');
  if (img) {
    if (img.dataset.shotImage !== shot.image) {
      img.dataset.shotImage = shot.image;
      img.src = shot.image;
    }
    const alt = `当前观察镜头 ${shot.id}`;
    if (img.alt !== alt) img.alt = alt;
  }
  setText('#analysis-shot-tag', `${shot.id} / 当前镜头`);
  renderAnalysisBadge(status, shot);
  renderAnalysisChip(status);
  updateInsightPill(status, shot.id);
}

let insightsViewKey = '';
const obsNodes = new Map();

function resetAnalysisView() {
  insightsViewKey = '';
  obsNodes.clear();
  resetInsightScrollMemory();
  const rail = $('#analysis-shot-list');
  if (rail) delete rail.dataset.signature;
  const pipeline = $('#analysis-pipeline');
  if (pipeline) delete pipeline.dataset.signature;
  const insights = $('#analysis-insights');
  if (insights) delete insights.dataset.viewKey;
}

function insightViewKeyFor(shot, status) {
  return `${shot.id}|${status === 'failed' ? 'failed' : 'normal'}`;
}

function observationKey(item) {
  return item.attributeId || item.name;
}

function verdictMeta(verdict) {
  switch (verdict) {
    case 'consistent': return { tone: 'ok', text: '一致' };
    case 'inconsistent': return { tone: 'alert', text: '不一致' };
    case 'unknown': return { tone: 'muted', text: '无法判断' };
    case 'waived': return { tone: 'info', text: '豁免' };
    case 'observed_only':
    case 'neutral': return { tone: 'neutral', text: '仅记录' };
    default: return { tone: 'neutral', text: '待判定' };
  }
}

function createObsItem(item, index) {
  const node = document.createElement('div');
  node.className = 'obs-item';
  node.style.animationDelay = `${Math.min(index, 8) * 40}ms`;
  node.innerHTML = `<div class="obs-head"><b></b><span class="obs-verdict"></span></div>
    <div class="obs-values"><span class="from"></span><span class="obs-target"></span></div>
    <div class="obs-evidence" data-role="evidence"></div>`;
  updateObsItem(node, item);
  return node;
}

/* 按字段更新观察项，不重建节点，避免入场动画与滚动位置被重置。 */
function updateObsItem(node, item) {
  const meta = verdictMeta(item.verdict);
  setText(node.querySelector('.obs-head b'), item.name);
  const verdictEl = node.querySelector('.obs-verdict');
  if (verdictEl) {
    const verdictKey = `${meta.tone}|${meta.text}`;
    if (verdictEl.dataset.key !== verdictKey) {
      verdictEl.dataset.key = verdictKey;
      verdictEl.innerHTML = pill(meta.text, meta.tone);
    }
  }
  const from = node.querySelector('.from');
  const fromText = item.verdict === 'unknown' ? '—' : item.observed;
  setText(from, fromText);
  const target = node.querySelector('.obs-target');
  if (target) {
    const targetKey = `${item.verdict}|${item.name}`;
    if (target.dataset.key !== targetKey) {
      target.dataset.key = targetKey;
      target.innerHTML = item.verdict === 'inconsistent'
        ? `${icon('arrow-right')}<span class="to">与设定不符</span>`
        : '';
    }
  }
  const evidence = node.querySelector('[data-role="evidence"]');
  if (evidence) {
    const unknown = item.verdict === 'unknown';
    const cls = unknown ? 'obs-unknown' : 'obs-evidence';
    if (evidence.className !== cls) evidence.className = cls;
    setText(evidence, `${unknown ? '原因' : '证据'}：${item.evidence}`);
  }
}

function normalInsightsHtml() {
  return `
    <div class="insight-section">
      <div class="insight-section-title"><span>SUBJECT FOCUS</span><span data-role="subject-pill"></span></div>
      <div class="identity-card" data-role="subject-card" data-state="idle">
        <span class="identity-avatar">
          <img data-role="subject-avatar" alt="" loading="lazy">
          <i class="identity-scan" aria-hidden="true"></i>
        </span>
        <div class="identity-copy">
          <b data-role="subject-name">当前镜头主体</b>
          <span data-role="subject-meta">等待主体观察</span>
        </div>
        <span class="identity-signal" data-role="subject-signal" aria-hidden="true">
          <i></i><i></i><i></i><i></i>
        </span>
      </div>
    </div>
    <div class="insight-section">
      <div class="insight-section-title"><span data-role="obs-title"></span><span data-role="obs-count"></span></div>
      <div class="obs-list" data-role="obs-list">
        <div class="insight-stage" data-role="obs-empty" hidden></div>
      </div>
    </div>
    <div class="insight-section" data-role="footer">
      <div class="insight-stage"><span data-role="stage-icon"></span><span data-role="stage-line"></span></div>
    </div>`;
}

function failedInsightsHtml(shot) {
  const real = STATE.analysis.realMode;
  const retry = real
    ? ''
    : `<div class="insight-section">
      <button class="btn btn-ghost btn-block" data-action="retry-shot">${icon('refresh')}<span data-role="retry-label"></span></button>
    </div>`;
  return `
    <div class="insight-section">
      <div class="insight-section-title"><span>SHOT STATUS · ${escapeHtml(shot.id)}</span><span data-role="failed-pill"></span></div>
      <div class="analysis-failure">
        <span class="status-icon is-alert">${icon('alert')}</span>
        <div><b data-role="failed-title"></b><p data-role="failed-copy"></p></div>
      </div>
    </div>
    <div class="insight-section">
      <div class="insight-stage">${statusIcon('info')}<span data-role="failed-note"></span></div>
    </div>${retry}`;
}

function updateFailedInsights(shot) {
  const panel = $('#analysis-insights');
  if (!panel) return;
  const real = STATE.analysis.realMode;
  const error = shotErrorText(shot.id).replace(/[。.]$/, '');
  const pillEl = panel.querySelector('[data-role="failed-pill"]');
  if (pillEl && pillEl.dataset.key !== 'failed') {
    pillEl.dataset.key = 'failed';
    pillEl.innerHTML = pill('观察失败', 'failed');
  }
  setText(panel.querySelector('[data-role="failed-title"]'), `${shot.id} 观察失败`);
  setText(
    panel.querySelector('[data-role="failed-copy"]'),
    real
      ? `${error}。其他镜头的观察结果与证据均已保留。请在历史报告重新开始本任务。`
      : `${error}。其他镜头的观察结果与证据均已保留，不需要整任务重跑。`,
  );
  setText(
    panel.querySelector('[data-role="failed-note"]'),
    real
      ? '观察失败 · 当前页不支持单镜头重试，可在历史报告重新开始本任务'
      : `观察失败 · 可单独重新观察，重新观察只覆盖 ${shot.id}`,
  );
  if (!real) setText(panel.querySelector('[data-role="retry-label"]'), `重新观察 ${shot.id}`);
}

function renderInsights(idx) {
  const shot = STATE.shots[idx];
  if (!shot) return;
  const a = STATE.analysis;
  const status = a.statuses[idx] || 'pending';
  const panel = $('#analysis-insights');
  if (!panel) return;

  const viewKey = insightViewKeyFor(shot, status);
  if (viewKey !== insightsViewKey) {
    insightsViewKey = viewKey;
    obsNodes.clear();
    panel.dataset.viewKey = viewKey;
    panel.innerHTML = status === 'failed' ? failedInsightsHtml(shot) : normalInsightsHtml();
  }
  if (status === 'failed') {
    updateFailedInsights(shot);
    return;
  }

  const observations = observationsFor(shot.id);
  const visibleCount = status === 'ok' || status === 'issue'
    ? observations.length
    : status === 'analyzing' && !a.realMode
      ? visibleObservationCount(idx)
      : 0;
  const visibleObservations = observations.slice(0, visibleCount);
  const stats = shotObservationStats(shot.id);
  const subject = a.subjects ? a.subjects[shot.id] : null;
  const identified = Boolean(subject) || stats.total > 0 || (!a.realMode && a.stage >= 1);

  const subjectPill = panel.querySelector('[data-role="subject-pill"]');
  if (subjectPill) {
    const key = identified ? 'ok' : 'neutral';
    if (subjectPill.dataset.key !== key) {
      subjectPill.dataset.key = key;
      subjectPill.innerHTML = pill(identified ? '主体锁定' : '等待主体', key);
    }
  }
  const avatar = panel.querySelector('[data-role="subject-avatar"]');
  const avatarSrc = shot.thumb || shot.image;
  if (avatar && avatar.getAttribute('src') !== avatarSrc) avatar.setAttribute('src', avatarSrc);
  // 只描述画面主体构成，不展示角色名、人脸识别结论或伪置信度百分比。
  const personCount = Number(subject?.personCount) || 0;
  const subjectMeta = personCount === 1
    ? '单人画面 · 已纳入观察'
    : personCount > 1
      ? '多人画面 · 以占比最大人物为观察对象'
      : identified
        ? '主体已纳入观察'
        : '等待主体观察';
  setText(panel.querySelector('[data-role="subject-meta"]'), subjectMeta);
  const card = panel.querySelector('[data-role="subject-card"]');
  if (card) {
    card.dataset.state = !identified ? 'idle' : personCount > 1 ? 'multi' : 'ready';
  }

  setText(panel.querySelector('[data-role="obs-title"]'), `OBSERVATIONS · ${shot.id}`);
  const countText = observations.length
    ? `${visibleObservations.length} / ${observations.length}`
    : status === 'analyzing'
      ? '观察中'
      : '—';
  setText(panel.querySelector('[data-role="obs-count"]'), countText);

  const list = panel.querySelector('[data-role="obs-list"]');
  if (list) {
    const desiredKeys = new Set(visibleObservations.map(observationKey));
    visibleObservations.forEach((item, i) => {
      const key = observationKey(item);
      let node = obsNodes.get(key);
      if (!node) {
        node = createObsItem(item, i);
        obsNodes.set(key, node);
        list.appendChild(node);
      } else {
        updateObsItem(node, item);
      }
    });
    for (const [key, node] of obsNodes) {
      if (!desiredKeys.has(key)) {
        node.remove();
        obsNodes.delete(key);
      }
    }
    const empty = list.querySelector('[data-role="obs-empty"]');
    if (empty) {
      const showEmpty = visibleObservations.length === 0;
      if (empty.hidden !== !showEmpty) empty.hidden = !showEmpty;
      if (showEmpty) {
        let text;
        if (status === 'analyzing') {
          text = a.realMode
            ? '正在观察画面要素 · 结果返回后一次性显示'
            : '正在逐项观察画面…';
        } else if (status === 'pending') {
          text = a.phase === 'paused'
            ? '观察已中断，可在历史报告重新开始'
            : pendingShotNote();
        } else {
          text = '暂无观察结果';
        }
        const iconHtml = status === 'analyzing' ? '<span class="scan-spinner"></span>' : statusIcon('info');
        const html = `${iconHtml}${text}`;
        if (empty.dataset.html !== html) {
          empty.dataset.html = html;
          empty.innerHTML = html;
        }
      }
    }
  }

  const footer = panel.querySelector('[data-role="footer"]');
  if (footer) {
    // 观察中没有结果时，由列表内空状态承载说明，避免同一句话重复两次。
    const show = status !== 'pending'
      && !(status === 'analyzing' && visibleObservations.length === 0);
    if (footer.hidden !== !show) footer.hidden = !show;
    if (show) {
      const iconEl = footer.querySelector('[data-role="stage-icon"]');
      const iconKey = status === 'analyzing' ? 'spinner' : 'ok';
      if (iconEl && iconEl.dataset.key !== iconKey) {
        iconEl.dataset.key = iconKey;
        iconEl.innerHTML = iconKey === 'spinner' ? '<span class="scan-spinner"></span>' : statusIcon('ok');
      }
      const line = status === 'analyzing'
        ? a.realMode
          ? '正在观察画面要素 · 结果返回后一次性显示'
          : `正在逐项观察 · 已完成 ${visibleObservations.length} / ${observations.length} 项`
        : !stats.judged
          ? `观察完成 · ${stats.total} 项已记录 · 等待一致性判定`
          : `观察完成 · ${stats.total} 项已记录 · ${stats.unknown} 项无法判断`;
      setText(footer.querySelector('[data-role="stage-line"]'), line);
    }
  }
}

function renderPipeline() {
  const a = STATE.analysis;
  const stages = analysisStageNames();
  const total = stages.length;
  const container = $('#analysis-pipeline');
  if (!container) return;
  const signature = stages.join('|');
  if (container.dataset.signature !== signature) {
    container.dataset.signature = signature;
    container.innerHTML = stages.map((name, i) => `
      <div class="pipe-step" style="--i:${i}">
        <i class="pipe-num">${String(i + 1).padStart(2, '0')}</i>
        <span class="pipe-name"></span>
        <span class="pipe-flag"></span>
      </div>`).join('');
  }
  const activeIndex = a.complete
    ? total
    : Math.max(0, Math.min(a.stage || 0, Math.max(0, total - 1)));
  const paused = a.phase === 'paused';
  const failedPhase = a.phase === 'failed';
  const containerCls = `pipeline-steps${a.complete ? ' is-complete' : ''}`;
  if (container.className !== containerCls) container.className = containerCls;
  container.querySelectorAll('.pipe-step').forEach((step, i) => {
    setText(step.querySelector('.pipe-name'), stages[i]);
    const done = a.complete || i < activeIndex;
    const active = !a.complete && i === activeIndex;
    const failed = (paused || failedPhase) && i === activeIndex;
    const stateCls = failed ? 'is-failed' : done ? 'is-done' : active ? 'is-active' : '';
    const nextCls = `pipe-step ${stateCls}`.trim();
    if (step.className !== nextCls) step.className = nextCls;
    const flag = step.querySelector('.pipe-flag');
    const flagKey = done ? 'check' : failed ? 'alert' : '';
    if (flag && flag.dataset.key !== flagKey) {
      flag.dataset.key = flagKey;
      flag.innerHTML = flagKey ? icon(flagKey) : '';
    }
  });
}

/* ---------------- results ---------------- */

function shotHasIssue(shotId) {
  return STATE.issues.some((i) => i.shot === shotId);
}
function shotStatus(shotId) {
  if (shotHasIssue(shotId)) return 'issue';
  if (STATE.unknowns.some((u) => u.shot === shotId)) return 'unknown';
  return 'ok';
}

function countConsistentCells() {
  return MATRIX.reduce((total, row) => total + ['S1', 'S2', 'S3'].filter((sid) => row.cells[sid]?.status === 'ok').length, 0);
}

function renderResults() {
  $('#sum-issues').textContent = STATE.issues.length;
  $('#sum-unknown').textContent = STATE.unknowns.length;
  $('#sum-suspected').textContent = 0;
  $('#sum-consistent').textContent = countConsistentCells();
  $('#tab-count-issues').textContent = STATE.issues.length;
  $('#tab-count-suspected').textContent = 0;
  $('#tab-count-unknown').textContent = STATE.unknowns.length;
  $('#tab-count-matrix').textContent = MATRIX.length * 3;
  const summaryText = $('#summary-text');
  if (summaryText) {
    summaryText.innerHTML = STATE.issues.length
      ? `阿岚在 3 个镜头中有 <b>${STATE.issues.length} 处确定不一致</b>，集中在 ${STATE.issues.map((i) => `${i.shot} 的${i.short || i.attribute}`).join('、')}。另有 ${STATE.unknowns.length} 项信息因画面不可见或角度遮挡，无法判断。`
      : `阿岚的 3 个镜头中已无确定不一致。剩余 ${STATE.unknowns.length} 项信息因画面不可见或角度遮挡，无法判断。原始镜头与修订记录均已保留。`;
  }

  const gallery = STATE.shots.filter((s) => {
    if (STATE.galleryFilter === 'issue') return shotStatus(s.id) === 'issue';
    if (STATE.galleryFilter === 'unknown') return shotStatus(s.id) === 'unknown';
    return true;
  });
  $('#results-gallery').innerHTML = gallery.map((s) => {
    const status = shotStatus(s.id);
    const flags = status === 'issue' ? 'is-alert' : status === 'unknown' ? 'is-muted' : 'is-ok';
    const flagIcon = status === 'issue' ? 'alert' : status === 'unknown' ? 'help' : 'check';
    const issueCount = STATE.issues.filter((i) => i.shot === s.id).length;
    const unknownCount = STATE.unknowns.filter((u) => u.shot === s.id).length;
    return `<button class="gallery-card ${status === 'issue' ? 'is-issue' : ''} ${STATE.selectedShot === s.id ? 'is-selected' : ''}" data-gallery-shot="${s.id}">
      <span class="gallery-img"><img src="${s.image}" alt=""><span class="shot-index">${s.id}</span><span class="gallery-flag ${flags}">${icon(flagIcon)}</span></span>
      <span class="gallery-copy"><b>${s.id}</b><span>${issueCount ? `${issueCount} 个问题` : status === 'unknown' ? `${unknownCount} 项待判断` : '全部一致'}</span></span>
    </button>`;
  }).join('');

  renderMatrix();
  renderIssueList();
  renderUnknownList();
  renderSuggestions();
  renderInspector();
  renderTabs();
}

function renderTabs() {
  $$('.tab').forEach((t) => {
    const active = t.dataset.tab === STATE.resultTab;
    t.classList.toggle('is-active', active);
    t.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  $$('.tab-panel').forEach((p) => p.classList.toggle('is-active', p.id === `tab-${STATE.resultTab}`));
}

function renderMatrix() {
  $('#matrix-body').innerHTML = MATRIX.map((row) => {
    const cells = ['S1', 'S2', 'S3'].map((sid) => {
      const cell = row.cells[sid];
      const iconName = cell.status === 'ok' ? 'check' : cell.status === 'alert' ? 'alert' : cell.status === 'muted' ? 'help' : cell.status === 'observed' ? 'minus' : 'info';
      const focused = cell.issue && STATE.selectedIssue === cell.issue;
      const label = cell.status === 'ok' ? '一致' : cell.status === 'alert' ? '不一致' : cell.status === 'muted' ? (cell.note || '仅记录') : cell.status === 'observed' ? '仅记录' : '豁免';
      return `<td class="matrix-cell">
        <button class="cell-btn ${focused ? 'is-focused' : ''}" data-cell-shot="${sid}" data-cell-issue="${cell.issue || ''}">
          <span class="status-icon is-${cell.status}">${icon(iconName)}</span>
          <span class="cell-copy is-${cell.status}"><b>${cell.status === 'muted' && cell.value === null ? '—' : escapeHtml(cell.value)}</b><span>${escapeHtml(label)}</span></span>
        </button>
      </td>`;
    }).join('');
    return `<tr>
      <td><span class="matrix-attr"><b>${row.key}</b><span>${row.code}</span></span></td>
      <td class="matrix-expect">${row.expected}</td>
      ${cells}
    </tr>`;
  }).join('');
}

function renderIssueList() {
  if (!STATE.issues.length) {
    $('#issue-list').innerHTML = `
      <div class="empty-state small">
        <span class="empty-icon">${icon('check')}</span>
        <h4>没有确定问题</h4>
        <p>所有可判断的「镜头 × 要素」都与角色设定一致。无法判断项仍单独展示，不计入一致结论。</p>
      </div>`;
    return;
  }
  $('#issue-list').innerHTML = STATE.issues.map((issue) => `
    <article class="issue-card ${STATE.selectedIssue === issue.id ? 'is-selected' : ''}" data-issue="${issue.id}" role="button" tabindex="0">
      <span class="issue-sev">
        <span class="status-icon ${issue.severityValue === 'high' ? 'is-alert' : 'is-warn'}">${icon('alert')}</span>
        <small>${issue.severityValue === 'high' ? 'HIGH' : 'MED'}</small>
      </span>
      <span class="issue-copy">
        <span class="issue-top"><span class="issue-id">${issue.id}</span><span class="issue-shot">${issue.shot}</span><h4>${escapeHtml(issue.attribute)}</h4></span>
        <span class="issue-values"><span class="expected">${escapeHtml(issue.expected)}</span>${icon('arrow-right')}<span class="actual">${escapeHtml(issue.observed)}</span></span>
        <span class="issue-evidence">证据：${escapeHtml(issue.evidence)}</span>
      </span>
      <span class="issue-side">
        <span class="issue-meta">严重度 ${issue.severity} · 置信度 ${issue.confidence}</span>
        <button class="btn btn-ghost btn-sm" data-optimize-issue="${issue.id}">优化此镜头${icon('arrow-right')}</button>
      </span>
    </article>`).join('');
}

function renderUnknownList() {
  $('#unknown-list').innerHTML = STATE.unknowns.length ? STATE.unknowns.map((u) => `
    <div class="unknown-item">
      <span class="status-icon is-muted">${icon('help')}</span>
      <span class="unknown-copy"><b>${u.attribute} · ${u.shot}</b><p>原因：${escapeHtml(u.reason)}</p></span>
      <span class="mono">${u.id}</span>
    </div>`).join('') : '<div class="empty-state small"><h4>没有无法判断项</h4><p>所有要素在画面中均可见并有充分证据。</p></div>';
}

function renderSuggestions() {
  const active = SUGGESTIONS.filter((s) => STATE.issues.some((i) => i.id === s.issueId));
  $('#suggestion-grid').innerHTML = active.length ? active.map((s) => `
    <article class="suggestion-card">
      <div class="suggestion-top">
        <div><span class="mono">${s.issueId} · ${s.shot}</span><h4>${escapeHtml(s.title)}</h4></div>
        ${pill('可直接使用', 'ok')}
      </div>
      <div class="suggestion-prompt">${escapeHtml(s.prompt)}</div>
      <div class="suggestion-foot">
        <span>${s.refs} · 每批 4 张</span>
        <span class="suggestion-actions">
          <button class="btn btn-ghost btn-sm" data-copy-suggestion="${s.issueId}">${icon('copy')}复制</button>
          <button class="btn btn-primary btn-sm" data-optimize-issue="${s.issueId}">优化</button>
        </span>
      </div>
    </article>`).join('') : '<div class="empty-state small"><h4>当前没有待修正问题</h4><p>问题关闭后，对应的修正提示词与抽卡方案会从活动建议中移除。</p></div>';
}

function renderInspector() {
  const issue = STATE.issues.find((i) => i.id === STATE.selectedIssue);
  if (issue) {
    const shot = STATE.shots.find((s) => s.id === issue.shot);
    $('#results-inspector').innerHTML = `
      <section class="inspector-card">
        <div class="inspector-head">
          <div><span class="mono">${issue.id} · ${issue.shot}</span><h3>${escapeHtml(issue.attribute)}</h3></div>
          <span class="status-icon ${issue.severityValue === 'high' ? 'is-alert' : 'is-warn'}">${icon('alert')}</span>
        </div>
        <div class="inspector-pill-row">
          ${pill(`严重度 ${issue.severity}`, issue.severityValue === 'high' ? 'failed' : 'warn')}
          ${pill(`置信度 ${issue.confidence}`, 'ok')}
          ${pill(issue.type, 'neutral')}
        </div>
        <div class="inspector-section">
          <span class="inspector-label">EXPECTED / OBSERVED</span>
          <div class="compare-values">
            <div class="compare-value"><span>设定期望</span><b>${escapeHtml(issue.expected)}</b></div>
            <div class="compare-value is-bad"><span>实际观察</span><b>${escapeHtml(issue.observed)}</b></div>
          </div>
        </div>
        <div class="inspector-section">
          <span class="inspector-label">EVIDENCE</span>
          <div class="evidence-quote">“${escapeHtml(issue.evidence)}”</div>
        </div>
        <div class="inspector-section">
          <span class="inspector-label">SCRIPT CONTEXT</span>
          <div class="waiver-trace">${escapeHtml(issue.waiver)}。本条未命中剧本豁免。</div>
        </div>
        <div class="inspector-actions">
          <button class="btn btn-primary" data-optimize-issue="${issue.id}">${icon('refresh')}优化此镜头</button>
          <button class="btn btn-ghost" data-locate-shot="${issue.shot}">${icon('image')}定位到 ${issue.shot}</button>
        </div>
      </section>
      <div class="inspector-nav"><span>镜头状态</span><b>${shot ? `${shot.id} · 1 个确定问题` : issue.shot}</b></div>`;
    return;
  }
  const shot = STATE.shots.find((s) => s.id === STATE.selectedShot);
  if (!shot) { $('#results-inspector').innerHTML = ''; return; }
  const obs = OBSERVATIONS[shot.id] || [];
  $('#results-inspector').innerHTML = `
    <section class="inspector-card">
      <div class="inspector-head"><div><span class="mono">${shot.id} · SHOT SUMMARY</span><h3>${shot.id} 镜头结论</h3></div>${statusIcon(shotStatus(shot.id), 'check')}</div>
      <div class="inspector-pill-row">${pill(shotStatus(shot.id) === 'ok' ? '全部一致' : shotStatus(shot.id) === 'unknown' ? '存在无法判断' : '存在问题', shotStatus(shot.id) === 'ok' ? 'ok' : shotStatus(shot.id) === 'unknown' ? 'neutral' : 'failed')}${pill('当前版本', 'neutral')}</div>
      <div class="inspector-section">
        <span class="inspector-label">OBSERVATIONS</span>
        ${obs.map((o) => `<div class="compare-value" style="margin-bottom:4px"><span>${o.name}</span><b>${o.observed ? escapeHtml(o.observed) : '无法判断'}</b></div>`).join('')}
      </div>
      <div class="inspector-actions"><button class="btn btn-ghost" data-lightbox-shot="${shot.id}">${icon('image')}查看大图</button></div>
    </section>`;
}

function openLightbox(shotId) {
  const shot = STATE.shots.find((s) => s.id === shotId);
  if (!shot) return;
  const img = $('#lightbox-img');
  img.src = shot.image;
  img.alt = `${shotId} 镜头大图`;
  $('#lightbox-id').textContent = shotId;
  $('#lightbox-name').textContent = shot.file || '镜头原图';
  $('#lightbox').hidden = false;
}

function closeLightbox() {
  $('#lightbox').hidden = true;
}

function locateShot(shotId) {
  STATE.selectedShot = shotId;
  STATE.selectedIssue = null;
  STATE.galleryFilter = 'all';
  $$('.gallery-filter .chip').forEach((chip) => chip.classList.toggle('is-active', chip.dataset.statusFilter === 'all'));
  renderResults();
  const card = document.querySelector(`.gallery-card[data-gallery-shot="${shotId}"]`);
  if (card) {
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
    card.classList.add('is-locating');
    setTimeout(() => card.classList.remove('is-locating'), 1400);
  }
  const inspector = $('#results-inspector');
  if (window.innerWidth < 1120) inspector.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function selectShot(shotId, issueId = null) {
  STATE.selectedShot = shotId;
  if (issueId) STATE.selectedIssue = issueId;
  else {
    const first = STATE.issues.find((i) => i.shot === shotId);
    STATE.selectedIssue = first ? first.id : null;
  }
  renderResults();
  const inspector = $('#results-inspector');
  if (window.innerWidth < 1120) inspector.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function selectIssue(issueId) {
  const issue = STATE.issues.find((i) => i.id === issueId);
  if (!issue) return;
  STATE.selectedIssue = issueId;
  STATE.selectedShot = issue.shot;
  renderResults();
  const inspector = $('#results-inspector');
  if (window.innerWidth < 1120) inspector.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function filterGallery(status) {
  STATE.galleryFilter = status;
  $$('.gallery-filter .chip').forEach((c) => c.classList.toggle('is-active', c.dataset.statusFilter === status));
  renderResults();
}

function exportReport(kind) {
  const profile = parseCharacter($('#character-input').value);
  const activeSuggestions = SUGGESTIONS.filter((s) => STATE.issues.some((i) => i.id === s.issueId));
  if (kind === 'json') {
    const data = {
      schemaVersion: '1.2',
      taskId: 'task_20261122_001',
      character: profile.name,
      createdAt: '2026-11-22T10:06:00+08:00',
      status: 'completed',
      profile: profile.attrs.map((a) => ({ name: a.label, value: a.value, source: a.defined ? 'explicit' : 'undefined' })),
      shots: STATE.shots.map((s) => ({ index: Number(s.id.replace('S', '')), status: shotStatus(s.id), imageRef: s.image })),
      issues: STATE.issues,
      unknownItems: STATE.unknowns,
      waivers: [],
      suggestions: activeSuggestions,
      stats: { totalShots: STATE.shots.length, confirmedIssueCount: STATE.issues.length, unknownCount: STATE.unknowns.length, waiverCount: 0, consistentJudgementCount: countConsistentCells() },
    };
    downloadFile(`一致性检查_${profile.name}_20261122_1006.json`, JSON.stringify(data, null, 2), 'application/json');
  } else {
    const lines = [
      `# 角色形象一致性检查报告`, '',
      `- 角色：${profile.name}`,
      `- 镜头数：${STATE.shots.length}`,
      `- 剧本说明：${$('#script-input').value.trim()}`,
      `- 检查时间：2026-11-22 10:06`,
      `- 结论：${STATE.issues.length} 处确定不一致，${STATE.unknowns.length} 项无法判断；无剧本豁免。`,
      '', '## 问题明细', '',
      ...STATE.issues.flatMap((i) => [
        `### ${i.id} · ${i.shot} · ${i.attribute}`,
        `- 设定期望：${i.expected}`,
        `- 实际观察：${i.observed}`,
        `- 证据：${i.evidence}`,
        `- 严重度：${i.severity} ｜ 置信度：${i.confidence}`,
        `- 剧本豁免：${i.waiver}`, '',
      ]),
      '## 无法判断项', '',
      ...STATE.unknowns.map((u) => `- ${u.id} · ${u.shot} · ${u.attribute}：${u.reason}`),
      '', '## 修正建议', '',
      ...activeSuggestions.map((s) => `### ${s.issueId} · ${s.shot}\n- 修正提示词：${s.prompt}\n- 参考：${s.refs}\n`),
      '> 本报告由 UI 原型导出，数据为本地演示数据。',
    ];
    downloadFile(`一致性检查_${profile.name}_20261122_1006.md`, lines.join('\n'), 'text/markdown');
  }
  toast(`已导出 ${kind === 'json' ? 'JSON' : 'Markdown'} 报告`);
}

/* ---------------- optimizer ---------------- */

function normalizeOptData(shot) {
  return OPTIMIZER_DATA[shot] || OPTIMIZER_DATA.S3;
}

function adoptedCandidateId(shot = STATE.opt.shot) {
  return (STATE.opt.adopted && STATE.opt.adopted[shot]) || null;
}

function setAdoptedCandidate(shot, candidateId) {
  if (!STATE.opt.adopted) STATE.opt.adopted = {};
  if (candidateId) STATE.opt.adopted[shot] = candidateId;
  else delete STATE.opt.adopted[shot];
}

const CANDIDATE_RANK = { pass: 0, partial: 1, fail: 2, unknown: 3 };

function candidateOutcome(candidate) {
  if (candidate.precheckFailed) return 'unknown';
  return candidate.overall || 'unknown';
}

/* Best candidate to inspect by default; only a passing best is marked "推荐". */
function summarizeCandidates(data) {
  const list = data.candidates || [];
  const scored = list.map((candidate, index) => {
    const checks = candidate.checks || [];
    return {
      candidate,
      index,
      rank: CANDIDATE_RANK[candidateOutcome(candidate)] ?? 2,
      passed: checks.filter((item) => item.pass === true).length,
      undecided: checks.filter((item) => item.pass === null || item.pass === undefined).length,
    };
  });
  scored.sort((a, b) => a.rank - b.rank || b.passed - a.passed || a.undecided - b.undecided || a.index - b.index);
  const best = scored.length ? scored[0].candidate : null;
  const stats = {
    total: list.length,
    pass: list.filter((candidate) => candidateOutcome(candidate) === 'pass').length,
    partial: list.filter((candidate) => candidateOutcome(candidate) === 'partial').length,
    fail: list.filter((candidate) => candidateOutcome(candidate) === 'fail').length,
    unknown: list.filter((candidate) => candidateOutcome(candidate) === 'unknown').length,
  };
  return {
    best,
    recommendedId: best && candidateOutcome(best) === 'pass' ? best.id : null,
    stats,
  };
}

function candidateBatchLabel(stats) {
  return `${stats.total} 张 · ${stats.pass ? `${stats.pass} 张通过` : '无通过'}`;
}

function renderOptimizer() {
  const shot = STATE.opt.shot;
  const data = normalizeOptData(shot);
  const originalShot = STATE.shots.find((s) => s.id === shot) || STATE.shots[2];
  $('#opt-title').textContent = data.title;
  $('#opt-subtitle').textContent = data.subtitle;
  setPageEyebrow(`OPTIMIZER / ${shot}`);
  $('#opt-issue-context').innerHTML = `<b>${data.contextTitle}</b><p>${data.contextCopy}</p>`;
  $('#opt-prompt').value = data.prompt;
  $('#opt-negative').value = data.negative;
  $('#opt-keypoints').innerHTML = data.keypoints.map((k) => `<p>${icon('check')}${escapeHtml(k)}</p>`).join('');
  $('#opt-cardplan').textContent = data.cardplan;
  const closeMap = { S2: 'assets/shot-2-close.jpg', S3: 'assets/shot-3-close.jpg' };
  $('#opt-original-img').src = closeMap[shot] || originalShot.image;
  $('#opt-diff-note').textContent = data.diff;
  $('#opt-compare').classList.toggle('is-portrait', !!closeMap[shot]);
  $$('#opt-shot-switch button').forEach((b) => {
    const rechecked = Boolean(adoptedCandidateId(b.dataset.shot));
    b.classList.toggle('is-active', b.dataset.shot === shot);
    b.classList.toggle('is-rechecked', rechecked);
    b.title = rechecked ? '该镜头已完成复检，可查看更新后的报告' : '';
  });

  const summary = summarizeCandidates(data);
  const selected = data.candidates.find((c) => c.id === STATE.opt.selected)
    || data.candidates.find((c) => c.id === adoptedCandidateId(shot))
    || summary.best
    || data.candidates[0];
  STATE.opt.selected = selected.id;
  renderCompare(selected);
  renderCandidates(data, selected);
  renderPrecheck(selected, data);
  syncAdoptButton();
  renderOptStatus();
  renderGenerationLog(shot, data);
  if (STATE.screen === 'optimizer') updateTopbarStatus('optimizer');
}

/* Keeps the adopt CTA in sync with the current state: regenerating clears the
   "查看报告" shortcut so the new batch can be adopted and rechecked again. */
function syncAdoptButton() {
  const btn = $('#opt-adopt');
  if (!btn) return;
  const note = $('#adopt-note');
  if (adoptedCandidateId()) {
    /* Once a shot is adopted, viewing the updated report stays available no
       matter which candidate is being compared. */
    btn.innerHTML = `${icon('check')}查看更新后的报告`;
    btn.dataset.nav = 'results';
    btn.disabled = false;
    if (note) note.classList.add('is-success');
  } else {
    btn.innerHTML = `${icon('check')}采用为当前镜头`;
    delete btn.dataset.nav;
    btn.disabled = STATE.opt.status !== 'complete';
    if (note) note.classList.remove('is-success');
  }
}

function renderGenerationLog(shot, data) {
  const adoptedId = adoptedCandidateId(shot);
  const adopted = Boolean(adoptedId);
  const generating = STATE.opt.status === 'generating';
  const prechecking = STATE.opt.status === 'prechecking';
  $('#gen-log-meta').textContent = `GEN-00${shot === 'S3' ? 1 : 2} · ${shot} · 本地记录`;
  const steps = [
    { label: '修正提示词', value: 'v2 · 已锁定期望值', note: '中文提示词', state: 'done' },
    { label: '生成候选', value: generating ? '生成中…' : '4 张 · 35 秒', note: generating ? '等待服务返回' : '每批默认 4 张', state: generating ? 'active' : 'done' },
    { label: '自动预检', value: generating ? '等待中' : prechecking ? '进行中…' : '1 通过 · 1 部分 · 2 待核对', note: '按挑选标准逐项核对', state: generating ? '' : prechecking ? 'active' : 'done' },
    { label: '用户采用', value: adopted ? `${adoptedId} · 已采用` : '待确认', note: adopted ? '原图保留' : '预检不自动采用', state: adopted ? 'done' : 'active' },
    { label: '单镜头复检', value: adopted ? `${shot} · 问题关闭` : '未开始', note: adopted ? '其他镜头未重跑' : '采用后触发', state: adopted ? 'done' : '' },
  ];
  $('#gen-log-track').innerHTML = steps.map((s) => `
    <div class="log-step ${s.state}">
      <span>${s.label}</span><b>${s.value}</b><small>${s.note}</small>
    </div>`).join('');
}

function renderOptStatus() {
  const el = $('#opt-status');
  if (adoptedCandidateId()) { el.className = 'status-pill is-ok'; el.innerHTML = '<i></i>已采用并复检'; return; }
  if (STATE.opt.status === 'generating') { el.className = 'status-pill is-live'; el.innerHTML = '<i></i>生成中'; return; }
  if (STATE.opt.status === 'prechecking') { el.className = 'status-pill is-live'; el.innerHTML = '<i></i>预检中'; return; }
  el.className = 'status-pill is-idle'; el.innerHTML = '<i></i>预检完成 · 待采用';
}

function updateCompareSlider(value) {
  const viewer = $('#opt-compare');
  if (!viewer || !viewer.clientWidth) return;
  const width = viewer.clientWidth;
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  const x = (v / 100) * width;
  const radius = 18;
  const knobX = Math.max(radius, Math.min(width - radius, x));
  const shift = knobX - x;
  $('#opt-after-pane').style.clipPath = `inset(0 0 0 ${v}%)`;
  $('#opt-handle').style.left = `${v}%`;
  const knob = $('#opt-handle span');
  if (knob) knob.style.transform = `translate(calc(-50% + ${shift}px), -50%)`;
}

function renderCompare(candidate) {
  const summary = summarizeCandidates(normalizeOptData(STATE.opt.shot));
  const label = candidate.overall === 'pass'
    ? (summary.recommendedId === candidate.id ? '建议采用' : '预检通过')
    : candidate.label;
  $('#opt-candidate-img').src = candidate.img;
  $('#opt-candidate-img').alt = `候选图 ${candidate.id}`;
  $('#opt-compare-label').textContent = `${candidate.id} · ${label}`;
  $('#opt-range').value = 50;
  updateCompareSlider(50);
}

function renderCandidates(data, selected) {
  if (STATE.opt.status === 'generating') {
    $('#candidate-count').textContent = '生成中 · 0 / 4';
    $('#opt-candidates').innerHTML = Array.from({ length: 4 }).map(() => '<div class="candidate-loading"><div class="candidate-skeleton"></div><div class="candidate-skeleton" style="height:24px"></div></div>').join('');
    return;
  }
  const prechecking = STATE.opt.status === 'prechecking';
  const adoptedId = adoptedCandidateId();
  const summary = summarizeCandidates(data);
  $('#candidate-count').textContent = prechecking ? '4 张 · 正在预检' : candidateBatchLabel(summary.stats);
  $('#opt-candidates').innerHTML = data.candidates.map((c) => {
    const stateClass = c.overall === 'pass' ? 'is-ok' : c.overall === 'partial' ? 'is-warn' : c.overall === 'fail' ? 'is-bad' : 'is-muted';
    const stateLabel = prechecking ? '预检中' : c.state;
    const comparing = selected.id === c.id;
    const recommended = !prechecking && summary.recommendedId === c.id;
    const tagText = comparing && recommended ? '推荐 · 对比中' : comparing ? '对比中' : recommended ? '推荐' : '';
    const copyLabel = prechecking
      ? '正在按挑选标准核对'
      : c.overall === 'pass' && !recommended
        ? '预检通过'
        : c.label;
    return `<button class="candidate-card ${comparing ? 'is-selected' : ''} ${adoptedId === c.id ? 'is-adopted' : ''}" data-candidate="${c.id}">
      <span class="candidate-img"><img src="${c.img}" alt="候选图 ${c.id}"><span class="candidate-badge">${c.id}</span>${tagText ? `<span class="candidate-tag ${comparing ? 'is-comparing' : 'is-reco'}">${comparing && recommended ? '<em class="tag-reco">推荐 · </em>对比中' : escapeHtml(tagText)}</span>` : ''}<span class="candidate-state ${prechecking ? 'is-muted' : stateClass}">${prechecking ? icon('refresh') : c.overall === 'pass' ? icon('check') : c.overall === 'fail' ? icon('alert') : icon('help')}${stateLabel}</span></span>
      <span class="candidate-copy"><b>${escapeHtml(c.summary)}</b><span>${escapeHtml(copyLabel)}</span>${adoptedId === c.id ? `<span class="candidate-adopt-tag">${icon('check')}已采用为当前镜头</span>` : ''}</span>
    </button>`;
  }).join('');
}

function renderPrecheck(candidate, data) {
  const el = $('#opt-precheck');
  const overall = $('#precheck-overall');
  if (STATE.opt.status === 'generating' || STATE.opt.status === 'prechecking') {
    overall.className = 'status-pill is-live';
    overall.innerHTML = '<i></i>预检中';
    $('#precheck-body').innerHTML = `<div class="precheck-summary"><span class="scan-spinner"></span><div><b>正在核对 4 张候选图</b><span>按抽卡标准逐项输出结论与证据</span></div></div>
      <div class="precheck-item"><span class="precheck-check">${icon('minus')}</span><div><b>目标要素与设定一致</b><p>等待预检返回…</p></div></div>
      <div class="precheck-item"><span class="precheck-check">${icon('minus')}</span><div><b>发型轮廓与 S1 一致</b><p>等待预检返回…</p></div></div>
      <div class="precheck-item"><span class="precheck-check">${icon('minus')}</span><div><b>构图与相邻镜头连贯</b><p>等待预检返回…</p></div></div>`;
    $('#adopt-note').textContent = '候选图返回后会自动预检。预检仅为建议，采用前需你确认。';
    $('#opt-adopt').disabled = true;
    return;
  }
  if (candidate.precheckFailed) {
    overall.className = 'status-pill is-warn';
    overall.innerHTML = '<i></i>预检未完成';
    $('#precheck-body').innerHTML = `<div class="precheck-summary" style="border-color:rgba(244,187,103,.18);background:rgba(244,187,103,.035)">${statusIcon('warn')}<div><b style="color:var(--amber)">自动预检未完成，候选图仍可查看和采用；是否采用由你决定。</b><span>本次未获得自动预检结论。</span></div></div>
      <div class="precheck-item"><span class="precheck-check">${icon('check')}</span><div><b>画面清晰，可判断</b><p>候选图可查看。</p></div></div>
      <div class="precheck-item"><span class="precheck-check">${icon('minus')}</span><div><b>目标要素与设定一致</b><p>预检未返回。</p></div></div>
      <div class="precheck-item"><span class="precheck-check">${icon('minus')}</span><div><b>发型轮廓与 S1 一致</b><p>预检未返回。</p></div></div>`;
    $('#adopt-note').textContent = adoptedCandidateId()
      ? `${STATE.opt.shot} 复检完成：问题已关闭。原始镜头已保留，可追溯。`
      : '预检失败不会阻止采用。';
    $('#opt-adopt').disabled = Boolean(adoptedCandidateId());
    return;
  }
  const summary = summarizeCandidates(normalizeOptData(STATE.opt.shot));
  const isRecommended = summary.recommendedId === candidate.id;
  const overallMap = {
    pass: ['is-ok', isRecommended ? '建议采用' : '预检通过', isRecommended ? '预检通过，可作为首选候选' : '满足关键标准，可对比后采用'],
    partial: ['is-warn', '部分符合', '存在无法判断项，需人工确认'],
    fail: ['is-failed', '不建议', '未满足关键挑选标准'],
    unknown: ['is-neutral', '无法判断', '预检信息不足'],
  };
  const [cls, text, copy] = overallMap[candidate.overall] || overallMap.unknown;
  overall.className = `status-pill ${cls}`;
  overall.innerHTML = `<i></i>${text}`;
  $('#precheck-body').innerHTML = `
    <div class="precheck-summary" style="border-color:${candidate.overall === 'pass' ? 'rgba(91,224,176,.16)' : candidate.overall === 'fail' ? 'rgba(255,92,114,.16)' : 'rgba(244,187,103,.16)'};background:${candidate.overall === 'pass' ? 'rgba(91,224,176,.035)' : candidate.overall === 'fail' ? 'rgba(255,92,114,.035)' : 'rgba(244,187,103,.035)'}">
      ${statusIcon(candidate.overall === 'pass' ? 'ok' : candidate.overall === 'fail' ? 'alert' : 'warn')}
      <div><b style="color:${candidate.overall === 'pass' ? 'var(--green)' : candidate.overall === 'fail' ? 'var(--red)' : 'var(--amber)'}">${copy}</b><span>${candidate.id} · ${candidate.overall === 'pass' && isRecommended ? '推荐候选' : '仅作采用建议'}</span></div>
    </div>
    ${candidate.checks.map((c) => {
      const pass = c.pass;
      const cls = pass === true ? 'is-ok' : pass === false ? 'is-bad' : 'is-warn';
      return `<div class="precheck-item">
        <span class="precheck-check ${cls}">${icon(pass === true ? 'check' : pass === false ? 'close' : 'minus')}</span>
        <div><b>${escapeHtml(c.name)}</b><p>${escapeHtml(c.evidence)}</p></div>
      </div>`;
    }).join('')}`;
  const needsOverride = candidate.overall !== 'pass';
  const adopted = Boolean(adoptedCandidateId());
  $('#adopt-note').textContent = adopted
    ? `${shotLabel(STATE.opt.shot)} 已完成复检，问题关闭。原图保留在生成记录中。`
    : needsOverride
      ? `预检不建议采用 ${candidate.id}，仍可人工采用并记录推翻预检结果。采用后将仅复检 ${STATE.opt.shot}，原图保留。`
      : `采用后将仅复检 ${STATE.opt.shot}，并更新总体报告。原图保留，不覆盖。`;
  $('#opt-adopt').disabled = STATE.opt.status !== 'complete' || adopted;
}

function shotLabel(shot) { return shot; }

function selectCandidate(id) {
  STATE.opt.selected = id;
  const data = normalizeOptData(STATE.opt.shot);
  const candidate = data.candidates.find((c) => c.id === id);
  if (!candidate) return;
  renderCompare(candidate);
  renderCandidates(data, candidate);
  renderPrecheck(candidate, data);
  syncAdoptButton();
}

function generateCandidates() {
  if (STATE.opt.status === 'generating' || STATE.opt.status === 'prechecking') return;
  STATE.opt.status = 'generating';
  setAdoptedCandidate(STATE.opt.shot, null);
  renderOptimizer();
  $('#opt-generate').disabled = true;
  $('#opt-generate').innerHTML = `${icon('refresh')}生成中…`;
  toast(`正在为 ${STATE.opt.shot} 生成 4 张候选图`);
  setTimeout(() => {
    STATE.opt.status = 'prechecking';
    renderOptimizer();
    toast('候选图已返回，正在按抽卡标准预检');
  }, 1900);
  setTimeout(() => {
    STATE.opt.status = 'complete';
    STATE.opt.selected = null;
    renderOptimizer();
    $('#opt-generate').disabled = false;
    $('#opt-generate').innerHTML = `${icon('refresh')}重新生成`;
    const summary = summarizeCandidates(normalizeOptData(STATE.opt.shot));
    toast(summary.recommendedId ? `预检完成：${summary.recommendedId} 建议采用` : '预检完成：本批无通过候选，可重抽或人工核对');
  }, 3400);
}

function adoptCandidate() {
  if (adoptedCandidateId() || STATE.opt.status !== 'complete') return;
  const shot = STATE.opt.shot;
  const data = normalizeOptData(shot);
  const candidate = data.candidates.find((c) => c.id === STATE.opt.selected);
  if (!candidate) return;
  const btn = $('#opt-adopt');
  btn.disabled = true;
  btn.innerHTML = `<span class="scan-spinner" style="width:14px;height:14px"></span>正在复检 ${shot}…`;
  $('#adopt-note').textContent = `正在将 ${candidate.id} 设为 ${shot} 当前版本，并仅复检该镜头。`;
  setTimeout(() => {
    setAdoptedCandidate(shot, candidate.id);
    STATE.opt.status = 'complete';
    applyAdoption(shot, data.issueId, candidate.fullImg || candidate.img);
    renderOptimizer();
    $('#adopt-note').textContent = `${shot} 复检完成：问题已关闭。原始镜头已保留，可追溯。`;
    const overrode = candidate.overall !== 'pass';
    toast(`${candidate.id} 已采用${overrode ? '（已记录推翻预检结果）' : ''}，${shot} 复检完成，问题关闭`);
  }, 1700);
}

function applyAdoption(shotId, issueId, image) {
  const issue = STATE.issues.find((i) => i.id === issueId);
  STATE.issues = STATE.issues.filter((i) => i.id !== issueId);
  const shot = STATE.shots.find((s) => s.id === shotId);
  if (shot) shot.image = image;
  const matrixRow = MATRIX.find((r) => r.cells[shotId]?.issue === issueId);
  if (matrixRow) {
    const cell = matrixRow.cells[shotId];
    cell.status = 'ok';
    cell.value = issue?.resolved || cell.value;
    delete cell.issue;
  }
  const observations = OBSERVATIONS[shotId] || [];
  if (issueId === 'ISS-001') {
    const o = observations.find((item) => item.name === '上装颜色');
    if (o) Object.assign(o, { observed: '浅米色', verdict: 'consistent', evidence: '复检后外套主色为浅暖米色，与 S1 一致' });
  }
  if (issueId === 'ISS-002') {
    const o = observations.find((item) => item.name === '配饰');
    if (o) Object.assign(o, { observed: '蓝紫四瓣吊坠', verdict: 'consistent', evidence: '复检后吊坠内部为蓝紫四瓣花，与 S1 一致' });
  }
  renderResults();
}

/* ---------------- settings / history ---------------- */

function testConnection(service) {
  const result = $(`#test-${service}-result`);
  result.hidden = false;
  result.className = 'test-result';
  result.textContent = '正在测试鉴权、网络可达性与额度…';
  setTimeout(() => {
    result.textContent = '连接成功 · 鉴权通过 · 额度可用 · 响应 842ms';
    toast('服务连接测试通过');
  }, 1200);
}

function filterHistory() {
  const search = ($('#history-search')?.value || '').trim().toLowerCase();
  let visible = 0;
  $$('.history-row').forEach((row) => {
    const statusOk = STATE.historyFilter === 'all' || row.dataset.status === STATE.historyFilter;
    const searchOk = !search || (row.dataset.search || '').toLowerCase().includes(search);
    const ok = statusOk && searchOk;
    row.hidden = !ok;
    if (ok) visible++;
  });
  $('#history-empty').hidden = visible > 0;
}

function openModal(title, copy, onConfirm) {
  $('#modal-title').textContent = title;
  $('#modal-copy').textContent = copy;
  $('#modal-backdrop').hidden = false;
  const btn = $('#modal-confirm');
  btn.onclick = () => {
    onConfirm();
    $('#modal-backdrop').hidden = true;
  };
}

/* ---------------- event wiring ---------------- */

document.addEventListener('click', (e) => {
  const nav = e.target.closest('[data-nav]');
  if (nav) {
    e.preventDefault();
    navigate(nav.dataset.nav);
    return;
  }

  const actionEl = e.target.closest('[data-action]');
  if (actionEl) {
    const action = actionEl.dataset.action;
    const message = actionEl.dataset.message;
    if (action === 'toast') { toast(message || '操作已完成'); return; }
    if (action === 'pick-files') { $('#shot-input').click(); return; }
    if (action === 'start-analysis') {
      if ($('#start-analysis').disabled) return;
      startAnalysis();
      return;
    }
    if (action === 'cancel-analysis') { cancelAnalysis(); return; }
    if (action === 'simulate-partial') { simulatePartialFailure(); return; }
    if (action === 'retry-shot') { retryShot(); return; }
    if (action === 'copy-report') {
      const location = STATE.issues.length
        ? `问题定位：${STATE.issues.map((i) => `${i.shot} ${i.short || i.attribute}`).join('、')}。`
        : '所有确定问题已关闭。';
      copyText(`阿岚 · 第一幕：3 个镜头，${STATE.issues.length} 处确定不一致，${STATE.unknowns.length} 项无法判断。${location}`, '报告摘要已复制');
      return;
    }
    if (action === 'open-optimizer') {
      const shot = actionEl.dataset.shot || 'S3';
      STATE.opt.shot = shot;
      STATE.opt.selected = null;
      STATE.opt.status = 'complete';
      showScreen('optimizer');
      return;
    }
    if (action === 'close-notify') { $('#notify-popover').hidden = true; return; }
    if (action === 'test-analysis') { testConnection('analysis'); return; }
    if (action === 'test-generation') { testConnection('generation'); return; }
    if (action === 'generate') { generateCandidates(); return; }
    if (action === 'redraw') { generateCandidates(); return; }
    if (action === 'adopt') { adoptCandidate(); return; }
    if (action === 'clear-data') {
      openModal('清除本地数据', '将删除历史任务、候选图与生成记录。此操作不可撤销。', () => toast('原型模式：本地数据未实际删除'));
      return;
    }
    if (action === 'close-modal') { $('#modal-backdrop').hidden = true; return; }
    if (action === 'close-lightbox') { closeLightbox(); return; }
  }

  const optimizeIssue = e.target.closest('[data-optimize-issue]');
  if (optimizeIssue) {
    const issue = STATE.issues.find((i) => i.id === optimizeIssue.dataset.optimizeIssue);
    const shot = issue ? issue.shot : 'S3';
    STATE.opt.shot = shot;
    STATE.opt.selected = null;
    STATE.opt.status = 'complete';
    showScreen('optimizer');
    return;
  }

  const issueTarget = e.target.closest('[data-issue]');
  if (issueTarget) { selectIssue(issueTarget.dataset.issue); return; }

  const lightboxShot = e.target.closest('[data-lightbox-shot]');
  if (lightboxShot) { openLightbox(lightboxShot.dataset.lightboxShot); return; }

  const locateShotBtn = e.target.closest('[data-locate-shot]');
  if (locateShotBtn) { locateShot(locateShotBtn.dataset.locateShot); return; }

  const galleryShot = e.target.closest('[data-gallery-shot]');
  if (galleryShot) {
    if (e.target.closest('[data-optimize-issue]')) return;
    selectShot(galleryShot.dataset.galleryShot, galleryShot.dataset.cellIssue);
    return;
  }

  const cell = e.target.closest('[data-cell-shot]');
  if (cell) {
    selectShot(cell.dataset.cellShot, cell.dataset.cellIssue || null);
    return;
  }

  const tab = e.target.closest('.tab');
  if (tab) {
    STATE.resultTab = tab.dataset.tab;
    renderTabs();
    return;
  }

  const filter = e.target.closest('[data-status-filter]');
  if (filter) { filterGallery(filter.dataset.statusFilter); return; }

  const analysisShot = e.target.closest('[data-analysis-shot]');
  if (analysisShot) {
    STATE.analysis.viewIndex = Number(analysisShot.dataset.analysisShot);
    STATE.selectedShot = STATE.shots[STATE.analysis.viewIndex]?.id;
    renderAnalysisScreen();
    return;
  }

  const candidate = e.target.closest('[data-candidate]');
  if (candidate) { selectCandidate(candidate.dataset.candidate); return; }

  const shotSwitch = e.target.closest('[data-shot]');
  if (shotSwitch && e.target.closest('#opt-shot-switch')) {
    STATE.opt.shot = shotSwitch.dataset.shot;
    STATE.opt.selected = null;
    STATE.opt.status = 'complete';
    renderOptimizer();
    return;
  }

  const copyBtn = e.target.closest('[data-copy]');
  if (copyBtn) {
    const el = document.getElementById(copyBtn.dataset.copy);
    copyText(el.value, '提示词已复制');
    return;
  }

  const copySuggestion = e.target.closest('[data-copy-suggestion]');
  if (copySuggestion) {
    const suggestion = SUGGESTIONS.find((s) => s.issueId === copySuggestion.dataset.copySuggestion);
    if (suggestion) copyText(suggestion.prompt, '修正提示词已复制');
    return;
  }

  const exportBtn = e.target.closest('[data-export]');
  if (exportBtn) { exportReport(exportBtn.dataset.export); return; }

  const removeShot = e.target.closest('[data-remove-shot]');
  if (removeShot) {
    STATE.shots = STATE.shots.filter((s) => s.id !== removeShot.dataset.removeShot);
    STATE.shots.forEach((s, i) => { s.id = `S${i + 1}`; });
    renderShots();
    toast('已移除镜头');
    return;
  }

  const moveShot = e.target.closest('[data-move-shot]');
  if (moveShot) {
    const idx = STATE.shots.findIndex((s) => s.id === moveShot.dataset.moveShot);
    const dir = Number(moveShot.dataset.dir);
    const target = idx + dir;
    if (idx >= 0 && target >= 0 && target < STATE.shots.length) {
      [STATE.shots[idx], STATE.shots[target]] = [STATE.shots[target], STATE.shots[idx]];
      STATE.shots.forEach((s, i) => { s.id = `S${i + 1}`; });
      renderShots();
      toast('镜头顺序已更新，编号已重排');
    }
    return;
  }

  const historyFilter = e.target.closest('[data-filter]');
  if (historyFilter) {
    STATE.historyFilter = historyFilter.dataset.filter;
    $$('#history-filters .chip').forEach((c) => c.classList.toggle('is-active', c === historyFilter));
    filterHistory();
    return;
  }

  const batch = e.target.closest('#batch-seg [data-count]');
  if (batch) {
    STATE.batch = Number(batch.dataset.count);
    $$('#batch-seg button').forEach((b) => b.classList.toggle('is-active', b === batch));
    toast(`默认生成张数已设为 ${STATE.batch} 张`);
    return;
  }

  if (e.target.closest('#notify-btn')) {
    const pop = $('#notify-popover');
    pop.hidden = !pop.hidden;
    $('#notify-btn').setAttribute('aria-expanded', String(!pop.hidden));
    return;
  }
  if (!e.target.closest('#notify-popover')) $('#notify-popover').hidden = true;
});

$('#character-input').addEventListener('input', () => {
  renderParsedAttributes();
  parseScript();
});
$('#script-input').addEventListener('input', parseScript);
$$('.template-row .chip').forEach((chip) => chip.addEventListener('click', () => {
  const template = chip.dataset.template;
  setScriptLock(template === 'none');
  $('#script-input').value = SCRIPT_TEMPLATES[template];
  parseScript();
  if (template === 'change') {
    $('#script-input').focus();
    toast('请写明变化的镜头与具体要素，如「S2 发色变为红褐色」');
  }
}));

let draggedShotId = null;
document.addEventListener('dragstart', (e) => {
  const card = e.target.closest('[data-shot-card]');
  if (card) {
    draggedShotId = card.dataset.shotCard;
    e.dataTransfer.effectAllowed = 'move';
    card.classList.add('is-dragging');
  }
});
document.addEventListener('dragend', (e) => {
  const card = e.target.closest('[data-shot-card]');
  if (card) card.classList.remove('is-dragging');
  draggedShotId = null;
});
document.addEventListener('dragover', (e) => {
  const card = e.target.closest('[data-shot-card]');
  if (card && draggedShotId) { e.preventDefault(); card.classList.add('is-drag-over'); }
});
document.addEventListener('dragleave', (e) => {
  const card = e.target.closest('[data-shot-card]');
  if (card) card.classList.remove('is-drag-over');
});
document.addEventListener('drop', (e) => {
  const card = e.target.closest('[data-shot-card]');
  if (!card || !draggedShotId) return;
  e.preventDefault();
  card.classList.remove('is-drag-over');
  const from = STATE.shots.findIndex((s) => s.id === draggedShotId);
  const to = STATE.shots.findIndex((s) => s.id === card.dataset.shotCard);
  if (from < 0 || to < 0 || from === to) return;
  const [moved] = STATE.shots.splice(from, 1);
  STATE.shots.splice(to, 0, moved);
  STATE.shots.forEach((s, i) => { s.id = `S${i + 1}`; });
  draggedShotId = null;
  renderShots();
  toast('镜头顺序已更新，编号已重排');
});

$('#dropzone').addEventListener('dragover', (e) => { e.preventDefault(); $('#dropzone').classList.add('is-dragover'); });
$('#dropzone').addEventListener('dragleave', () => $('#dropzone').classList.remove('is-dragover'));
$('#dropzone').addEventListener('drop', (e) => {
  e.preventDefault();
  $('#dropzone').classList.remove('is-dragover');
  addFiles(e.dataTransfer.files);
});
$('#shot-input').addEventListener('change', (e) => { addFiles(e.target.files); e.target.value = ''; });
$('#history-search').addEventListener('input', filterHistory);

$('#opt-range').addEventListener('input', (e) => updateCompareSlider(e.target.value));
window.addEventListener('resize', () => {
  const range = document.querySelector('#opt-range');
  if (range) updateCompareSlider(range.value);
});

$('#lightbox').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closeLightbox();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    $('#modal-backdrop').hidden = true;
    $('#notify-popover').hidden = true;
    closeLightbox();
  }
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[data-issue][role="button"]')) {
    e.preventDefault();
    selectIssue(e.target.dataset.issue);
  }
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('#notify-popover') && !e.target.closest('#notify-btn')) {
    $('#notify-popover').hidden = true;
  }
});

/* ---------------- boot ---------------- */

renderParsedAttributes();
setScriptLock(true);
parseScript();
renderShots();
renderPipeline();

const bootScreen = window.location.hash.replace('#', '');
if (bootScreen && SCREEN_META[bootScreen]) {
  navigate(bootScreen);
} else {
  showScreen('home');
}

window.addEventListener('hashchange', () => {
  const name = window.location.hash.replace('#', '');
  if (SCREEN_META[name] && name !== STATE.screen) navigate(name);
  else if (name && !SCREEN_META[name]) showScreen('home');
});

/* Prototype inspection hook, useful for QA and demos from the console. */
window.__CCS = {
  STATE,
  navigate,
  showScreen,
  startAnalysis,
  renderAnalysisScreen,
  updateAnalysisClock,
  updateTaskPill,
  resetAnalysisView,
  renderResults,
  renderOptimizer,
};
