# AI 角色形象一致性检查助手（char_cons）

本地部署、单用户、单角色的 AI 角色形象一致性检查 Web 应用。面向 AI 漫剧、短剧与分镜创作流程：上传角色设定、剧本说明与镜头图，系统逐镜头观察 11 个外观要素，按确定性规则判定一致 / 不一致 / 无法判断 / 豁免 / 仅记录，并输出可定位的报告、修正提示词与候选图。

| 项目 | 说明 |
| --- | --- |
| 当前版本 | `0.1.0`（P0） |
| 运行方式 | Windows 本地单进程，默认仅监听 `127.0.0.1` |
| 技术栈 | FastAPI + SQLite（WAL）+ 原生 ES Modules 前端 |
| AI 服务 | 火山方舟豆包 Seed 2.0 视觉 + Seedream 5.5；模型 ID 需自行配置 |
| 自动化测试 | `161 passed, 3 skipped`（2026-11-26 复跑） |

> AI 只负责观察、解析、建议与预检；一致性判定由本地确定性代码执行。真实模型的时延、费用、稳定性与角色一致性仍需在真实账号下持续实测。

## 1. 项目简介

`char_cons` 用于检查同一角色在不同镜头中的外观是否保持一致。它不训练模型，也不做人脸身份识别，而是把「角色设定 + 剧本说明 + 镜头图」作为输入，通过视觉模型提取可核对的外观观察值，再交由本地规则引擎完成判定与统计。

核心原则：

- **判定确定、可复核**：R1～R10 由代码实现；AI 输出观察值、证据与置信度，不直接下结论。
- **本地优先**：任务、原图、报告、候选图与设置均保存在本机；仅在调用第三方模型时按需发送图片。
- **单镜头隔离**：单镜头观察、单候选生成、单镜头复检失败不丢弃整份报告，可单独重试。
- **同源数据**：页面、矩阵、摘要、导出与历史均来自同一份判定结果，不各自计算。
- **原始素材不覆盖**：采用候选图时新建当前版本，原图始终保留。

## 2. 核心功能

### 2.1 任务与素材

- 创建、列表、搜索、筛选、详情、排序与删除任务；刷新或重启后数据保留。
- 上传、排序、备注、替换与删除镜头图；支持 JPEG、PNG、WebP。
- 单张图片默认上限 20 MB，可在设置页调整为 1～100 MB。
- 角色设定、剧本说明与镜头素材齐备后方可开始分析。

### 2.2 角色设定与剧本解析

- 角色设定由豆包视觉/语言模型结构化解析，并经 Pydantic 校验；模型返回空结果或可回退错误时使用本地规则解析；鉴权、额度与内容安全错误会直接提示。
- 若模型与本地规则都无法提取显式要素，则中止分析并提示补充设定。
- 剧本解析使用确定性规则，识别「无换装 / 已定位变化 / 未定位变化 / 场景切换」。
- 仅豁免剧本中同时写明镜头号与具体要素的变化；只写「换装」而未写要素时不豁免任何要素；未写明的要素始终严格比对。

### 2.3 逐镜头观察

- 每个镜头一次视觉请求，输出 11 个要素的观察值、可见性、原因、证据与置信度。
- 观察并发上限为 3。
- 单镜头失败隔离；仅当全部镜头失败时才判定任务失败。
- 观察进度、阶段与镜头状态持久化到 SQLite；刷新页面后可继续查看，重启后遗留的运行中任务会标记为 `paused`，由用户决定是否重新开始。

### 2.4 一致性判定

- 11 个要素：发型、发色、上装款式、上装颜色、上装图案、下装款式、下装颜色、下装图案、配饰、鞋履、道具。
- 结论状态：一致、不一致、无法判断、剧本豁免、仅记录；低置信度差异单独标记为疑似问题。
- 颜色按色系与明度容差比较；款式按大类比较；发型按长度、造型、刘海分别判断。
- 设定未定义只表示「没有设定期望值」，不会推断期望，也不做跨镜头对比：可见时仅记录，不可见或缺少观察值时无法判断。
- 统计口径按「镜头 × 要素」判定单元计算；疑似问题单独统计，不计入确定不一致。

### 2.5 报告与联动

