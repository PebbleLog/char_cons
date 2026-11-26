-- 004_generation_loop.sql
-- 阶段五：生成闭环所需的版本关联与候选图元数据。
-- 只新增列/索引，不修改既有数据；历史行通过 judgement_id 回填版本。

ALTER TABLE issues ADD COLUMN version_id TEXT;
ALTER TABLE unknown_items ADD COLUMN version_id TEXT;
ALTER TABLE waivers ADD COLUMN version_id TEXT;
ALTER TABLE suspected_issues ADD COLUMN version_id TEXT;

UPDATE issues
SET version_id = (SELECT j.version_id FROM judgements j WHERE j.id = issues.judgement_id)
WHERE version_id IS NULL;

UPDATE unknown_items
SET version_id = (SELECT j.version_id FROM judgements j WHERE j.id = unknown_items.judgement_id)
WHERE version_id IS NULL;

UPDATE waivers
SET version_id = (SELECT j.version_id FROM judgements j WHERE j.id = waivers.judgement_id)
WHERE judgement_id IS NOT NULL;

UPDATE suspected_issues
SET version_id = (SELECT j.version_id FROM judgements j WHERE j.id = suspected_issues.judgement_id)
WHERE version_id IS NULL;

CREATE INDEX idx_issues_current ON issues(task_id, shot_id, version_id);
CREATE INDEX idx_unknown_current ON unknown_items(task_id, shot_id, version_id);
CREATE INDEX idx_waiver_current ON waivers(task_id, shot_id, version_id);
CREATE INDEX idx_suspected_current ON suspected_issues(task_id, shot_id, version_id);

-- 候选图缩略图、随机种子与耗时（便于复现与轻量加载）
ALTER TABLE generation_candidates ADD COLUMN thumb_path TEXT;
ALTER TABLE generation_candidates ADD COLUMN seed INTEGER;
ALTER TABLE generation_candidates ADD COLUMN elapsed_ms INTEGER;

-- 修正建议来源：ai / local（本地规则回退时必须可追溯，不冒充模型结果）
ALTER TABLE suggestions ADD COLUMN source TEXT;
