-- 001_init.sql
-- 依据技术方案 6.3 建立完整业务表。迁移只执行一次，后续变更请新增文件。

-- 任务 ---------------------------------------------------------------
CREATE TABLE tasks (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    character_name      TEXT,
    mode                TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('demo', 'live')),
    status              TEXT NOT NULL DEFAULT 'idle'
                        CHECK (status IN ('idle', 'running', 'retrying', 'paused',
                                          'completed', 'partial', 'failed')),
    profile_raw         TEXT NOT NULL DEFAULT '',
    script_raw          TEXT NOT NULL DEFAULT '',
    profile_json        TEXT,
    script_context_json TEXT,
    schema_version      TEXT NOT NULL DEFAULT '1.3',
    prompt_version      TEXT,
    analysis_model      TEXT,
    generation_model    TEXT,
    default_batch_size  INTEGER NOT NULL DEFAULT 4
                        CHECK (default_batch_size BETWEEN 1 AND 4),
    batch_plan_json     TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    started_at          TEXT,
    completed_at        TEXT,
    error_code          TEXT,
    error_message       TEXT
);

-- 镜头 ---------------------------------------------------------------
CREATE TABLE shots (
    id                    TEXT PRIMARY KEY,
    task_id               TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    seq                   INTEGER NOT NULL,
    shot_code             TEXT NOT NULL,
    original_filename     TEXT,
    original_path         TEXT NOT NULL,
    analysis_path         TEXT,
    thumb_path            TEXT,
    current_version_id    TEXT,
    width                 INTEGER,
    height                INTEGER,
    file_size             INTEGER,
    mime_type             TEXT,
    note                  TEXT NOT NULL DEFAULT '',
    quality_status        TEXT CHECK (quality_status IS NULL
                                      OR quality_status IN ('ok', 'warn', 'error')),
    quality_warnings_json TEXT,
    analysis_status       TEXT NOT NULL DEFAULT 'pending'
                          CHECK (analysis_status IN ('pending', 'analyzing', 'ok', 'failed')),
    conclusion_status     TEXT CHECK (conclusion_status IS NULL
                                      OR conclusion_status IN ('ok', 'issue', 'unknown')),
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    UNIQUE (task_id, seq),
    UNIQUE (task_id, shot_code)
);

-- 生成记录 -----------------------------------------------------------
CREATE TABLE generation_records (
    id                     TEXT PRIMARY KEY,
    task_id                TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    shot_id                TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    issue_ids_json         TEXT,
    provider               TEXT NOT NULL,
    model                  TEXT NOT NULL,
    prompt                 TEXT NOT NULL,
    negative_prompt        TEXT,
    negative_prompt_mode   TEXT NOT NULL DEFAULT 'merged',
    reference_shot_ids_json TEXT,
    requested_count        INTEGER NOT NULL DEFAULT 4 CHECK (requested_count BETWEEN 1 AND 4),
    supported_params_json  TEXT,
    status                 TEXT NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'generating', 'prechecking',
                                             'succeeded', 'partial', 'failed')),
    precheck_status        TEXT NOT NULL DEFAULT 'pending'
                           CHECK (precheck_status IN ('pending', 'running', 'completed', 'failed')),
    precheck_mode          TEXT CHECK (precheck_mode IS NULL
                                       OR precheck_mode IN ('batch', 'per_candidate')),
    request_count          INTEGER NOT NULL DEFAULT 0,
    succeeded_count        INTEGER NOT NULL DEFAULT 0,
    failed_count           INTEGER NOT NULL DEFAULT 0,
    started_at             TEXT,
    finished_at            TEXT,
    error_code             TEXT,
    error_message          TEXT,
    cost_estimate          REAL,
    currency               TEXT NOT NULL DEFAULT 'CNY',
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL
);