- 报告包含摘要统计、镜头画廊、11×N 要素矩阵、确定问题、疑似问题、无法判断、剧本豁免、仅记录、证据、建议与抽卡方案。
- 从工作台或历史页打开已完成/部分完成的任务，进入真实报告页。
- 报告打开时默认不选中问题；点击镜头卡、问题卡或矩阵单元格后，画廊、矩阵与右侧检查器三处同步高亮。
- 支持 Markdown 与 JSON 导出，导出内容与页面共用同一份报告数据。
- 导出不包含 API Key、绝对路径或远程图片地址；文件名形如 `一致性检查_角色名_YYYYMMDD_HHmm.md` / `.json`。

### 2.6 提示词修正与候选生成

- 优化入口按镜头批量组织：一次优化覆盖该镜头全部未关闭问题，共用一份合并提示词与一次生成。
- 建议包含修正提示词、负向内容、修改要点、参考镜头与抽卡方案；模型不可用时回退确定性本地模板，并在 `suggestions.source` 标注 `ai` / `local`。
- Seedream 5.5 单次只生成 1 张；默认 4 张候选由 4 次并行调用完成，允许部分成功。
- 已返回的候选图立即下载并保存到本地；整批等待超时不会丢弃已有候选。
- Seedream 无独立负向参数，负向内容合并进正向提示词，界面如实标注。
- 生成服务返回的远程 URL 仅作诊断保留，候选图以本地文件为准。

### 2.7 自动预检

- 候选生成后自动预检，优先一次批量预检；随请求携带建议写明的参考镜头图，最多 2 张。
- 参考图只用于核对「与参考镜头一致」类标准，不参与构图、背景、光线判断。
- 候选映射不完整或 JSON 解析失败时，降级为逐张预检并记录 `precheck_mode`。
- 预检结论仅作为采用建议，不参与设定判定，也不会自动采用；预检失败不影响候选展示与人工采用。

### 2.8 采用与单镜头复检

- 采用候选后新建当前版本；原图与其他镜头的版本永不覆盖。
- 仅重新观察被替换的镜头，并增量更新问题、矩阵与统计。
- 复检仍不一致时问题保持开启；复检失败时回滚当前版本、保留采用记录并可重试。
- 采用图成为结果页画廊、检查器、历史与首页缩略图的默认展示图；检查器提供「查看原图」。

### 2.9 历史、设置与导出

- 历史页支持状态筛选、搜索与存档概况；有运行中任务时自动轮询刷新。
- 分析失败、草稿或暂停任务可在历史行打开原因说明并重新开始分析。
- 设置页可配置分析/生成服务商、模型 ID、Base URL、API Key、生成尺寸、默认候选张数与上传上限。
- 「测试连接」可区分鉴权失败、网络不可达、超时与额度不足；分析测试不发送本地图片，生成测试会发起 1 次最小生成请求，可能产生费用。
- 支持本地数据概况、占用空间统计与清除数据；运行中的分析或生成会被拒绝。
- 在结果页下载 Markdown / JSON 报告；历史页可重新打开对应结果页后导出。

## 3. 技术架构

### 3.1 技术栈

| 层次 | 实现 |
| --- | --- |
| 前端 | 原生 HTML / CSS + ES Modules，无构建链 |
| Web 服务 | FastAPI `0.162.0` + Uvicorn `0.54.0`，单进程 |
| 数据 | SQLite（WAL 模式）+ 本地文件目录 |
| 请求模型 | Pydantic `2.14.1` |
| HTTP 客户端 | httpx `0.28.1` |
| 图片处理 | Pillow `13.0.0` |
| 密钥存储 | keyring `25.7.0`（Windows 凭据管理器） |
| 测试 | pytest `9.2.0`、pytest-asyncio `1.5.0`、Playwright `1.65.2`（使用本机 Chrome/Edge） |
| AI 服务 | 火山方舟豆包 Seed 2.0 视觉、Seedream 5.5 |

### 3.2 分层结构

```text
浏览器（frontend/）
    │  HTTP / JSON / multipart
    ▼
FastAPI 路由（app/api/）
    ▼
业务服务（app/services/）
    ├─ 分析编排、判定引擎、建议、生成、复检、报告、导出、设置
    ├─ Provider 适配器（app/providers/）：豆包视觉 / Seedream / Mock
    ├─ 版本化提示词（app/prompts/）
    └─ SQLite 访问层（app/repositories/）
```

### 3.3 处理流程

```text
上传素材
  → 角色设定解析 / 剧本解析
  → 逐镜头观察（11 要素，并发 3）
  → R1～R10 确定性判定
  → 报告、矩阵、建议与抽卡
  → Seedream 候选生成（1 张/次，默认 4 次并行）
  → 自动预检
  → 人工采用
  → 仅复检被替换镜头
  → 更新报告并保留版本
```

