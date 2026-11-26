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
  shots: DEMO_SHOTS.map((s) => ({ ...s })),
  attributes: [],
  issues: [
    {
      id: 'ISS-001',
      shot: 'S2',
      attribute: '上装颜色',
      short: '外套偏冷灰',
      title: '上装颜色不一致 · 浅暖米色在冷光下变成冷灰米色',
      expected: '浅米色（暖调）',
      observed: '冷灰米色',
      evidence: 'S2 外套在窗边冷光下明显偏冷灰，暖调不足，与 S1/S3 的浅暖米色不一致。',
      severity: '中',
      severityValue: 'medium',
      confidence: '高',
      confidenceValue: 'high',
      resolved: '浅米色',
      waiver: '不适用（剧本说明三镜头无换装）',
      type: '违反设定',
    },
    {
      id: 'ISS-002',
      shot: 'S3',
      attribute: '配饰',
      short: '吊坠图案不符',
      title: '配饰细节不一致 · 蓝紫四瓣吊坠变成红橙五瓣',
      expected: '蓝紫四瓣花吊坠',
      observed: '红橙五瓣花吊坠',
      evidence: 'S3 吊坠轮廓与 S1 相同，但内部图案为红橙五瓣花，与设定的蓝紫四瓣花不一致。',
      severity: '中',
      severityValue: 'medium',
      confidence: '高',
      confidenceValue: 'high',
      resolved: '蓝紫四瓣吊坠',
      waiver: '不适用（无摘换配饰情节）',
      type: '违反设定',
    },
  ],
  unknowns: [
    { id: 'UNK-001', shot: 'S1', attribute: '下装款式', reason: '画面仅至胸口，下装未入画。' },
    { id: 'UNK-002', shot: 'S2', attribute: '下装款式', reason: '画面仅至腰部，下装未入画。' },
    { id: 'UNK-003', shot: 'S2', attribute: '项链', reason: '侧身角度下胸前被衣领遮挡，无法确认项链是否存在。' },
    { id: 'UNK-004', shot: 'S3', attribute: '下装款式', reason: '下半身被桌沿遮挡。' },
    { id: 'UNK-005', shot: 'S1', attribute: '下装颜色', reason: '画面仅至胸口，下装颜色未入画。' },
    { id: 'UNK-006', shot: 'S2', attribute: '下装颜色', reason: '画面仅至腰部，下装颜色未入画。' },
    { id: 'UNK-007', shot: 'S3', attribute: '下装颜色', reason: '下半身被桌沿遮挡。' },
    { id: 'UNK-008', shot: 'S1', attribute: '鞋履', reason: '画面仅至胸口，鞋履未入画。' },
    { id: 'UNK-009', shot: 'S2', attribute: '鞋履', reason: '画面仅至腰部，鞋履未入画。' },
    { id: 'UNK-010', shot: 'S3', attribute: '鞋履', reason: '下半身被桌沿遮挡。' },
    { id: 'UNK-011', shot: 'S1', attribute: '下装图案', reason: '画面仅至胸口，下装图案未入画。' },
    { id: 'UNK-012', shot: 'S2', attribute: '下装图案', reason: '画面仅至腰部，下装图案未入画。' },
    { id: 'UNK-013', shot: 'S3', attribute: '下装图案', reason: '下半身被桌沿遮挡。' },
  ],
  selectedShot: 'S3',
  selectedIssue: 'ISS-002',
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
    statuses: ['pending', 'pending', 'pending'],
    observedCounts: [0, 0, 0],
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
    progress: 0, stage: 0, statuses: ['pending', 'pending', 'pending'],
    observedCounts: [0, 0, 0],
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
  { name: '设定解析', hint: '正在提取角色设定中的发型、服装与配饰' },
  { name: '剧本解析', hint: '正在核对镜头说明与允许的局部变化' },
  { name: '逐镜头观察', hint: '正在逐镜头观察发型、服装与配饰' },
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

