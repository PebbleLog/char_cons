"""结构化报告：页面、矩阵、摘要、导出统一从同一份 judgements 派生。"""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from ..core.constants import ATTRIBUTE_IDS, ATTRIBUTE_NAMES, SCHEMA_VERSION
from ..core.errors import AppError
from ..repositories import (
    generation_repo,
    judgement_repo,
    shot_repo,
    task_repo,
    usage_repo,
)
from ..repositories.database import Database
from . import generation_service, suggestion_service


def _load(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _shot_urls(task_id: str, shot_id: str, version_id: str | None = None) -> dict[str, str]:
    base = f"/api/tasks/{task_id}/shots/{shot_id}/image"
    # thumb/current 随采用版本变化；带版本参数让浏览器缓存随版本失效，避免采用后仍显示旧图。
    version = f"&v={version_id}" if version_id else ""
    return {
        "imageUrl": f"{base}?variant=original",
        "thumbUrl": f"{base}?variant=thumb{version}",
        "currentUrl": f"{base}?variant=current{version}",
    }


def _issue_serialize(row: aiosqlite.Row, shot_code: str) -> dict[str, Any]:
    return {
        "id": row["id"],
        "shotId": row["shot_id"],
        "shotCode": shot_code,
        "attributeId": row["attribute_id"],
        "attributeName": row["attribute_name"],
        "type": row["type"],
        "expected": row["expected"],
        "observed": row["observed"],
        "evidence": row["evidence"],
        "confidence": row["confidence"],
        "severity": row["severity"],
        "status": row["status"],
        "waiverStatus": row["waiver_status"],
    }


def _unknown_serialize(row: aiosqlite.Row, shot_code: str) -> dict[str, Any]:
    return {
        "id": row["id"],
        "shotId": row["shot_id"],
        "shotCode": shot_code,
        "attributeId": row["attribute_id"],
        "attributeName": row["attribute_name"],
        "visibility": row["visibility"],
        "reason": row["reason"],
    }


def _summary(stats: dict[str, int], issues: list[dict], unknowns: list[dict], name: str) -> str:
    if stats["totalUnits"] == 0:
        return "全部镜头观察失败，未生成一致性结论。"
    if issues:
        locations = "、".join(
            f"{issue['shotCode']} 的{issue['attributeName']}" for issue in issues[:4]
        )
        text = (
            f"{name or '该角色'}在 {stats['totalShots']} 个镜头中有 "
            f"{len(issues)} 处确定不一致，集中在 {locations}"
        )
    else:
        text = f"{name or '该角色'}的 {stats['totalShots']} 个镜头中已无确定不一致"
    if unknowns:
        text += f"；另有 {len(unknowns)} 项信息因画面不可见或证据不足，无法判断"
    if stats["failedShots"]:
        text += f"；{stats['failedShots']} 个镜头观察失败，报告仅覆盖成功镜头"
    return text + "。"


async def build_report(db: Database, task_id: str) -> dict[str, Any]:
    task = await task_repo.get_task(db, task_id)
    if task is None:
        raise AppError("not_found", "任务不存在或已被删除。", status_code=404)

    units = await judgement_repo.list_units(db, task_id)
    if not units:
        if task["status"] in ("running", "retrying"):
            raise AppError(
                "report_not_ready", "分析尚未完成，报告暂不可用。", status_code=409, retryable=True
            )
        raise AppError(
            "report_unavailable", "该任务没有可用的检测报告。", status_code=409
        )

    shots = await shot_repo.get_shots(db, task_id)
    issues_rows = await judgement_repo.list_issues(db, task_id)
    unknown_rows = await judgement_repo.list_unknowns(db, task_id)
    waiver_rows = await judgement_repo.list_waivers(db, task_id)
    suspected_rows = await judgement_repo.list_suspected(db, task_id)
    shot_code = {shot["id"]: shot["shot_code"] for shot in shots}

    issues = [_issue_serialize(row, shot_code.get(row["shot_id"], "")) for row in issues_rows]
    unknowns = [
        _unknown_serialize(row, shot_code.get(row["shot_id"], "")) for row in unknown_rows
    ]
    waivers = [
        {
            "id": row["id"],
            "shotId": row["shot_id"],
            "shotCode": shot_code.get(row["shot_id"], ""),
            "attributeId": row["attribute_id"],
            "attributeName": row["attribute_name"],
            "scope": _load(row["scope_json"]),
            "scriptEvidence": row["script_evidence"],
        }
        for row in waiver_rows
    ]
    suspected = [
        {
            "id": row["id"],
            "shotId": row["shot_id"],
            "shotCode": shot_code.get(row["shot_id"], ""),
            "attributeId": row["attribute_id"],
            "attributeName": row["attribute_name"],
            "expected": row["expected"],
            "observed": row["observed"],
            "evidence": row["evidence"],
            "confidence": row["confidence"],
            "reason": row["reason"],
            "status": row["status"],
        }
        for row in suspected_rows
    ]

    counts = {verdict: 0 for verdict in ("consistent", "inconsistent", "unknown", "waived", "observed_only")}
    for row in units:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    failed_shots = sum(1 for shot in shots if shot["analysis_status"] == "failed")
    stats = {
        "totalShots": len(shots),
        "totalUnits": len(units),
        "failedShots": failed_shots,
        "consistent": counts["consistent"],
        "inconsistent": counts["inconsistent"],
        "confirmedIssues": len(issues),
        "unknown": counts["unknown"],
        "waived": counts["waived"],
        "observedOnly": counts["observed_only"],
        "suspectedIssues": len(suspected),
    }

    issues_by_shot: dict[str, list[dict]] = {}
    for issue in issues:
        issues_by_shot.setdefault(issue["shotId"], []).append(issue)
    unknown_by_shot: dict[str, list[dict]] = {}
    for item in unknowns:
        unknown_by_shot.setdefault(item["shotId"], []).append(item)

    gallery = []
    for shot in shots:
        version = await shot_repo.get_current_version(db, shot["id"])
        is_adopted = bool(version and version["kind"] == "adopted")
        adopted_candidate_code = None
        if is_adopted and version["source_generation_id"] and version["source_candidate_id"]:
            candidate = await generation_repo.get_candidate(
                db, version["source_generation_id"], version["source_candidate_id"]
            )
            adopted_candidate_code = candidate["candidate_code"] if candidate else None
        gallery.append(
            {
                "shotId": shot["id"],
                "shotCode": shot["shot_code"],
                "seq": shot["seq"],
                "analysisStatus": shot["analysis_status"],
                "conclusionStatus": shot["conclusion_status"],
                "issueCount": len(issues_by_shot.get(shot["id"], [])),
                "unknownCount": len(unknown_by_shot.get(shot["id"], [])),
                "errorCode": shot["analysis_error_code"],
                "errorMessage": shot["analysis_error_message"],
                "isAdopted": is_adopted,
                "currentVersionId": version["id"] if version else None,
                "adoptedCandidateCode": adopted_candidate_code,
                "versionLabel": (
                    f"已采用 {adopted_candidate_code}" if is_adopted and adopted_candidate_code
                    else "已采用" if is_adopted
                    else "原图"
                ),
                **_shot_urls(
                    task_id, shot["id"], version["id"] if version else None
                ),
            }
        )

    unit_map = {(row["shot_id"], row["attribute_id"]): row for row in units}
    issue_by_judgement = {row["judgement_id"]: row for row in issues_rows}
    unknown_by_judgement = {row["judgement_id"]: row for row in unknown_rows}
    waiver_by_judgement = {
        row["judgement_id"]: row for row in waiver_rows if row["judgement_id"]
    }
    profile = _load(task["profile_json"]) or {}
    profile_values = {
        item.get("id"): item.get("value")
        for item in profile.get("attributes", [])
        if isinstance(item, dict)
    }

    matrix = []
    for attribute_id in ATTRIBUTE_IDS:
        cells = []
        for shot in shots:
            unit = unit_map.get((shot["id"], attribute_id))
            if unit is None:
                cells.append(
                    {
                        "shotId": shot["id"],
                        "shotCode": shot["shot_code"],
                        "verdict": "failed" if shot["analysis_status"] == "failed" else None,
                        "observed": None,
                        "issueId": None,
                        "unknownId": None,
                        "waiverId": None,
                    }
                )
                continue
            issue = issue_by_judgement.get(unit["id"])
            unknown = unknown_by_judgement.get(unit["id"])
            waiver = waiver_by_judgement.get(unit["id"])
            cells.append(
                {
                    "shotId": shot["id"],
                    "shotCode": shot["shot_code"],
                    "verdict": unit["verdict"],
                    "observed": unit["observed"],
                    "expected": unit["expected"],
                    "reason": unit["reason"],
                    "confidence": unit["confidence"],
                    "issueId": issue["id"] if issue else None,
                    "unknownId": unknown["id"] if unknown else None,
                    "waiverId": waiver["id"] if waiver else None,
                }
            )
        matrix.append(
            {
                "attributeId": attribute_id,
                "attributeName": ATTRIBUTE_NAMES[attribute_id],
                "expected": profile_values.get(attribute_id),
                "cells": cells,
            }
        )

    suggestions = await suggestion_service.list_for_report(db, task_id)
    generation_data = await generation_service.list_for_report(db, task_id)

    usage = await usage_repo.summary_for_task(db, task_id)
    analysis_calls = sum(
        int(item.get("calls", 0)) for kind, item in usage.items() if kind in ("profile", "observe", "suggestion", "precheck")
    )
    generation_calls = sum(
        int(item.get("calls", 0)) for kind, item in usage.items() if kind == "generation"
    )
    estimated_cost = sum(float(item.get("cost", 0) or 0) for item in usage.values())

    summary = _summary(stats, issues, unknowns, task["character_name"] or "")
    return {
        "schemaVersion": task["schema_version"] or SCHEMA_VERSION,
        "promptVersion": task["prompt_version"],
        "analysisModel": task["analysis_model"],
        "task": {
            "id": task["id"],
            "name": task["name"],
            "characterName": task["character_name"],
            "mode": task["mode"],
            "status": task["status"],
            "profileRaw": task["profile_raw"],
            "scriptRaw": task["script_raw"],
            "createdAt": task["created_at"],
            "completedAt": task["completed_at"],
            "errorCode": task["error_code"],
            "errorMessage": task["error_message"],
        },
        "profile": profile,
        "script": _load(task["script_context_json"]),
        "summary": summary,
        "stats": stats,
        "gallery": gallery,
        "matrix": matrix,
        "issues": issues,
        "suspectedIssues": suspected,
        "unknownItems": unknowns,
        "waivers": waivers,
        "suggestions": suggestions,
        "generationRecords": generation_data["generations"],
        "adoptions": generation_data["adoptions"],
        "usageSummary": {
            "analysisCalls": analysis_calls,
            "generationCalls": generation_calls,
            "estimatedCost": estimated_cost if estimated_cost else None,
            "currency": "CNY",
        },
    }