### 3.4 关键设计

- **本地单进程**：默认只监听 `127.0.0.1`，不引入 Redis、Celery 或 Docker。
- **异步分析**：分析任务在后台运行，进度、阶段、镜头状态与结果持久化到 SQLite；前端轮询读取。
- **超时与重试**：429、5xx 与超时使用指数退避，默认共 3 次尝试；JSON 校验失败修复 1 次；鉴权、额度与内容安全错误不重试。
- **失败隔离**：单镜头、单候选、单次预检均独立处理，允许部分成功。
- **安全存储**：分析 Key 与生成 Key 分开保存；通用 `ARK_API_KEY` 不会自动复用。
- **可配置模型**：代码不内置可用模型 ID；模型 ID、Base URL、尺寸与费用均以火山方舟控制台和实际账号为准。

## 4. 目录结构

```text
char_cons/
├─ app/                         后端（FastAPI）
│  ├─ main.py                   应用入口：中间件、路由、静态托管、启动恢复
│  ├─ api/                      任务、分析、报告、生成、设置、存档、健康检查
│  ├─ core/                     配置、日志、错误、CSRF、路径安全、并发、常量
│  ├─ models/                   API 请求模型
│  ├─ migrations/               SQLite 迁移：001_init ～ 004_generation_loop
│  ├─ prompts/                  版本化提示词与 manifest
│  ├─ providers/                豆包视觉 / Seedream / Mock 适配器
│  ├─ repositories/             SQLite 访问层
│  └─ services/                 分析、判定、建议、生成、复检、报告、导出、设置
├─ frontend/                    正式前端运行时（由 FastAPI 在 / 托管）
│  ├─ index.html                单页结构与全部视图
│  ├─ styles.css                设计令牌、布局、组件与响应式样式
│  ├─ styles.additions.css      真实功能补充样式
│  ├─ app.js                    演示模式交互与本地模拟
│  ├─ js/core/                  会话、API、弹窗、隐私告知、通知、通用 UI
│  ├─ js/pages/                 home / history / create / analysis / results / optimizer / settings
│  ├─ assets/                   角色与镜头素材
│  └─ picture/                  本地图片素材
├─ tests/                       pytest 单元、接口、受控回归与性能测试
├─ scripts/
│  ├─ e2e_app.py                仅 E2E 使用的受控观察夹具服务器
│  ├─ e2e_playwright.py         页面回归（14 项检查）
│  ├─ e2e_analysis_dynamic.py   分析过程动态回归
│  ├─ verify_startup.py         Windows 启动验证
│  ├─ verify_vision.py          视觉服务连通性验证
│  ├─ verify_generation.py      生成服务连通性验证
│  └─ verify_live_loop.py       真实模型闭环（需凭据与 --yes）
├─ UI页面原型/                  定稿界面基线（静态模拟，不联网）
│  ├─ index.html                单页原型结构与全部页面
│  ├─ styles.css                设计令牌、布局与响应式样式
│  ├─ app.js                    页面切换、模拟分析与生成
│  ├─ assets/                   原型角色和镜头素材
│  ├─ picture/                  本地图片素材
│  ├─ preview/                  关键页面预览截图
│  └─ 打开说明.txt              原型打开与演示路径说明
├─ 测试用例/                    本地示例素材
│  ├─ test1/                    3 张镜头图 + 角色设定与剧本说明
│  └─ test2/                    3 张镜头图 + 角色设定与剧本说明
├─ config.example.json          非敏感配置样例（不含 Key）
├─ pytest.ini                   pytest 配置
├─ requirements.txt             固定版本的依赖清单
├─ run.py                       本地启动脚本（读取配置、可选自动打开浏览器）
└─ .gitignore
```

## 5. 环境要求

- **操作系统**：Windows 10/11（本项目在 Windows 11 验证）。
- **Python**：3.11（验证版本 `3.11.15`），必须使用项目指定解释器：

  ```text
  D:\miniconda3\miniconda3\envs\Agent\python.exe
  ```

- **浏览器**：Chrome 或 Edge。
- **网络**：使用真实模型时需可访问火山方舟 API；Mock 模式可离线运行。
- **不依赖**：Docker、Redis、Celery、Node.js 构建链。

