-- 002_indexes.sql
-- 技术方案 6.3 / 6.4 列出的查询索引。

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_mode_updated ON tasks(mode, updated_at);
CREATE INDEX idx_tasks_mode_status_updated ON tasks(mode, status, updated_at);

CREATE INDEX idx_shots_task ON shots(task_id, seq);

CREATE INDEX idx_versions_shot ON shot_versions(shot_id, is_current);

CREATE INDEX idx_obs_shot ON observations(shot_id, attribute_id);

CREATE INDEX idx_judgements_task_verdict ON judgements(task_id, verdict);
CREATE INDEX idx_judgements_task_shot ON judgements(task_id, shot_id);

CREATE INDEX idx_issues_task_status ON issues(task_id, status);
CREATE INDEX idx_issues_shot ON issues(shot_id);

CREATE INDEX idx_unknown_task ON unknown_items(task_id);

CREATE INDEX idx_suspected_task ON suspected_issues(task_id, status);

CREATE INDEX idx_suggestions_task_issue ON suggestions(task_id, issue_id);

CREATE INDEX idx_gen_task_shot ON generation_records(task_id, shot_id);
CREATE INDEX idx_gen_status ON generation_records(status);

CREATE INDEX idx_adoptions_task_shot ON adoptions(task_id, shot_id);
CREATE INDEX idx_adoptions_candidate ON adoptions(candidate_id);

CREATE INDEX idx_events_task ON events(task_id, created_at);
CREATE INDEX idx_events_type ON events(type);

CREATE INDEX idx_usage_task ON usage_records(task_id, kind);
CREATE INDEX idx_usage_request ON usage_records(request_id);
