-- 003_analysis_progress.sql
-- 异步分析进度持久化（阶段三）。进程重启后仍能展示阶段与百分比。

ALTER TABLE tasks ADD COLUMN analysis_stage INTEGER;
ALTER TABLE tasks ADD COLUMN analysis_stage_name TEXT;
ALTER TABLE tasks ADD COLUMN analysis_progress INTEGER NOT NULL DEFAULT 0;
ALTER TABLE tasks ADD COLUMN analysis_eta_seconds INTEGER;

ALTER TABLE shots ADD COLUMN analysis_error_code TEXT;
ALTER TABLE shots ADD COLUMN analysis_error_message TEXT;

CREATE INDEX idx_tasks_status_progress ON tasks(status, analysis_progress);