> 本项目所有安装、启动与测试命令均使用上述解释器的绝对路径。若该环境不可用，请先准备对应的 Conda 环境；不要改用系统全局 Python。

## 6. 安装

```bat
:: 安装运行时与测试依赖
D:\miniconda3\miniconda3\envs\Agent\python.exe -m pip install -r requirements.txt

:: 可选：确认关键依赖可导入
D:\miniconda3\miniconda3\envs\Agent\python.exe -c "import fastapi, uvicorn, aiosqlite, PIL, keyring, httpx; print('ok')"
```

页面回归使用本机 Chrome/Edge，无需执行 `playwright install`。

## 7. 配置

### 7.1 数据目录与配置文件

默认数据目录：

```text
%APPDATA%\char_cons\
├─ char_cons.db         SQLite 数据库（任务、报告、设置、事件）
├─ config.json          非敏感配置（可选）
└─ data\
   ├─ uploads\          原图、分析副本、缩略图
   ├─ generated\        候选图
   ├─ exports\          导出文件
   └─ logs\             日志（不含 Key 与图片内容）
```

- 可用环境变量 `CHAR_CONS_HOME` 覆盖数据根目录。
- 配置可复制 `config.example.json` 为 `%APPDATA%\char_cons\config.json`，也可直接使用设置页修改。
- 备份时关闭应用后复制 `char_cons.db` 与 `data\` 目录。

### 7.2 主要配置项

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `8765` | 本地监听地址与端口 |
| `upload_max_mb` | `20` | 单张图片上限，1～100 MB |
| `default_batch_size` | `4` | 默认候选张数，1～4 |
| `analysis_provider` | `doubao` | `doubao` 或 `mock` |
| `analysis_model` | 空 | 视觉模型 ID，必须来自控制台 |
| `analysis_base_url` | 方舟北京地址 | 可替换为实际 Base URL |
| `generation_provider` | `doubao` | `doubao` 或 `mock` |
| `generation_model` | 空 | Seedream 模型 ID，必须来自控制台 |
| `generation_base_url` | 方舟北京地址 | 可替换为实际 Base URL |
| `generation_size` | 空 | 留空表示由服务端使用默认尺寸 |
| `retry_max_attempts` | `3` | 可重试错误的总尝试次数 |
| `vision_timeout_seconds` | `180` | 单次视觉观察超时 |
| `precheck_timeout_seconds` | `180` | 预检超时 |
| `seedream_timeout_seconds` | `300` | 单张生成超时 |
| `generation_batch_wait_seconds` | `900` | 整批候选等待上限 |

`config.example.json` 还包含观察等待、预检批量等待、上传/下载/导出超时、SQLite busy timeout 等可调项。

### 7.3 环境变量

| 变量 | 作用 |
| --- | --- |
| `CHAR_CONS_HOME` | 覆盖本地数据根目录 |
| `CHAR_CONS_HOST` / `CHAR_CONS_PORT` | 覆盖监听地址 / 端口 |
| `CHAR_CONS_ANALYSIS_PROVIDER` | `doubao` 或 `mock` |
| `CHAR_CONS_ANALYSIS_MODEL` | 视觉模型 ID |
| `CHAR_CONS_ANALYSIS_BASE_URL` | 分析服务 Base URL |
| `CHAR_CONS_ANALYSIS_API_KEY` | 分析服务 Key（优先于凭据管理器） |
| `CHAR_CONS_GENERATION_PROVIDER` | `doubao` 或 `mock` |
| `CHAR_CONS_GENERATION_MODEL` | Seedream 模型 ID |
| `CHAR_CONS_GENERATION_BASE_URL` | 生成服务 Base URL |
| `CHAR_CONS_GENERATION_SIZE` | 生成尺寸 |
| `CHAR_CONS_GENERATION_API_KEY` | 生成服务 Key（优先于凭据管理器） |
| `CHAR_CONS_LIVE_VISION=1` | 启用真实视觉测试（会产生费用） |
| `CHAR_CONS_LIVE_GENERATION=1` | 启用真实生成测试（会产生费用） |

### 7.4 API Key 与模型配置

- 通过设置页保存的 Key 仅经本地后端写入 **Windows 凭据管理器**：服务名 `char_cons`，分析用户名 `ark-analysis`，生成用户名 `ark-generation`。
- 分析 Key 与生成 Key 分开保存，不自动复用；通用 `ARK_API_KEY` 不作为回退。
- 读取顺序：环境变量 → 凭据管理器。若使用环境变量，设置页会显示来源为 `env`。
- 前端只接收 `hasKey` / `source` 与固定掩码；Key 不进入 localStorage、sessionStorage、导出文件、日志或仓库。
- 模型 ID 默认留空，必须填写火山方舟控制台中实际可用的 ID；模型参数、尺寸档位、费用与角色一致性均以控制台和实际测试为准。

## 8. 启动与访问

### 8.1 推荐启动方式

```bat
:: 启动并自动打开浏览器
D:\miniconda3\miniconda3\envs\Agent\python.exe run.py
```

常用参数：

```bat
D:\miniconda3\miniconda3\envs\Agent\python.exe run.py --no-browser
D:\miniconda3\miniconda3\envs\Agent\python.exe run.py --port 8790 --no-browser
D:\miniconda3\miniconda3\envs\Agent\python.exe run.py --reload
```

### 8.2 手动启动

```bat
D:\miniconda3\miniconda3\envs\Agent\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