-- 候选图 -------------------------------------------------------------
CREATE TABLE generation_candidates (
    id                   TEXT PRIMARY KEY,
    generation_id        TEXT NOT NULL
                         REFERENCES generation_records(id) ON DELETE CASCADE,
    candidate_index      INTEGER NOT NULL CHECK (candidate_index BETWEEN 1 AND 4),
    candidate_code       TEXT NOT NULL,
    provider_request_id  TEXT,
    remote_url           TEXT,
    local_path           TEXT NOT NULL,
    width                INTEGER,
    height               INTEGER,
    state                TEXT CHECK (state IS NULL
                                     OR state IN ('pass', 'partial', 'fail', 'unknown')),
    precheck_json        TEXT,
    adopted              INTEGER NOT NULL DEFAULT 0 CHECK (adopted IN (0, 1)),
    adopted_at           TEXT,
    user_checklist_json  TEXT,
    error_json           TEXT,
    created_at           TEXT NOT NULL,
    UNIQUE (generation_id, candidate_index),
    UNIQUE (generation_id, candidate_code)
);

-- 镜头版本（原图 / 采用版本） ------------------------------------------
CREATE TABLE shot_versions (
    id                   TEXT PRIMARY KEY,
    shot_id              TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    kind                 TEXT NOT NULL CHECK (kind IN ('original', 'adopted')),
    image_path           TEXT NOT NULL,
    width                INTEGER,
    height               INTEGER,
    file_size            INTEGER,
    source_generation_id TEXT REFERENCES generation_records(id) ON DELETE SET NULL,
    source_candidate_id  TEXT REFERENCES generation_candidates(id) ON DELETE SET NULL,
    is_current           INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
    recheck_status       TEXT CHECK (recheck_status IS NULL
                                     OR recheck_status IN ('pending', 'running', 'consistent',
                                                           'inconsistent', 'unknown', 'failed')),
    recheck_at           TEXT,
    adoption_id          TEXT,
    created_at           TEXT NOT NULL
);

-- 观察 ---------------------------------------------------------------
CREATE TABLE observations (
    id                TEXT PRIMARY KEY,
    task_id           TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    shot_id           TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    version_id        TEXT NOT NULL REFERENCES shot_versions(id) ON DELETE CASCADE,
    attribute_id      TEXT NOT NULL,
    observed_value    TEXT,
    visibility        TEXT NOT NULL CHECK (visibility IN ('visible', 'partial', 'not_visible')),
    visibility_reason TEXT,
    evidence          TEXT,
    confidence        TEXT CHECK (confidence IS NULL
                                  OR confidence IN ('high', 'medium', 'low')),
    subject_json      TEXT,
    raw_json          TEXT,
    created_at        TEXT NOT NULL,
    UNIQUE (version_id, attribute_id)
);

-- 判定单元 -----------------------------------------------------------
CREATE TABLE judgements (
    id           TEXT PRIMARY KEY,
    task_id      TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    shot_id      TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    version_id   TEXT NOT NULL REFERENCES shot_versions(id) ON DELETE CASCADE,
    attribute_id TEXT NOT NULL,
    verdict      TEXT NOT NULL
                 CHECK (verdict IN ('consistent', 'inconsistent', 'unknown',
                                    'waived', 'observed_only')),
    expected     TEXT,
    observed     TEXT,
    reason       TEXT,
    confidence   TEXT CHECK (confidence IS NULL OR confidence IN ('high', 'medium', 'low')),
    severity     TEXT CHECK (severity IS NULL OR severity IN ('high', 'medium', 'low')),
    issue_type   TEXT CHECK (issue_type IS NULL
                             OR issue_type IN ('profile_violation', 'cross_shot_mismatch')),
    created_at   TEXT NOT NULL,
    UNIQUE (version_id, attribute_id)
);

-- 确定问题 -----------------------------------------------------------
CREATE TABLE issues (
    id             TEXT PRIMARY KEY,
    task_id        TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    shot_id        TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    judgement_id   TEXT NOT NULL REFERENCES judgements(id) ON DELETE CASCADE,
    attribute_id   TEXT NOT NULL,
    attribute_name TEXT NOT NULL,
    type           TEXT NOT NULL CHECK (type IN ('profile_violation', 'cross_shot_mismatch')),
    expected       TEXT,
    observed       TEXT,
    evidence       TEXT NOT NULL,
    confidence     TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    severity       TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
    waiver_status  TEXT NOT NULL DEFAULT 'not_applicable'
                   CHECK (waiver_status IN ('not_applicable', 'waived')),
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    closed_at      TEXT,
    created_at     TEXT NOT NULL
);