function showScreen(name) {
  if (!SCREEN_META[name]) return;
  STATE.screen = name;
  $$('.screen').forEach((s) => s.classList.toggle('is-active', s.id === `screen-${name}`));
  const navKey = name === 'results' || name === 'optimizer' ? 'analysis' : name;
  $$('.nav-item[data-nav]').forEach((b) => b.classList.toggle('is-active', b.dataset.nav === navKey));
  const meta = SCREEN_META[name];
  $('#page-title').textContent = meta.title;
  setPageEyebrow(meta.eyebrow);
  $('#page-subtitle').textContent = meta.sub;
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
    el.className = `status-pill ${cls}`;
    el.innerHTML = `<i></i>${text}`;
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
  const name = nameMatch ? nameMatch[1] : '阿岚';

  const colors = ['浅米色', '米色', '黄色', '蓝色', '深蓝色', '深蓝', '藏青', '天蓝', '红色', '黑色', '白色', '灰色', '绿色', '紫色', '棕色', '卡其色', '牛仔蓝'];
  const nearestColor = (pattern) => {
    const match = pattern.exec(text);
    if (!match) return null;
    const target = match.index + match[0].length / 2;
    const matches = [];
    colors.forEach((color) => {
      let at = text.indexOf(color);
      while (at !== -1) {
        matches.push({ color, at, end: at + color.length });
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
    return bestDistance <= 12 ? best : null;
  };

  const hair = /低侧发髻|低髻/.test(text) ? '低侧发髻' : /短发/.test(text) ? '短发' : /长发/.test(text) ? '长发' : /齐肩/.test(text) ? '齐肩发' : null;
  attrs.push({ label: '发型', value: hair, defined: !!hair });
  const hairColor = /深棕|棕色/.test(text) ? '深棕' : /黑发|黑色头发/.test(text) ? '黑色' : /金发/.test(text) ? '金色' : null;
  attrs.push({ label: '发色', value: hairColor, defined: !!hairColor });

  const patternTokens = [
    ['纯色', ['纯色', '素色']],
    ['条纹', ['条纹']],
    ['格纹', ['格纹', '格子']],
    ['印花', ['印花']],
    ['logo', ['logo', 'LOGO', 'Logo']],
  ];
  const nearestPattern = (pattern) => {
    const match = pattern.exec(text);
    if (!match) return null;
    const target = match.index + match[0].length / 2;
    let best = null;
    let bestDistance = Infinity;
    patternTokens.forEach(([value, words]) => {
      words.forEach((word) => {
        let at = text.indexOf(word);
        while (at !== -1) {
          const distance = Math.abs(at + word.length / 2 - target);
          if (distance < bestDistance) { bestDistance = distance; best = value; }
          at = text.indexOf(word, at + 1);
        }
      });
    });
    return bestDistance <= 12 ? best : null;
  };

  const topGarmentPattern = /亚麻西装外套|西装外套|外套|卫衣|衬衫|毛衣|连衣裙/;
  const topPattern = nearestPattern(topGarmentPattern);
  const style = /西装/.test(text) ? (/亚麻/.test(text) ? '亚麻西装外套' : '西装外套') : /卫衣/.test(text) ? '卫衣' : /衬衫/.test(text) ? '衬衫' : /毛衣/.test(text) ? '毛衣' : /外套/.test(text) ? '外套' : /连衣裙/.test(text) ? '连衣裙' : null;
  const topColor = nearestColor(topGarmentPattern);
  attrs.push({ label: '上装款式', value: style, defined: !!style });
  attrs.push({ label: '上装颜色', value: topColor, defined: !!topColor });
  attrs.push({ label: '上装图案', value: topPattern, defined: !!topPattern });

  const bottomGarmentPattern = /背带裤|长裤|短裤|裙子|半身裙/;
  const bottomStyle = /背带裤/.test(text) ? '背带裤' : /长裤/.test(text) ? '长裤' : /短裤/.test(text) ? '短裤' : /裙子|半身裙/.test(text) ? '裙子' : null;
  const bottomColor = nearestColor(bottomGarmentPattern);
  const bottomPattern = nearestPattern(bottomGarmentPattern);
  attrs.push({ label: '下装款式', value: bottomStyle, defined: !!bottomStyle });
  attrs.push({ label: '下装颜色', value: bottomColor, defined: !!bottomColor });
  attrs.push({ label: '下装图案', value: bottomPattern, defined: !!bottomPattern });

  const accessory = /无围巾/.test(text) ? '无围巾' : /围巾/.test(text) ? '围巾' : /眼镜/.test(text) ? '眼镜' : /项链/.test(text) ? (/圆形|吊坠/.test(text) ? '圆形吊坠项链' : '项链') : null;
  attrs.push({ label: '配饰', value: accessory, defined: !!accessory });

  const shoePattern = /高跟鞋|运动鞋|皮鞋|靴子|平底鞋|凉鞋|乐福鞋/;
  const shoeStyle = /高跟鞋/.test(text) ? '高跟鞋' : /运动鞋/.test(text) ? '运动鞋' : /皮鞋/.test(text) ? '皮鞋' : /靴子/.test(text) ? '靴子' : /平底鞋/.test(text) ? '平底鞋' : /凉鞋/.test(text) ? '凉鞋' : /乐福鞋/.test(text) ? '乐福鞋' : null;
  const shoeColor = nearestColor(shoePattern);
  attrs.push({ label: '鞋履', value: shoeStyle ? (shoeColor ? `${shoeColor}${shoeStyle}` : shoeStyle) : null, defined: !!shoeStyle });

  const props = [];
  if (/咖啡杯|马克杯/.test(text)) props.push('咖啡杯');
  if (/雨伞/.test(text)) props.push('雨伞');
  if (/书本|书籍/.test(text)) props.push('书本');
  if (/刀|剑|枪/.test(text)) props.push('武器');
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
  $('#current-task-name').textContent = `${parseCharacter(text).name} · 第一幕`;
  updateCreateValidation();
}

const SCRIPT_RULE_ITEMS = [
  { label: '发型', changeable: false },
  { label: '发色', changeable: false },
  { label: '上装款式', changeable: true },
  { label: '上装颜色', changeable: true },
  { label: '上装图案', changeable: true },
  { label: '下装款式', changeable: true },
  { label: '下装颜色', changeable: true },
  { label: '下装图案', changeable: true },
  { label: '配饰', changeable: false },
  { label: '鞋履', changeable: true },
  { label: '道具', changeable: false },
];

const SCRIPT_TEMPLATES = {
  none: '这些镜头为同一场戏的连续动作，无换装情节。',
  change: 'S3 换装为深色外套，其余镜头保持原服装与配饰。',
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

function extractChangeTargets(text) {
  const refs = new Set();
  for (const m of text.matchAll(/换装|换成|改为/g)) {
    const before = text.slice(0, m.index).split(/[，,。；;！!？?\n]/).pop() || '';
    const after = text.slice(m.index).split(/[，,。；;！!？?\n]/)[0] || '';
    for (const seg of [before, after]) {
      for (const r of seg.matchAll(/(?:S\s*([1-9])|第\s*([1-9])\s*个?镜头|镜头\s*([1-9]))/gi)) {
        refs.add(`S${r[1] || r[2] || r[3]}`);
      }
    }
  }
  return [...refs];
}

function renderScriptRules(mode, targets) {
  const defined = new Map((STATE.attributes || []).map((a) => [a.label, a.defined]));
  const targetLabel = targets.length ? targets.join('、') : '该镜头';
  $('#script-rule-grid').innerHTML = SCRIPT_RULE_ITEMS.map((item) => {
    if (defined.get(item.label) === false) {
      return `<div class="rule-item is-undef"><span>${icon('minus')}<b>${item.label}</b></span><span class="rule-state">设定未定义 · 不比对</span></div>`;
    }
    if (mode === 'change' && item.changeable) {
      return `<div class="rule-item is-open"><span>${icon('check')}<b>${item.label}</b></span><span class="rule-state">${targetLabel} 允许变化</span></div>`;
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
  const noChange = /无换装|没有换装|不换装/.test(text);
  const mentionsChange = /换装|换成|改为/.test(text);
  const targets = mentionsChange ? extractChangeTargets(text) : [];

  const mode = !text ? 'empty' : noChange ? 'none' : targets.length ? 'change' : mentionsChange ? 'unlocated' : 'strict';

  const badge = $('#script-mode');
  const tone = mode === 'change' ? 'is-allow' : mode === 'unlocated' || mode === 'empty' ? 'is-warn' : 'is-strict';
  badge.className = `rule-badge ${tone}`;
  badge.textContent = mode === 'change'
    ? '局部豁免 · 其余严格'
    : mode === 'unlocated'
      ? '待定位 · 暂不豁免'
      : mode === 'empty'
        ? '待填写 · 暂不豁免'
        : '严格比对 · 无豁免';

  const targetLabel = targets.length ? targets.join('、') : '该镜头';
  const notes = {
    none: '剧情未允许换装：以下要素在全部镜头中按角色设定严格比对。',
    change: `已识别 ${targetLabel} 换装：仅 ${targetLabel} 的上装、下装与鞋履允许变化，其余要素仍严格比对。`,
    unlocated: '描述中出现换装，但没有写明镜头号，无法建立豁免：以下要素暂按不允许变化处理。',
    empty: '剧本说明为空：填写前以下要素全部按严格比对处理。',
    strict: '未检测到允许变化的描述：以下要素在全部镜头中按角色设定严格比对。',
  };
  const foots = {
    none: '',
    change: `豁免只作用于 ${targetLabel} 的上装、下装与鞋履；发型、发色、配饰与道具仍逐镜头比对。`,
    unlocated: '补充镜头号与变化项后可建立豁免，例如「S3 换装为深色外套」。',
    empty: '示例：「S3 换装为深色外套，其余镜头保持原服装与配饰。」',
    strict: '光线、角度与场景切换不构成豁免；只有写明的换装才允许局部变化。',
  };

  $('#script-rule-note').textContent = notes[mode];
  const footEl = $('#script-rule-foot');
  footEl.textContent = foots[mode];
  footEl.hidden = !foots[mode];
  $('#script-warning').hidden = mode !== 'unlocated';
  renderScriptRules(mode, targets);
  syncScriptChips(mode);
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
  $('#estimate-time').textContent = `${STATE.shots.length} 张 · 约 ${Math.max(20, STATE.shots.length * 15)} 秒`;
  updateCreateValidation();
}

function updateCreateValidation() {
  const charOk = $('#character-input').value.trim().length > 0;
  const scriptOk = $('#script-input').value.trim().length > 0;
  const shotsOk = STATE.shots.length > 0;
  $('#check-character').className = `check-item ${charOk ? 'is-done' : 'is-missing'}`;
  $('#check-script').className = `check-item ${scriptOk ? 'is-done' : 'is-missing'}`;
  $('#check-shots').className = `check-item ${shotsOk ? 'is-done' : 'is-missing'}`;
  $('#check-shots-text').textContent = `${STATE.shots.length} 张镜头`;
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
    const shot = { id, image, file: file.name, quality: 'warn', qualityLabel: '读取中 · 校验中', note: '待填写镜头备注', progress: 22 };
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
  }[phase] || ['is-idle', '待开始'];
}

function updateTaskPill() {
  if (STATE.screen !== 'analysis') return;
  const el = $('#task-status-pill');
  if (!el) return;
  const [cls, text] = analysisPhasePill();
  el.className = `status-pill ${cls}`;
  el.innerHTML = `<i></i>${text}`;
}

function padStage(n) {
  return String(n).padStart(2, '0');
}

function shotObservationStats(shotId) {
  const list = OBSERVATIONS[shotId] || [];
  return {
    total: list.length,
    unknown: list.filter((item) => item.verdict === 'unknown').length,
    inconsistent: list.filter((item) => item.verdict === 'inconsistent').length,
  };
}

function visibleObservationCount(index) {
  const shot = STATE.shots[index];
  const total = (OBSERVATIONS[shot?.id] || []).length;
  const status = STATE.analysis.statuses[index] || 'pending';
  if (status === 'pending') return 0;
  if (status === 'analyzing') return Math.min(total, Math.max(3, STATE.analysis.observedCounts[index] || 0));
  return total;
}

function analyzingBadgeNote(index) {
  const observations = OBSERVATIONS[STATE.shots[index]?.id] || [];
  const count = visibleObservationCount(index);
  const current = observations[count - 1];
  return current
    ? `正在观察：${current.name} · ${count} / ${observations.length}`
    : '正在逐项观察画面';
}

function shotStateMeta(status, shotId) {
  if (status === 'ok' || status === 'issue') {
    const { inconsistent } = shotObservationStats(shotId);
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

function pendingShotNote(index) {
  if (STATE.analysis.stage < 3) return '等待逐镜头观察开始';
  return index === 0 ? '即将开始观察' : '等待前序镜头完成';
}

function shotDetailText(status, shotId, index) {
  const stats = shotObservationStats(shotId);
  if (status === 'pending') return pendingShotNote(index);
  if (status === 'analyzing') return '正在逐项观察画面';
  if (status === 'failed') return '响应超时 · 可重新观察';
  return `${stats.unknown} 项无法判断`;
}

function updateAnalysisHeader() {
  const a = STATE.analysis;
  const shots = STATE.shots;
  const total = shots.length;
  const name = parseCharacter($('#character-input').value).name;
  const stageIndex = Math.max(0, Math.min(a.stage, ANALYSIS_STAGES.length - 1));
  const stage = ANALYSIS_STAGES[stageIndex];
  const done = a.statuses.filter((status) => status === 'ok' || status === 'issue').length;
  const analyzingIdx = a.statuses.indexOf('analyzing');
  const failedIdx = a.statuses.indexOf('failed');
  const analyzingShot = analyzingIdx >= 0 ? shots[analyzingIdx] : null;
  const failedShot = failedIdx >= 0 ? shots[failedIdx] : null;
  const observedTotal = Object.values(OBSERVATIONS).reduce((sum, list) => sum + list.length, 0);
  const paused = a.phase === 'paused';

  $('#analysis-current-title').textContent = paused
    ? `${name}的连续镜头分析已暂停`
    : a.complete
      ? `${name}的连续镜头分析已完成`
      : `正在分析${name}的连续镜头`;
  const kicker = $('#analysis-kicker');
  if (kicker) {
    kicker.textContent = paused ? 'ANALYSIS PAUSED' : a.complete ? 'ANALYSIS COMPLETE' : 'LIVE ANALYSIS';
  }
  if (STATE.screen === 'analysis') {
    setPageEyebrow(paused
      ? 'TASK / PAUSED'
      : a.complete
        ? 'TASK / COMPLETED'
        : a.phase === 'retrying'
          ? 'TASK / RETRYING'
          : 'TASK / ANALYZING');
  }

  let subline;
  if (paused) {
    subline = `分析暂停 · ${failedShot ? failedShot.id : '当前镜头'} 观察失败 · 其他镜头结果已保留`;
  } else if (a.phase === 'retrying') {
    subline = `逐镜头观察 · 正在重新观察 ${shots[a.viewIndex] ? shots[a.viewIndex].id : '当前镜头'}`;
  } else if (a.complete) {
    subline = `分析完成 · ${STATE.issues.length} 处确定不一致 · ${STATE.unknowns.length} 项无法判断`;
  } else if (stageIndex === 0) {
    subline = `素材校验 · 正在检查 ${total} 张镜头的格式、清晰度与可用性`;
  } else if (stageIndex === 1) {
    subline = `设定解析 · 正在提取${name}的发型、服装与配饰设定`;
  } else if (stageIndex === 2) {
    subline = '剧本解析 · 正在核对镜头说明与允许的局部变化';
  } else if (stageIndex === 3) {
    subline = `逐镜头观察 · 已完成 ${done} / ${total}${analyzingShot ? ` · ${analyzingShot.id} 观察中` : ''}`;
  } else if (stageIndex === 4) {
    subline = `一致性判定 · 已比对 ${observedTotal} 项观察记录`;
  } else {
    subline = `生成建议 · 正在为 ${STATE.issues.length} 处不一致整理修正方案`;
  }
  $('#analysis-subline').textContent = subline;

  const stagePill = $('#analysis-stage-pill');
  stagePill.className = `status-pill ${a.complete ? 'is-ok' : paused ? 'is-alert' : 'is-live'}`;
  $('#analysis-stage-label').textContent = `${padStage(stageIndex + 1)} / ${padStage(ANALYSIS_STAGES.length)} · ${stage.name}`;

  const demoBtn = $('[data-action="simulate-partial"]');
  const cancelBtn = $('[data-action="cancel-analysis"]');
  if (demoBtn) demoBtn.hidden = a.complete;
  if (cancelBtn) cancelBtn.hidden = a.complete;

  $('#pipeline-status').textContent = paused
    ? `已暂停在 ${padStage(stageIndex + 1)} / ${padStage(ANALYSIS_STAGES.length)} · ${stage.name}`
    : `已完成 ${a.complete ? ANALYSIS_STAGES.length : stageIndex} / ${ANALYSIS_STAGES.length} 个阶段`;
}

function setAnalysisProgress(progress, stage, eta) {
  const a = STATE.analysis;
  a.progress = progress;
  a.stage = stage;
  $('#analysis-progress').style.width = `${progress}%`;
  $('#analysis-progress').parentElement.setAttribute('aria-valuenow', String(Math.round(progress)));
  $('#analysis-progress-text').textContent = `进度 ${Math.round(progress)}%`;
  if (eta !== undefined) {
    const terminal = eta === 'done' || eta === 'paused';
    $('#analysis-eta-label').textContent = terminal ? '任务状态' : '预计剩余';
    $('#analysis-eta').textContent = eta === 'done' ? '已完成' : eta === 'paused' ? '已暂停' : eta;
  }
  updateAnalysisHeader();
  renderPipeline();
  const scanning = a.phase === 'running' && stage >= 3 && stage <= 4;
  $('#analysis-scan').classList.toggle('is-running', scanning);
  const label = $('#analysis-stage-label');
  label.classList.remove('is-flash');
  void label.offsetWidth;
  label.classList.add('is-flash');
}

function startObservationReveal(index) {
  const a = STATE.analysis;
  const total = (OBSERVATIONS[STATE.shots[index]?.id] || []).length;
  a.observedCounts[index] = Math.min(3, total);
  for (let count = 4; count <= total; count += 1) {
    STATE.analysis.timers.push(setTimeout(() => {
      if (STATE.analysis.statuses[index] !== 'analyzing') return;
      STATE.analysis.observedCounts[index] = count;
      if (STATE.screen === 'analysis' && STATE.analysis.viewIndex === index) {
        renderInsights(index, true);
        const body = $('.analysis-insights .insight-body');
        if (body) body.scrollTop = body.scrollHeight;
        const badgeNote = $('#analysis-badge small');
        if (badgeNote) badgeNote.textContent = analyzingBadgeNote(index);
      }
    }, (count - 3) * 300));
  }
}

function startAnalysis() {
  clearAnalysisTimers();
  const a = STATE.analysis;
  a.started = true;
  a.complete = false;
  a.phase = 'running';
  a.current = 0;
  a.viewIndex = 0;
  a.stage = 0;
  a.progress = 0;
  a.statuses = ['pending', 'pending', 'pending'];
  a.observedCounts = [0, 0, 0];
  insightScrollShot = null;
  STATE.selectedShot = STATE.shots[0]?.id || 'S1';
  showScreen('analysis');
  setAnalysisProgress(3, 0, '约 18 秒');
  renderAnalysisScreen();
  updateTaskPill();

  const T = (delay, fn) => STATE.analysis.timers.push(setTimeout(fn, delay));

  T(900, () => setAnalysisProgress(10, 1, '约 16 秒'));
  T(2100, () => setAnalysisProgress(19, 2, '约 15 秒'));
  T(3500, () => {
    a.statuses = ['analyzing', 'pending', 'pending'];
    a.current = 0;
    a.viewIndex = 0;
    startObservationReveal(0);
    setAnalysisProgress(30, 3, '约 13 秒');
    renderAnalysisScreen();
  });
  T(6100, () => {
    a.statuses = ['ok', 'analyzing', 'pending'];
    a.current = 1;
    a.viewIndex = 1;
    STATE.selectedShot = 'S2';
    startObservationReveal(1);
    setAnalysisProgress(45, 3, '约 11 秒');
    renderAnalysisScreen();
  });
  T(8900, () => {
    a.statuses = ['ok', 'issue', 'analyzing'];
    a.current = 2;
    a.viewIndex = 2;
    STATE.selectedShot = 'S3';
    startObservationReveal(2);
    setAnalysisProgress(60, 3, '约 8 秒');
    renderAnalysisScreen();
  });
  T(11700, () => {
    a.statuses = ['ok', 'issue', 'issue'];
    a.current = 2;
    setAnalysisProgress(76, 4, '约 5 秒');
    renderAnalysisScreen();
    resetInsightScroll();
  });
  T(13500, () => setAnalysisProgress(88, 5, '约 3 秒'));
  T(15500, () => setAnalysisProgress(96, 5, '约 2 秒'));
  T(17000, () => {
    a.complete = true;
    a.phase = 'complete';
    a.statuses = ['ok', 'issue', 'issue'];
    setAnalysisProgress(100, 5, 'done');
    renderAnalysisScreen();
    resetInsightScroll();
    updateTaskPill();
    toast(`分析完成 · ${STATE.issues.length} 处确定不一致 · ${STATE.unknowns.length} 项无法判断`);
  });
}

function simulatePartialFailure() {
  if (!STATE.analysis.started) { toast('请先开始分析，再演示异常状态'); return; }
  clearAnalysisTimers();
  const a = STATE.analysis;
  a.complete = false;
  a.phase = 'paused';
  a.statuses = ['ok', 'failed', 'issue'];
  a.current = 1;
  a.viewIndex = 1;
  STATE.selectedShot = 'S2';
  setAnalysisProgress(74, 3, 'paused');
  renderAnalysisScreen();
  updateTaskPill();
  toast('演示状态：S2 观察失败，可单独重新观察');
}

function retryShot() {
  const a = STATE.analysis;
  const i = a.viewIndex;
  const shot = STATE.shots[i];
  if (!shot) return;
  a.phase = 'retrying';
  a.complete = false;
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
    setAnalysisProgress(fullyDone ? 100 : 88, fullyDone ? 5 : 4, fullyDone ? 'done' : '约 3 秒');
    renderAnalysisScreen();
    resetInsightScroll();
    updateTaskPill();
    toast(`${shot.id} 重新观察完成 · 其他镜头未重跑`);
  }, 2600));
}

function cancelAnalysis() {
  clearAnalysisTimers();
  const a = STATE.analysis;
  a.started = false;
  a.complete = false;
  a.phase = 'idle';
  a.stage = 0;
  a.progress = 0;
  a.statuses = ['pending', 'pending', 'pending'];
  a.observedCounts = [0, 0, 0];
  $('#analysis-result-cta').hidden = true;
  $('#analysis-scan').classList.remove('is-running');
  setAnalysisProgress(0, 0, '约 18 秒');
  showScreen('create');
  toast('已取消分析，已录入的素材保留');
}

let insightScrollShot = null;

function syncInsightScroll(shotId) {
  if (insightScrollShot === shotId) return;
  insightScrollShot = shotId;
  const body = $('.analysis-insights .insight-body');
  if (body) body.scrollTop = 0;
}

function resetInsightScroll() {
  const body = $('.analysis-insights .insight-body');
  if (body) body.scrollTop = 0;
}

function renderAnalysisBadge(status, shot, index) {
  const stats = shotObservationStats(shot.id);
  let cls = 'is-idle';
  let orb = `<span class="badge-glyph">${icon('clock')}</span>`;
  let title = '待观察';
  let note = pendingShotNote(index);
  if (status === 'analyzing') {
    cls = 'is-live';
    orb = '<span class="scan-spinner"></span>';
    title = '观察中';
    note = analyzingBadgeNote(index);
  } else if (status === 'failed') {
    cls = 'is-alert';
    orb = `<span class="badge-glyph">${icon('alert')}</span>`;
    title = '观察失败';
    note = '响应超时 · 可重新观察该镜头';
  } else if (status === 'ok' || status === 'issue') {
    const issue = stats.inconsistent > 0;
    cls = issue ? 'is-alert' : 'is-done';
    orb = `<span class="badge-glyph">${icon(issue ? 'alert' : 'check')}</span>`;
    title = issue ? `${stats.inconsistent} 处不一致` : '全部一致';
    note = `${stats.unknown} 项无法判断 · 证据已记录`;
  }
  const badge = $('#analysis-badge');
  badge.className = `preview-analysis-badge ${cls}`;
  badge.innerHTML = `<span class="badge-orb">${orb}</span><div><b>${title}</b><small>${note}</small></div>`;
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
  chip.className = `preview-chip ${cls}`;
  $('#preview-chip-text').textContent = text;
}

function updateInsightPill(status, shotId) {
  const meta = shotStateMeta(status, shotId);
  const el = $('#insight-state-pill');
  el.className = `status-pill ${meta.cls}`;
  el.innerHTML = `<i></i>${meta.label}`;
}

function updateResultCta() {
  const cta = $('#analysis-result-cta');
  if (!cta) return;
  if (!STATE.analysis.complete) { cta.hidden = true; return; }
  $('#analysis-result-text').textContent = `${STATE.issues.length} 处确定不一致，${STATE.unknowns.length} 项无法判断。`;
  cta.hidden = false;
}

function renderAnalysisScreen() {
  const order = STATE.shots;
  if (!order.length) return;
  const a = STATE.analysis;
  const idx = Math.max(0, Math.min(a.viewIndex ?? 0, order.length - 1));
  const shot = order[idx];
  const status = a.statuses[idx] || 'pending';

  $('#analysis-shot-list').innerHTML = order.map((s, i) => {
    const st = a.statuses[i] || 'pending';
    const meta = shotStateMeta(st, s.id);
    const classes = ['rail-item', i === idx ? 'is-active' : '', st === 'analyzing' ? 'is-analyzing' : '', st === 'issue' ? 'is-issue' : ''].filter(Boolean).join(' ');
    return `<button class="${classes}" data-analysis-shot="${i}" aria-current="${i === idx ? 'true' : 'false'}">
      <span class="rail-thumb"><img src="${s.image}" alt=""></span>
      <span class="rail-copy">
        <b>${s.id}</b>
        <span class="rail-detail">${shotDetailText(st, s.id, i)}</span>
        <span class="rail-state ${meta.cls}">${icon(meta.icon)}${meta.label}</span>
      </span>
    </button>`;
  }).join('');

  const done = a.statuses.filter((st) => st === 'ok' || st === 'issue').length;
  $('#rail-count').textContent = `已完成 ${done} / ${order.length}`;
  $('#analysis-shot-tag').textContent = `${shot.id} / 原始镜头`;
  $('#analysis-preview-img').src = shot.image;
  $('#analysis-preview-img').alt = `当前观察镜头 ${shot.id}`;

  renderAnalysisBadge(status, shot, idx);
  renderAnalysisChip(status);
  updateInsightPill(status, shot.id);
  renderInsights(idx);
  syncInsightScroll(shot.id);
  renderPipeline();
  updateAnalysisHeader();
  updateResultCta();
}

function renderInsights(idx, quiet = false) {
  const shot = STATE.shots[idx];
  if (!shot) return;
  const a = STATE.analysis;
  const status = a.statuses[idx] || 'pending';
  const observations = OBSERVATIONS[shot.id] || [];
  const stats = shotObservationStats(shot.id);
  const name = parseCharacter($('#character-input').value).name;

  if (status === 'failed') {
    $('#analysis-insights').innerHTML = `
      <div class="insight-section">
        <div class="insight-section-title"><span>SHOT STATUS · ${shot.id}</span>${pill('观察失败', 'failed')}</div>
        <div class="analysis-failure">
          <span class="status-icon is-alert">${icon('alert')}</span>
          <div><b>${shot.id} 观察失败</b><p>模型服务响应超时。其他镜头的观察结果与证据均已保留，不需要整任务重跑。</p></div>
        </div>
      </div>
      <div class="insight-section">
        <div class="insight-stage">${statusIcon('info')}观察失败 · 可单独重新观察，重新观察只覆盖 ${shot.id}</div>
      </div>
      <div class="insight-section">
        <button class="btn btn-ghost btn-block" data-action="retry-shot">${icon('refresh')}重新观察 ${shot.id}</button>
      </div>`;
    return;
  }

  const visibleObservations = observations.slice(0, visibleObservationCount(idx));

  const obsHtml = visibleObservations.map((o, i) => {
    const judge = o.verdict === 'consistent' ? 'ok' : o.verdict === 'inconsistent' ? 'alert' : o.verdict === 'unknown' ? 'muted' : 'neutral';
    const judgeText = o.verdict === 'consistent' ? '一致' : o.verdict === 'inconsistent' ? '不一致' : o.verdict === 'unknown' ? '无法判断' : '仅记录';
    return `<div class="obs-item" style="animation-delay:${Math.min(i, 8) * 40}ms">
      <div class="obs-head"><b>${o.name}</b>${pill(judgeText, judge)}</div>
      <div class="obs-values">
        <span class="from">${o.verdict === 'unknown' ? '—' : escapeHtml(o.observed)}</span>
        ${o.verdict === 'inconsistent' ? icon('arrow-right') : ''}
        ${o.verdict === 'inconsistent' ? `<span class="to">${o.name === '配饰' ? '配饰不符' : o.name === '上装颜色' ? '超出容差' : '需复核'}</span>` : ''}
      </div>
      <div class="${o.verdict === 'unknown' ? 'obs-unknown' : 'obs-evidence'}">${o.verdict === 'unknown' ? `原因：${escapeHtml(o.evidence)}` : `证据：${escapeHtml(o.evidence)}`}</div>
    </div>`;
  }).join('');

  const stageLine = status === 'analyzing'
    ? `正在逐项观察 · 已完成 ${visibleObservations.length} / ${observations.length} 项`
    : `观察完成 · ${stats.total} 项已记录 · ${stats.unknown} 项无法判断`;
  const stageIcon = status === 'analyzing' ? '<span class="scan-spinner"></span>' : statusIcon('ok');
  const emptyObs = `<div class="insight-stage">${statusIcon('info')}${pendingShotNote(idx)}</div>`;
  const stageFooter = status === 'pending' ? '' : `
    <div class="insight-section">
      <div class="insight-stage">${stageIcon}${stageLine}</div>
    </div>`;
  const identified = a.stage >= 1;

  $('#analysis-insights').innerHTML = `
    <div class="insight-section">
      <div class="insight-section-title"><span>SUBJECT IDENTIFICATION</span>${pill(identified ? '已识别' : '待识别', identified ? 'ok' : 'neutral')}</div>
      <div class="identity-card">
        <span class="identity-avatar"><img src="assets/identity-avatar.jpg" alt=""></span>
        <div><b>${name} · 主要人物</b><span>画面主体 · 单人画面</span></div>
        <em>96%</em>
      </div>
    </div>
    <div class="insight-section">
      <div class="insight-section-title"><span>OBSERVATIONS · ${shot.id}</span><span>${visibleObservations.length} / ${observations.length}</span></div>
      <div class="obs-list${quiet ? ' is-quiet' : ''}">${obsHtml || emptyObs}</div>
    </div>${stageFooter}`;
}

function renderPipeline() {
  const a = STATE.analysis;
  const total = ANALYSIS_STAGES.length;
  const paused = a.phase === 'paused';
  const activeIndex = a.complete ? total : a.stage;

  $('#analysis-pipeline').innerHTML = ANALYSIS_STAGES.map((stage, i) => {
    const done = a.complete || i < activeIndex;
    const active = !a.complete && i === activeIndex;
    const failed = paused && i === activeIndex;
    const stateCls = failed ? 'is-failed' : done ? 'is-done' : active ? 'is-active' : '';
    const flag = done ? icon('check') : failed ? icon('alert') : '';
    return `<div class="pipe-step ${stateCls}" style="--i:${i}">
      <i class="pipe-num">${String(i + 1).padStart(2, '0')}</i>
      <span class="pipe-name">${stage.name}</span>
      <span class="pipe-flag">${flag}</span>
    </div>`;
  }).join('');

  const container = $('#analysis-pipeline');
  container.className = `pipeline-steps${a.complete ? ' is-complete' : ''}`;
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
    <div class="precheck-summary" style="border-color:${candidate.overall === 'pass' ? 'rgba(91,224,176,.16)' : candidate.overall === 'fail' ? 'rgba(255,119,136,.16)' : 'rgba(244,187,103,.16)'};background:${candidate.overall === 'pass' ? 'rgba(91,224,176,.035)' : candidate.overall === 'fail' ? 'rgba(255,119,136,.035)' : 'rgba(244,187,103,.035)'}">
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
    if (action === 'load-demo') {
      clearAnalysisTimers();
      resetDemoData();
      $('#character-input').value = '阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，黑色丝质衬衫，紫色口袋巾，圆形吊坠项链（蓝紫四瓣花）。';
      $('#script-input').value = '这些镜头为同一场戏的连续动作，无换装情节。';
      setScriptLock(true);
      renderParsedAttributes();
      parseScript();
      renderShots();
      renderPipeline();
      showScreen('create');
      toast('已载入课题示例：3 个镜头，2 处确定问题');
      return;
    }
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
window.__CCS = { STATE, navigate, showScreen, startAnalysis, renderResults, renderOptimizer };