访问：

- 应用首页：`http://127.0.0.1:8765/`
- 健康检查：`GET http://127.0.0.1:8765/api/health`（数据库或存储异常时返回 `503`）
- 会话与 CSRF：`GET http://127.0.0.1:8765/api/session`
- OpenAPI 文档：`http://127.0.0.1:8765/api/docs`

启动时会自动创建数据目录、执行 SQLite 迁移，并将上次进程遗留的 `running` / `retrying` 任务标记为 `paused`。默认只监听回环地址，不建议将服务暴露到公网。

## 9. 页面与使用流程

### 9.1 页面入口

运行时入口为 `frontend/index.html`，由 FastAPI 在 `/` 托管；下表为哈希路由。

| 页面 | 地址 | 说明 |
| --- | --- | --- |
| 工作台 | `#home` | 角色主视觉、最近任务、新建入口 |
| 新建检测任务 | `#create` | 角色设定、剧本说明、镜头上传与排序 |
| AI 分析工作台 | `#analysis` | 三栏工作区、逐镜头进度、失败重试 |
| 检测结果 | `#results` | 摘要、镜头画廊、要素矩阵、问题/疑似/无法判断/豁免、建议与抽卡 |
| 优化提示词 | `#optimizer` | 前后对比、修正提示词、候选图、自动预检、采用与单镜头复检 |
| 历史报告 | `#history` | 本地任务列表、状态筛选与搜索 |
| 设置 | `#settings` | 服务状态、连接测试、生成张数、隐私与本地数据 |

### 9.2 推荐使用流程

1. 打开工作台，点击「新建检测任务」。
2. 手动填写角色固定外观（最多 500 字）；默认不预填示例角色，也不会自动填入示例值。
3. 剧本说明默认预置「所有镜头之间为同一场戏的连续动作，无换装情节。」模板，可按实际剧情修改（最多 1000 字）。如存在换装，请写明镜头号与具体变化要素；场景切换本身不会自动豁免外观。
4. 上传真实镜头图片（支持 JPEG/PNG/WebP，按叙事顺序排序），点击「开始检查」。
5. 首次调用第三方模型前会显示数据边界告知；确认后进入异步分析工作台，可查看逐镜头进度与单镜头失败原因。
6. 分析完成后进入检测结果：查看摘要、矩阵、问题与证据；点击镜头卡、问题卡或矩阵单元格可联动定位。
7. 对存在问题的镜头点击「优化此镜头」：查看合并建议，重新生成候选，查看自动预检结论，人工采用后仅复检该镜头。
8. 在历史页筛选、搜索、重新打开任务；在结果页导出 Markdown / JSON。
9. 在设置页管理服务、模型、Key、生成张数、上传上限与本地数据。

### 9.3 界面基线

`UI页面原型/` 是定稿静态可点击原型，用于对照页面结构、视觉令牌与交互状态；其中的分析过程、候选图与预检结果均为本地模拟数据，不调用真实模型，也不需要 API Key。正式运行时界面位于 `frontend/`。

直接双击 `UI页面原型/index.html` 即可打开；如浏览器限制本地文件访问，可在该目录启动静态服务器：

```bat
cd /d "UI页面原型"
D:\miniconda3\miniconda3\envs\Agent\python.exe -m http.server 4173 --bind 127.0.0.1
```

然后访问 `http://127.0.0.1:4173/`。原型说明见 `UI页面原型/打开说明.txt`。