-- 无法判断 -----------------------------------------------------------
CREATE TABLE unknown_items (
    id             TEXT PRIMARY KEY,
    task_id        TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    shot_id        TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    judgement_id   TEXT NOT NULL REFERENCES judgements(id) ON DELETE CASCADE,
    attribute_id   TEXT NOT NULL,
    attribute_name TEXT NOT NULL,
    visibility     TEXT NOT NULL,
    reason         TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

-- 剧本豁免 -----------------------------------------------------------
CREATE TABLE waivers (
    id             TEXT PRIMARY KEY,
    task_id        TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    shot_id        TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    judgement_id   TEXT REFERENCES judgements(id) ON DELETE CASCADE,
    attribute_id   TEXT NOT NULL,
    attribute_name TEXT NOT NULL,
    scope_json     TEXT,
    script_evidence TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

-- 疑似问题 -----------------------------------------------------------
CREATE TABLE suspected_issues (
    id             TEXT PRIMARY KEY,
    task_id        TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    shot_id        TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    judgement_id   TEXT NOT NULL REFERENCES judgements(id) ON DELETE CASCADE,
    attribute_id   TEXT NOT NULL,
    attribute_name TEXT NOT NULL,
    expected       TEXT,
    observed       TEXT,
    evidence       TEXT,
    confidence     TEXT,
    reason         TEXT,
    status         TEXT NOT NULL DEFAULT 'open'
                   CHECK (status IN ('open', 'confirmed', 'dismissed')),
    created_at     TEXT NOT NULL
);

-- 修正建议 -----------------------------------------------------------
CREATE TABLE suggestions (
    id                   TEXT PRIMARY KEY,
    task_id              TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    issue_id             TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    shot_id              TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    revised_prompt       TEXT NOT NULL,
    negative_prompt      TEXT,
    negative_prompt_mode TEXT NOT NULL DEFAULT 'merged',
    key_points_json      TEXT,
    reference_shots_json TEXT,
    rationale            TEXT,
    card_draw_plan_json  TEXT,
    status               TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('ready', 'failed')),
    prompt_version       TEXT,
    error_message        TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);

-- 采用记录 -----------------------------------------------------------
CREATE TABLE adoptions (
    id                   TEXT PRIMARY KEY,
    task_id              TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    shot_id              TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    generation_id        TEXT NOT NULL REFERENCES generation_records(id),
    candidate_id         TEXT NOT NULL REFERENCES generation_candidates(id),
    adopted_at           TEXT NOT NULL,
    adopted_by           TEXT NOT NULL DEFAULT 'local-user',
    precheck_overall     TEXT,
    overridden_precheck  INTEGER NOT NULL DEFAULT 0 CHECK (overridden_precheck IN (0, 1)),
    original_version_id  TEXT,
    new_version_id       TEXT,
    recheck_status       TEXT,
    recheck_at           TEXT,
    recheck_result_json  TEXT,
    created_at           TEXT NOT NULL
);

-- 非敏感配置 ---------------------------------------------------------
CREATE TABLE settings (
    key        TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 任务事件（脱敏） ----------------------------------------------------
CREATE TABLE events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      TEXT,
    type         TEXT NOT NULL,
    payload_json TEXT,
    request_id   TEXT,
    created_at   TEXT NOT NULL
);

-- 调用用量 -----------------------------------------------------------
CREATE TABLE usage_records (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id        TEXT REFERENCES tasks(id) ON DELETE CASCADE,
    kind           TEXT NOT NULL
                   CHECK (kind IN ('profile', 'observe', 'suggestion', 'precheck', 'generation')),
    provider       TEXT,
    model          TEXT,
    request_id     TEXT,
    input_images   INTEGER NOT NULL DEFAULT 0,
    input_tokens   INTEGER NOT NULL DEFAULT 0,
    output_tokens  INTEGER NOT NULL DEFAULT 0,
    image_count    INTEGER NOT NULL DEFAULT 0,
    estimated_cost REAL,
    currency       TEXT NOT NULL DEFAULT 'CNY',
    created_at     TEXT NOT NULL
);
