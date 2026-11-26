"""Markdown / JSON 报告导出（F-11 / 技术方案 7.5）。

- 与页面使用同一份 `build_report` 结果，不另行计算统计；
- 不包含 API Key、绝对路径、内部请求头或远程图片 URL；
- JSON 额外包含当前版本的观察与判定明细；Markdown 覆盖问题、建议、生成与采用记录。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote

from ..core.constants import ATTRIBUTE_NAMES, SCHEMA_VERSION
from ..core.errors import AppError
from ..core.timeutil import now_iso
from ..repositories import observation_repo, shot_repo
from ..repositories.database import Database
from . import report_service

_SAFE_NAME = re.compile(r"[^\w一-鿿.-]+", re.UNICODE)

_RECHECK_LABELS = {
    "consistent": "一致（问题关闭）",
    "inconsistent": "仍不一致（问题保持开启）",
    "unknown": "无法判断",
    "failed": "复检失败",
    "running": "复检中",
}
_CANDIDATE_LABELS = {
    "pass": "预检通过", "partial": "部分符合", "fail": "不建议", "unknown": "无结论",
}


def _clean_gallery(gallery: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = (
        "shotCode", "seq", "analysisStatus", "conclusionStatus",
        "issueCount", "unknownCount", "errorCode", "errorMessage",
    )
    return [{key: item.get(key) for key in keys} for item in gallery]


def _clean_generation(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "shotId": record.get("shotId"),
        "issueIds": record.get("issueIds") or [],
        "provider": record.get("provider"),
        "model": record.get("model"),
        "prompt": record.get("prompt"),
        "negativePrompt": record.get("negativePrompt"),
        "negativePromptMode": record.get("negativePromptMode"),
        "requestedCount": record.get("requestedCount"),
        "succeededCount": record.get("succeededCount"),
        "failedCount": record.get("failedCount"),
        "status": record.get("status"),
        "precheckStatus": record.get("precheckStatus"),
        "precheckMode": record.get("precheckMode"),
        "errorCode": record.get("errorCode"),
        "errorMessage": record.get("errorMessage"),
        "supportedParams": record.get("supportedParams"),
        "candidates": [
            {
                "candidateCode": item.get("candidateCode"),
                "candidateIndex": item.get("candidateIndex"),
                "state": item.get("state"),
                "precheck": item.get("precheck"),
                "adopted": item.get("adopted"),
                "adoptedAt": item.get("adoptedAt"),
                "seed": item.get("seed"),
            }
            for item in record.get("candidates") or []
        ],
    }


async def _shot_details(db: Database, task_id: str) -> tuple[list[dict], list[dict]]:
    shots = await shot_repo.get_shots(db, task_id)
    observations_out: list[dict] = []
    judgements_out: list[dict] = []
    for shot in shots:
        version = (
            await shot_repo.get_current_version(db, shot["id"])
            if shot["current_version_id"]
            else None
        )
        observations: list[dict] = []
        judgements: list[dict] = []
        if version:
            rows = await observation_repo.list_for_shot_version(
                db, shot["id"], version["id"]
            )
            observation_map = {row["attribute_id"]: row for row in rows}
            judgement_rows = await db.fetchall(
                "SELECT * FROM judgements WHERE version_id = ? ORDER BY rowid",
                (version["id"],),
            )
            verdict_map = {row["attribute_id"]: row["verdict"] for row in judgement_rows}
            for attribute_id, row in observation_map.items():
                observations.append(
                    {
                        "attributeId": attribute_id,
                        "attributeName": ATTRIBUTE_NAMES.get(attribute_id, attribute_id),
                        "observedValue": row["observed_value"],
                        "visibility": row["visibility"],
                        "visibilityReason": row["visibility_reason"],
                        "evidence": row["evidence"],
                        "confidence": row["confidence"],
                        "verdict": verdict_map.get(attribute_id),
                    }
                )
            for row in judgement_rows:
                judgements.append(
                    {
                        "attributeId": row["attribute_id"],
                        "attributeName": ATTRIBUTE_NAMES.get(
                            row["attribute_id"], row["attribute_id"]
                        ),
                        "verdict": row["verdict"],
                        "expected": row["expected"],
                        "observed": row["observed"],
                        "reason": row["reason"],
                        "confidence": row["confidence"],
                        "severity": row["severity"],
                        "issueType": row["issue_type"],
                    }
                )
        observations_out.append(
            {
                "shotCode": shot["shot_code"],
                "seq": shot["seq"],
                "analysisStatus": shot["analysis_status"],
                "conclusionStatus": shot["conclusion_status"],
                "errorCode": shot["analysis_error_code"],
                "errorMessage": shot["analysis_error_message"],
                "currentVersionKind": version["kind"] if version else None,
                "observations": observations,
                "judgements": judgements,
            }
        )
        judgements_out.extend(
            {"shotCode": shot["shot_code"], **item} for item in judgements
        )
    return observations_out, judgements_out


async def build_export(
    db: Database, task_id: str, fmt: str
) -> tuple[bytes, str, str]:
    if fmt not in ("md", "json"):
        raise AppError("invalid_request", "仅支持 Markdown 或 JSON 导出。", status_code=400)
    report = await report_service.build_report(db, task_id)
    shots, judgements = await _shot_details(db, task_id)
    exported_at = now_iso()
    mode = report["task"].get("mode") or "live"
    data_notice = "演示数据" if mode == "demo" else None
    payload = {
        "schemaVersion": report.get("schemaVersion") or SCHEMA_VERSION,
        "exportedAt": exported_at,
        "mode": mode,
        "dataNotice": data_notice,
        "summary": report["summary"],
        "stats": report["stats"],
        "task": report["task"],
        "profile": report["profile"],
        "script": report["script"],
        "gallery": _clean_gallery(report["gallery"]),
        "matrix": report["matrix"],
        "shots": shots,
        "judgements": judgements,
        "issues": report["issues"],
        "suspectedIssues": report["suspectedIssues"],
        "unknownItems": report["unknownItems"],
        "waivers": report["waivers"],
        "suggestions": report["suggestions"],
        "generationRecords": [
            _clean_generation(item) for item in report["generationRecords"]
        ],
        "adoptions": report["adoptions"],
        "usageSummary": report["usageSummary"],
    }

    token = (report["task"].get("characterName") or report["task"].get("name") or "角色").strip()
    token = _SAFE_NAME.sub("_", token)[:40] or "角色"
    stamp = datetime.fromisoformat(exported_at).strftime("%Y%m%d_%H%M")
    if fmt == "json":
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        return content.encode("utf-8"), "application/json; charset=utf-8", f"一致性检查_{token}_{stamp}.json"
    return _markdown(payload).encode("utf-8"), "text/markdown; charset=utf-8", f"一致性检查_{token}_{stamp}.md"


def content_disposition(filename: str) -> str:
    suffix = ".json" if filename.lower().endswith(".json") else ".md"
    ascii_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename) or f"report{suffix}"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _fence(value: str) -> str:
    fence = "````" if "```" in value else "```"
    return f"{fence}text\n{value}\n{fence}"


def _markdown(payload: dict[str, Any]) -> str:
    task = payload["task"]
    stats = payload["stats"]
    lines: list[str] = []
    lines.append("# 角色形象一致性检查报告")
    lines.append("")
    lines.append(f"- 生成时间：{payload['exportedAt']}")
    lines.append(f"- 数据模式：{'演示数据' if payload['mode'] == 'demo' else '真实本地任务'}")
    lines.append(f"- 角色：{task.get('characterName') or '—'}")
    lines.append(f"- 任务：{task.get('name') or '—'}")
    lines.append(f"- 任务状态：{task.get('status') or '—'}")
    lines.append("")
    lines.append("## 结论摘要")
    lines.append("")
    lines.append(payload["summary"])
    lines.append("")
    lines.append("## 统计")
    lines.append("")
    lines.append("| 项目 | 数量 |")
    lines.append("| --- | ---: |")
    for label, key in (
        ("镜头数", "totalShots"), ("判定单元", "totalUnits"), ("一致", "consistent"),
        ("不一致", "inconsistent"), ("确定问题", "confirmedIssues"),
        ("疑似问题", "suspectedIssues"), ("无法判断", "unknown"),
        ("剧本豁免", "waived"), ("仅记录", "observedOnly"), ("失败镜头", "failedShots"),
    ):
        lines.append(f"| {label} | {stats.get(key, 0)} |")
    lines.append("")

    profile_attributes = (payload.get("profile") or {}).get("attributes") or []
    if profile_attributes:
        lines.append("## 角色设定")
        lines.append("")
        lines.append("| 要素 | 设定值 | 来源 |")
        lines.append("| --- | --- | --- |")
        for item in profile_attributes:
            lines.append(
                f"| {ATTRIBUTE_NAMES.get(item.get('id'), item.get('name') or item.get('id'))} "
                f"| {_cell(item.get('value') or '未定义')} | {_cell(item.get('source'))} |"
            )
        lines.append("")

    script = payload.get("script") or {}
    if script:
        lines.append("## 剧本规则")
        lines.append("")
        lines.append(f"- 规则：{script.get('ruleBadge') or '严格比对 · 无豁免'}")
        warnings = script.get("warnings") or []
        for warning in warnings:
            lines.append(f"- 提示：{warning}")
        lines.append("")

    lines.append("## 镜头总览")
    lines.append("")
    lines.append("| 镜头 | 分析状态 | 结论 | 问题数 | 无法判断 |")
    lines.append("| --- | --- | --- | ---: | ---: |")
    for shot in payload["gallery"]:
        lines.append(
            f"| {_cell(shot['shotCode'])} | {_cell(shot.get('analysisStatus'))} "
            f"| {_cell(shot.get('conclusionStatus') or '—')} "
            f"| {shot.get('issueCount', 0)} | {shot.get('unknownCount', 0)} |"
        )
    lines.append("")

    def section(title: str, items: list[dict], renderer) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("无。")
            lines.append("")
            return
        for item in items:
            renderer(item)
        lines.append("")

    def issue_block(item: dict) -> None:
        lines.append(f"### {item['id']} · {item['shotCode']} · {item['attributeName']}")
        lines.append("")
        lines.append(f"- 设定期望：{item.get('expected') or '—'}")
        lines.append(f"- 实际观察：{item.get('observed') or '—'}")
        lines.append(f"- 证据：{item.get('evidence') or '—'}")
        lines.append(f"- 严重度 / 置信度：{item.get('severity') or '—'} / {item.get('confidence') or '—'}")
        lines.append(f"- 状态：{item.get('status') or 'open'}")
        lines.append("")

    section("确定问题", payload["issues"], issue_block)

    def suspected_block(item: dict) -> None:
        lines.append(f"### {item['id']} · {item['shotCode']} · {item['attributeName']}")
        lines.append("")
        lines.append(f"- 观察：{item.get('observed') or '—'}")
        lines.append(f"- 证据 / 原因：{item.get('evidence') or item.get('reason') or '—'}")
        lines.append(f"- 置信度：{item.get('confidence') or '—'}")
        lines.append("")

    section("疑似问题", payload["suspectedIssues"], suspected_block)

    def unknown_block(item: dict) -> None:
        lines.append(f"- **{item['id']} · {item['shotCode']} · {item['attributeName']}**：{item.get('reason') or '无法判断'}")
    section("无法判断", payload["unknownItems"], unknown_block)

    def waiver_block(item: dict) -> None:
        lines.append(f"- **{item['id']} · {item['shotCode']} · {item['attributeName']}**：{item.get('scriptEvidence') or '剧本豁免'}")
    section("剧本豁免", payload["waivers"], waiver_block)

    lines.append("## 修正建议与抽卡")
    lines.append("")
    suggestions = payload["suggestions"]
    if not suggestions:
        lines.append("无。")
        lines.append("")
    for item in suggestions:
        lines.append(f"### {item['issueId']} · {item['shotCode']} · {'模型建议' if item.get('source') == 'ai' else '本地规则建议'}")
        lines.append("")
        lines.append("修正提示词：")
        lines.append("")
        lines.append(_fence(item.get("revisedPrompt") or ""))
        lines.append("")
        if item.get("negativePrompt"):
            lines.append(f"负向内容（合并模式）：{item['negativePrompt']}")
            lines.append("")
        points = item.get("keyPoints") or []
        if points:
            lines.append("修改要点：")
            for point in points:
                lines.append(f"- {point}")
            lines.append("")
        plan = item.get("cardDrawPlan") or {}
        if plan:
            lines.append(f"- 参考镜头：{', '.join(plan.get('referenceShots') or []) or '无'}")
            lines.append(f"- 每批张数：{plan.get('batchSize') or 4}")
            for criterion in plan.get("selectionCriteria") or []:
                lines.append(f"- 挑选标准：{criterion}")
            lines.append(f"- 升级策略：{plan.get('escalation') or '—'}")
            lines.append("")

    lines.append("## 生成记录")
    lines.append("")
    records = payload["generationRecords"]
    if not records:
        lines.append("无。")
        lines.append("")
    for record in records:
        lines.append(
            f"### {record['id']} · {record.get('model') or '—'} · "
            f"{record.get('status')} / 预检 {record.get('precheckStatus')}"
        )
        lines.append("")
        lines.append(f"- 请求 {record.get('requestedCount')} 张，成功 {record.get('succeededCount')} 张，失败 {record.get('failedCount')} 张")
        if record.get("errorMessage"):
            lines.append(f"- 错误：{record['errorMessage']}")
        lines.append("- 生成提示词：")
        lines.append("")
        lines.append(_fence(record.get("prompt") or ""))
        lines.append("")
        for candidate in record.get("candidates") or []:
            precheck = candidate.get("precheck") or {}
            state_label = _CANDIDATE_LABELS.get(
                candidate.get("state"), candidate.get("state") or "无结论"
            )
            lines.append(
                f"- {candidate.get('candidateCode')} · 状态 {state_label} "
                f"{'· 已采用' if candidate.get('adopted') else ''}"
            )
            if precheck.get("summary"):
                lines.append(f"  - 预检：{precheck['summary']}")
        lines.append("")

    lines.append("## 采用记录")
    lines.append("")
    adoptions = payload["adoptions"]
    if not adoptions:
        lines.append("无。")
        lines.append("")
    for adoption in adoptions:
        recheck_label = _RECHECK_LABELS.get(
            adoption.get("recheckStatus"), adoption.get("recheckStatus") or "—"
        )
        lines.append(
            f"- {adoption.get('candidateCode') or adoption.get('candidateId')} · "
            f"{adoption.get('shotCode') or adoption.get('shotId')} · 复检 "
            f"{recheck_label} · 采用于 {adoption.get('adoptedAt') or '—'}"
        )
        if adoption.get("overriddenPrecheck"):
            lines.append("  - 已记录推翻预检结果")
        result = adoption.get("recheckResult") or {}
        if result.get("remainingIssueIds"):
            lines.append(f"  - 复检后仍开启问题：{', '.join(result['remainingIssueIds'])}")
    lines.append("")

    failed = [shot for shot in payload["gallery"] if shot.get("analysisStatus") == "failed"]
    if failed:
        lines.append("## 失败镜头与处理建议")
        lines.append("")
        for shot in failed:
            lines.append(
                f"- {shot['shotCode']}：{shot.get('errorMessage') or '观察失败'}；"
                "建议检查素材后重新观察该镜头。"
            )
        lines.append("")

    usage = payload.get("usageSummary") or {}
    lines.append("## 用量")
    lines.append("")
    lines.append(f"- 分析调用：{usage.get('analysisCalls', 0)} 次")
    lines.append(f"- 生成调用：{usage.get('generationCalls', 0)} 次")
    if usage.get("estimatedCost") is not None:
        lines.append(f"- 预估费用：{usage['estimatedCost']} {usage.get('currency') or 'CNY'}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("本报告由本地工具生成；不包含 API Key、绝对路径或远程图片地址。")
    if payload.get("dataNotice"):
        lines.append("")
        lines.append(f"> {payload['dataNotice']}：本报告来自演示任务，不进入真实历史统计。")
    return "\n".join(lines)