界面采用深色创意工作室风格，以图片为视觉中心；一致 / 不一致 / 无法判断 / 豁免 / 失败等状态同时使用图标与文字，不只依赖颜色；已按 1440 与 375 宽度验证布局。

## 10. 接口概览

> 所有写请求（`POST` / `PUT` / `PATCH` / `DELETE`）需携带 `GET /api/session` 返回的 `X-CSRF-Token`，并通过同源校验。完整请求/响应结构以 `/api/docs` 为准。

### 10.1 系统

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查：数据库、存储、版本与运行时长 |
| GET | `/api/session` | 会话信息、CSRF Token、上传上限与模式 |
| GET | `/api/docs` | OpenAPI 交互文档 |

### 10.2 任务与素材

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/tasks` | 创建任务 |
| GET | `/api/tasks` | 任务列表，支持 `mode`、`status`、`q`、分页 |
| GET | `/api/tasks/{taskId}` | 任务详情 |
| PATCH | `/api/tasks/{taskId}` | 更新任务名称、角色名、设定、剧本、候选张数 |
| DELETE | `/api/tasks/{taskId}` | 删除任务 |
| POST | `/api/tasks/{taskId}/validate` | 校验素材是否齐备 |
| POST | `/api/tasks/{taskId}/shots` | 上传镜头（multipart） |
| POST | `/api/tasks/{taskId}/shots/reorder` | 重排镜头 |
| PATCH | `/api/tasks/{taskId}/shots/{shotId}` | 更新镜头备注 |
| POST | `/api/tasks/{taskId}/shots/{shotId}/replace` | 替换镜头图 |
| DELETE | `/api/tasks/{taskId}/shots/{shotId}` | 删除镜头 |
| GET | `/api/tasks/{taskId}/shots/{shotId}/image` | 读取镜头图；`variant` 可选 `original`、`analysis`、`thumb`、`current` |

### 10.3 分析与报告

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/tasks/{taskId}/analyze` | 启动异步分析 |
| GET | `/api/tasks/{taskId}/analysis` | 读取分析进度、阶段与镜头状态 |
| POST | `/api/tasks/{taskId}/cancel` | 取消分析 |
| GET | `/api/tasks/{taskId}/shots/{shotId}/observations` | 读取单镜头观察结果 |
| GET | `/api/tasks/{taskId}/report` | 读取完整报告 |
| GET | `/api/tasks/{taskId}/export` | 导出报告；`format` 可选 `md` 或 `json` |
| GET | `/api/archive/summary` | 存档概况与占用统计 |

### 10.4 优化、生成与复检

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/tasks/{taskId}/issues/{issueId}/optimizer` | 读取单问题优化建议 |
| POST | `/api/tasks/{taskId}/issues/{issueId}/generate` | 针对单问题启动生成 |
| GET | `/api/tasks/{taskId}/shots/{shotId}/optimizer` | 读取镜头级合并优化建议 |
| POST | `/api/tasks/{taskId}/shots/{shotId}/generate` | 针对镜头启动批量生成 |
| GET | `/api/tasks/{taskId}/generations/{generationId}` | 读取生成记录、候选与预检 |
| POST | `/api/tasks/{taskId}/generations/{generationId}/cancel` | 取消生成 |
| POST | `/api/tasks/{taskId}/generations/{generationId}/adopt` | 采用候选并触发单镜头复检 |
| GET | `/api/tasks/{taskId}/generations/{generationId}/candidates/{candidateId}/image` | 读取候选图；`variant` 可选 `full` 或 `thumb` |
| POST | `/api/tasks/{taskId}/shots/{shotId}/recheck` | 重新复检单镜头 |

### 10.5 设置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/settings` | 读取设置与服务状态 |
| PUT | `/api/settings` | 更新默认张数、上传上限、超时与隐私确认等 |
| PUT | `/api/settings/services/{service}` | 更新分析或生成服务配置 |
| DELETE | `/api/settings/keys/{service}` | 删除分析或生成 Key |
| POST | `/api/settings/test` | 测试第三方连接 |
| GET | `/api/settings/storage` | 本地数据概况 |
| POST | `/api/settings/clear-data` | 清除本地数据（需二次确认） |

## 11. 判定规则与统计口径

### 11.1 判定优先级

| 规则 | 条件 | 结论 |
| --- | --- | --- |
| R1 | 镜头分析失败 | 镜头级失败，不产出该镜头结论 |
| R2 | 要素不可见（遮挡、出画、背影、过暗、过小、模糊等） | 无法判断，必须记录原因 |
| R3 | 部分可见，但证据不足以支撑判定 | 无法判断 |
| R4 | 剧本中明确写明该镜头该要素的变化 | 剧本豁免，不生成问题 |
| R5 | 设定已定义，观察值在容差内 | 一致 |
| R6 | 设定已定义，观察值超出容差 | 不一致，生成问题项 |
| R7 | 设定未定义，但画面可见并可记录观察事实 | 仅记录，不做对错判定 |
| R8 | 跨镜头对比 | 已取消；未定义要素不做跨镜头推断，不生成问题或提示 |
| R9 | 观察或对比置信度低，差异不足以形成可靠结论 | 疑似问题（待人工复核） |
| R10 | 缺少足以支撑结论的画面证据 | 无法判断，必须记录原因 |

### 11.2 容差与特殊规则

- **颜色**：输出规范色名与色系。同色系且明度接近视为一致；跨色系判不一致；同色系明显深浅差异标为疑似。
- **款式**：同一大类视为一致但标注差异；不同大类判不一致。
- **发型**：长度、造型、刘海分别判断，任一项明显变化即判不一致。
- **配饰**：设定要求存在而未出现判不一致；设定未定义时，可见仅记录、不可见无法判断；图案或形状不符判不一致。
- **低置信度**：进入疑似问题，不计入确定不一致；人工复核不篡改模型原始观察。
- **设定未定义**：只表示没有设定期望值，不代表可以跨镜头推断期望；可见时仅记录，不可见或没有观察值时无法判断。
- **剧本豁免**：仅豁免剧本写明的镜头与要素；只写「换装」不豁免任何要素。

### 11.3 统计口径

- 统计单位为「镜头 × 要素」判定单元，不使用镜头数或问题条数代替。
- 定稿示例为 3 个镜头 × 11 个要素 = 33 个判定单元：**12 一致 + 2 不一致 + 14 无法判断 + 5 仅记录 + 0 豁免**。
- 该统计用于验证判定引擎与报告结构，不代表任意输入都会得到相同分布。
- 疑似问题单独统计，不计入确定不一致；问题条数与问题镜头数分开统计。

## 12. 测试与验证

### 12.1 常用命令

```bat
:: 单元 / API / 集成测试（默认使用 Mock）
D:\miniconda3\miniconda3\envs\Agent\python.exe -m pytest

:: 受控回归样本（20 组合成用例）
D:\miniconda3\miniconda3\envs\Agent\python.exe -m pytest tests\test_golden_cases.py -q

:: 本地性能冒烟（Mock）
D:\miniconda3\miniconda3\envs\Agent\python.exe -m pytest tests\test_performance_smoke.py -q -s

:: Windows 启动验证（临时数据目录）
D:\miniconda3\miniconda3\envs\Agent\python.exe scripts\verify_startup.py

:: 页面回归（本机 Chrome/Edge，14 项检查）
D:\miniconda3\miniconda3\envs\Agent\python.exe scripts\e2e_playwright.py

:: 分析过程动态回归（本机 Chrome）
D:\miniconda3\miniconda3\envs\Agent\python.exe scripts\e2e_analysis_dynamic.py
```

### 12.2 验证状态

| 项目 | 结果 |
| --- | --- |
| 自动化测试 | `161 passed, 3 skipped`（2026-11-26 复跑） |
| 受控回归 | 20 / 20 通过（合成输入，非真实人工金色样本） |
| Playwright 页面回归 | 14 项检查通过（七页、闭环、导出、设置、历史、375px） |
| Windows 启动验证 | 通过（健康检查、静态页、七视图、设置/任务接口） |
| 本地性能冒烟 | 通过（Mock；不代表真实模型时延） |
| 真实视觉分析 | 已跑通（2026-11-25，Seed-2.0-lite，真实任务 9 次观察） |
| 真实 Seedream 生成与预检 | 已跑通（2026-11-25，4 张候选 + 批量预检） |
| 真实完整采用/复检 | 待执行 |
| 真实时延、费用、并发稳定性与角色一致性 | 待实测 |
| 12～20 组人工复核金色样本 | 未开始，缺素材与人工标注 |
| 180/60/180/180 秒性能目标（p95） | 未验证 |

跳过项（3 个）：

1. 真实豆包视觉测试：需 `CHAR_CONS_LIVE_VISION=1`、模型 ID 与 Key。
2. 真实 Seedream 生成测试：需 `CHAR_CONS_LIVE_GENERATION=1`、模型 ID 与 Key。
3. Windows 符号链接权限测试：当前权限不足。

### 12.3 真实模型验证命令

```bat
:: 视觉连通性（可选 --mock 离线验证）
set "CHAR_CONS_ANALYSIS_MODEL=请替换为控制台中的视觉模型 ID"
set "CHAR_CONS_ANALYSIS_API_KEY=请替换为分析 Key"
D:\miniconda3\miniconda3\envs\Agent\python.exe scripts\verify_vision.py --image 某张镜头.png

:: 生成连通性（可选 --mock 离线验证）
set "CHAR_CONS_GENERATION_MODEL=请替换为控制台中的 Seedream 模型 ID"
set "CHAR_CONS_GENERATION_API_KEY=请替换为生成 Key"
D:\miniconda3\miniconda3\envs\Agent\python.exe scripts\verify_generation.py

:: 真实闭环：分析 → 报告 → 生成 → 预检 → 采用 → 复检（会产生费用）
D:\miniconda3\miniconda3\envs\Agent\python.exe scripts\verify_live_loop.py --yes --candidates 1
```

真实调用会产生费用；脚本使用临时数据目录，不写入真实历史，也不打印 Key。

## 13. 安全与隐私

- 默认仅监听 `127.0.0.1`，不对外网暴露。
- 设置页保存的 API Key 仅写入 Windows 凭据管理器；开发与 CI 也可通过环境变量提供 Key，环境变量优先于凭据管理器。
- 分析与生成 Key 分开，不自动复用通用 `ARK_API_KEY`。
- 前端只显示 Key 是否配置与固定掩码；Key 不进入浏览器存储、导出、日志、错误堆栈或 Git。
- 写接口启用 CSRF Token 与同源校验；缺失或来源不符返回 `403`。
- 文件访问使用安全路径拼接，防止路径穿越；上传文件名与候选文件名由服务端生成。
- 导出不包含 Key、绝对路径或远程图片 URL。
- 不做人脸身份识别，不保存人脸特征。
- 首次开始分析、首次重新生成或首次测试第三方连接前，展示数据发送范围告知；确认状态保存在本地 SQLite。
- 清除本地数据需二次确认；运行中的分析或生成会被拒绝；API Key 与本地设置保留。
- 任务按 `live` / `demo` 模式分别统计；演示数据与真实数据分开计数，避免混入真实历史统计。

## 14. 已知限制（P0）

- 仅覆盖 P0 范围；不包含账号体系、云端存储、多人协作、视频抽帧、人脸识别或自动修图。
- 真实模型 ID、Base URL、尺寸档位、单张费用与整体费用以火山方舟控制台和实际账号为准；代码不写死可用 ID。
- 真实角色一致性、4 候选并行时延、失败率与 180/60/180/180 秒性能目标尚未完成验收。
- 12～20 组真实素材 + 人工复核金色样本尚未制作；现有 20 组为合成受控回归，不能替代模型准确率验收。
- 默认自动化测试使用明确标记的 Mock；Mock 结果不代表真实模型效果。
- 本地单进程架构，不支持多实例水平扩展或分布式任务队列。
- Seedream 5.5 无独立负向参数，负向内容合并进正向提示词。
- 生成取消仅提供后端接口，定稿优化页未新增独立取消控件。
- 费用预估、PDF/长图导出、历史版本对比、撤销采用、候选图放大、预检标准人工编辑与孤儿文件清理不在本期范围。

## 15. 相关文件

| 文件/目录 | 用途 |
| --- | --- |
| `config.example.json` | 非敏感配置样例，可复制为 `%APPDATA%\char_cons\config.json` |
| `requirements.txt` | 固定版本的运行时与测试依赖 |
| `pytest.ini` | pytest 配置 |
| `run.py` | 本地启动脚本 |
| `frontend/` | 正式前端运行时 |
| `UI页面原型/` | 定稿界面基线与静态演示 |
| `UI页面原型/打开说明.txt` | 原型打开方式与演示路径 |
| `测试用例/` | 本地示例素材（test1、test2） |
| `tests/golden_cases.py` | 20 组合成受控回归样本 |
| `scripts/e2e_playwright.py` | 页面回归脚本 |
| `scripts/verify_startup.py` | Windows 启动验证脚本 |
| `scripts/verify_live_loop.py` | 真实模型闭环验证脚本 |
