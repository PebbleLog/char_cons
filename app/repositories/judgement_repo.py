"""判定、问题、无法判断、豁免、疑似问题持久化。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import aiosqlite

from ..core.ids import new_id
from ..core.timeutil import now_iso
from .database import Database

if TYPE_CHECKING:  # 仅类型标注，避免持久层依赖业务层
    from ..services.judgment_engine import JudgmentResult


async def clear_for_task(db: Database, task_id: str) -> None:
    # issues / unknown_items / suspected_issues / waivers / suggestions 由外键级联删除
    await db.execute("DELETE FROM judgements WHERE task_id = ?", (task_id,))
    await db.execute("DELETE FROM issues WHERE task_id = ?", (task_id,))
    await db.execute("DELETE FROM unknown_items WHERE task_id = ?", (task_id,))
    await db.execute("DELETE FROM waivers WHERE task_id = ?", (task_id,))
    await db.execute("DELETE FROM suspected_issues WHERE task_id = ?", (task_id,))


async def persist_result(
    conn: aiosqlite.Connection, task_id: str, result: "JudgmentResult"
) -> None:
    now = now_iso()
    unit_ids: dict[int, str] = {}
    # ID 是全局主键，不能按任务从 001 重新编号，否则第二个任务会冲突。
    next_issue = await _next_number(conn, "issues", "ISS")
    next_unknown = await _next_number(conn, "unknown_items", "UNK")
    next_waiver = await _next_number(conn, "waivers", "WVR")
    next_suspected = await _next_number(conn, "suspected_issues", "SUS")

    for unit in result.units:
        judgement_id = new_id("jdg")
        unit_ids[id(unit)] = judgement_id
        await conn.execute(
            """
            INSERT INTO judgements (
                id, task_id, shot_id, version_id, attribute_id, verdict,
                expected, observed, reason, confidence, severity, issue_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                judgement_id, task_id, unit.shot_id, unit.version_id,
                unit.attribute_id, unit.verdict, unit.expected, unit.observed,
                unit.reason, unit.confidence, unit.severity, unit.issue_type, now,
            ),
        )

    for draft in result.issues:
        unit = draft.unit
        issue_id = f"ISS-{next_issue:03d}"
        next_issue += 1
        await conn.execute(
            """
            INSERT INTO issues (
                id, task_id, shot_id, judgement_id, attribute_id, attribute_name,
                type, expected, observed, evidence, confidence, severity,
                waiver_status, status, version_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'not_applicable', 'open', ?, ?)
            """,
            (
                issue_id, task_id, unit.shot_id,
                unit_ids[id(unit)], unit.attribute_id, draft.attribute_name,
                draft.type, unit.expected, unit.observed,
                unit.evidence or unit.reason or "画面观察证据",
                unit.confidence or "medium", unit.severity or "medium",
                unit.version_id, now,
            ),
        )

    for draft in result.unknown_items:
        unit = draft.unit
        unknown_id = f"UNK-{next_unknown:03d}"
        next_unknown += 1
        await conn.execute(
            """
            INSERT INTO unknown_items (
                id, task_id, shot_id, judgement_id, attribute_id,
                attribute_name, visibility, reason, version_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                unknown_id, task_id, unit.shot_id, unit_ids[id(unit)],
                unit.attribute_id, draft.attribute_name,
                unit.visibility or "not_visible", unit.reason or "无法判断",
                unit.version_id, now,
            ),
        )

    for draft in result.waivers:
        unit = draft.unit
        waiver_id = f"WVR-{next_waiver:03d}"
        next_waiver += 1
        await conn.execute(
            """
            INSERT INTO waivers (
                id, task_id, shot_id, judgement_id, attribute_id,
                attribute_name, scope_json, script_evidence, version_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                waiver_id, task_id, unit.shot_id, unit_ids[id(unit)],
                unit.attribute_id, draft.attribute_name,
                json.dumps(
                    {"shotCode": unit.shot_code, "attributeId": unit.attribute_id},
                    ensure_ascii=False,
                ),
                draft.script_evidence, unit.version_id, now,
            ),
        )

    for draft in result.suspected:
        unit = draft.unit
        suspected_id = f"SUS-{next_suspected:03d}"
        next_suspected += 1
        await conn.execute(
            """
            INSERT INTO suspected_issues (
                id, task_id, shot_id, judgement_id, attribute_id, attribute_name,
                expected, observed, evidence, confidence, reason, status,
                version_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (
                suspected_id, task_id, unit.shot_id, unit_ids[id(unit)],
                unit.attribute_id, draft.attribute_name, unit.expected,
                unit.observed, unit.evidence, unit.confidence, unit.reason,
                unit.version_id, now,
            ),
        )

    for shot_id, conclusion in result.shot_conclusions.items():
        await conn.execute(
            "UPDATE shots SET conclusion_status = ?, updated_at = ? WHERE id = ?",
            (conclusion, now, shot_id),
        )


async def list_units(db: Database, task_id: str) -> list[aiosqlite.Row]:
    """只返回当前版本判定；历史版本仅供追溯，不参与报告统计。"""
    return await db.fetchall(
        """
        SELECT j.* FROM judgements j
        JOIN shots s ON s.id = j.shot_id AND s.current_version_id = j.version_id
        WHERE j.task_id = ?
        """,
        (task_id,),
    )


async def list_issues(db: Database, task_id: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """
        SELECT i.* FROM issues i
        JOIN shots s ON s.id = i.shot_id AND s.current_version_id = i.version_id
        WHERE i.task_id = ? AND i.status = 'open'
        ORDER BY i.id
        """,
        (task_id,),
    )


async def list_unknowns(db: Database, task_id: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """
        SELECT u.* FROM unknown_items u
        JOIN shots s ON s.id = u.shot_id AND s.current_version_id = u.version_id
        WHERE u.task_id = ? ORDER BY u.id
        """,
        (task_id,),
    )


async def list_waivers(db: Database, task_id: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """
        SELECT w.* FROM waivers w
        JOIN shots s ON s.id = w.shot_id AND s.current_version_id = w.version_id
        WHERE w.task_id = ? ORDER BY w.id
        """,
        (task_id,),
    )


async def list_suspected(db: Database, task_id: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """
        SELECT p.* FROM suspected_issues p
        JOIN shots s ON s.id = p.shot_id AND s.current_version_id = p.version_id
        WHERE p.task_id = ? ORDER BY p.id
        """,
        (task_id,),
    )


async def counts_by_shot(db: Database, task_id: str) -> dict[str, dict[str, int]]:
    rows = await db.fetchall(
        """
        SELECT j.shot_id, j.verdict, COUNT(*) AS count
        FROM judgements j
        JOIN shots s ON s.id = j.shot_id AND s.current_version_id = j.version_id
        WHERE j.task_id = ? GROUP BY j.shot_id, j.verdict
        """,
        (task_id,),
    )
    result: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = result.setdefault(row["shot_id"], {})
        bucket[row["verdict"]] = int(row["count"])
    return result


async def verdicts_by_shot(db: Database, task_id: str) -> dict[tuple[str, str], str]:
    rows = await db.fetchall(
        """
        SELECT j.shot_id, j.attribute_id, j.verdict
        FROM judgements j
        JOIN shots s ON s.id = j.shot_id AND s.current_version_id = j.version_id
        WHERE j.task_id = ?
        """,
        (task_id,),
    )
    return {(row["shot_id"], row["attribute_id"]): row["verdict"] for row in rows}


async def issue_ids_by_judgement(db: Database, task_id: str) -> dict[str, str]:
    rows = await db.fetchall(
        "SELECT id, judgement_id FROM issues WHERE task_id = ?", (task_id,)
    )
    return {row["judgement_id"]: row["id"] for row in rows}


# ---- 单镜头复检增量写入 --------------------------------------
async def _next_number(
    conn: aiosqlite.Connection, table: str, prefix: str
) -> int:
    rows = await (
        await conn.execute(
            f"SELECT id FROM {table} WHERE id LIKE ?",
            (f"{prefix}-%",),
        )
    ).fetchall()
    numbers = []
    for row in rows:
        try:
            numbers.append(int(str(row["id"]).split("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return max(numbers, default=0) + 1


async def persist_shot_recheck(
    conn: aiosqlite.Connection,
    task_id: str,
    result: "JudgmentResult",
    shot_id: str,
) -> dict[str, Any]:
    """只替换目标镜头的当前判定，保留其他镜头与历史版本。

    采用候选后调用：新版本观察已写入 observations；本函数写入目标镜头的
    judgements/issues/unknown/waiver/suspected，并沿用原问题编号（同一要素）。
    目标镜头旧版本的行不删除，报告通过 current_version_id 过滤。
    """
    now = now_iso()
    shot_units = [unit for unit in result.units if unit.shot_id == shot_id]
    if not shot_units:
        return {"verdict": None, "issues": 0, "unknown": 0}

    # 旧问题用于复用编号；同一要素优先沿用最近的 ISS 编号。
    old_issue_rows = await (
        await conn.execute(
            "SELECT * FROM issues WHERE task_id = ? AND shot_id = ? ORDER BY rowid DESC",
            (task_id, shot_id),
        )
    ).fetchall()
    old_issue_by_attr: dict[str, str] = {}
    for row in old_issue_rows:
        old_issue_by_attr.setdefault(row["attribute_id"], row["id"])
    await conn.execute(
        "UPDATE issues SET status = 'closed', closed_at = ? "
        "WHERE task_id = ? AND shot_id = ? AND status = 'open'",
        (now, task_id, shot_id),
    )

    unit_ids: dict[int, str] = {}
    for unit in shot_units:
        judgement_id = new_id("jdg")
        unit_ids[id(unit)] = judgement_id
        await conn.execute(
            """
            INSERT INTO judgements (
                id, task_id, shot_id, version_id, attribute_id, verdict,
                expected, observed, reason, confidence, severity, issue_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                judgement_id, task_id, unit.shot_id, unit.version_id,
                unit.attribute_id, unit.verdict, unit.expected, unit.observed,
                unit.reason, unit.confidence, unit.severity, unit.issue_type, now,
            ),
        )

    issues = [draft for draft in result.issues if draft.unit.shot_id == shot_id]
    for draft in issues:
        unit = draft.unit
        issue_id = old_issue_by_attr.get(unit.attribute_id)
        if issue_id:
            await conn.execute(
                """
                UPDATE issues SET judgement_id = ?, attribute_name = ?, type = ?,
                    expected = ?, observed = ?, evidence = ?, confidence = ?,
                    severity = ?, waiver_status = 'not_applicable', status = 'open',
                    closed_at = NULL, version_id = ? WHERE id = ?
                """,
                (
                    unit_ids[id(unit)], draft.attribute_name, draft.type,
                    unit.expected, unit.observed,
                    unit.evidence or unit.reason or "画面观察证据",
                    unit.confidence or "medium", unit.severity or "medium",
                    unit.version_id, issue_id,
                ),
            )
        else:
            index = await _next_number(conn, "issues", "ISS")
            await conn.execute(
                """
                INSERT INTO issues (
                    id, task_id, shot_id, judgement_id, attribute_id, attribute_name,
                    type, expected, observed, evidence, confidence, severity,
                    waiver_status, status, version_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          'not_applicable', 'open', ?, ?)
                """,
                (
                    f"ISS-{index:03d}", task_id, unit.shot_id,
                    unit_ids[id(unit)], unit.attribute_id, draft.attribute_name,
                    draft.type, unit.expected, unit.observed,
                    unit.evidence or unit.reason or "画面观察证据",
                    unit.confidence or "medium", unit.severity or "medium",
                    unit.version_id, now,
                ),
            )

    unknowns = [draft for draft in result.unknown_items if draft.unit.shot_id == shot_id]
    for draft in unknowns:
        unit = draft.unit
        index = await _next_number(conn, "unknown_items", "UNK")
        await conn.execute(
            """
            INSERT INTO unknown_items (
                id, task_id, shot_id, judgement_id, attribute_id,
                attribute_name, visibility, reason, version_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"UNK-{index:03d}", task_id, unit.shot_id, unit_ids[id(unit)],
                unit.attribute_id, draft.attribute_name,
                unit.visibility or "not_visible", unit.reason or "无法判断",
                unit.version_id, now,
            ),
        )

    waivers = [draft for draft in result.waivers if draft.unit.shot_id == shot_id]
    for draft in waivers:
        unit = draft.unit
        index = await _next_number(conn, "waivers", "WVR")
        await conn.execute(
            """
            INSERT INTO waivers (
                id, task_id, shot_id, judgement_id, attribute_id,
                attribute_name, scope_json, script_evidence, version_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"WVR-{index:03d}", task_id, unit.shot_id, unit_ids[id(unit)],
                unit.attribute_id, draft.attribute_name,
                json.dumps(
                    {"shotCode": unit.shot_code, "attributeId": unit.attribute_id},
                    ensure_ascii=False,
                ),
                draft.script_evidence, unit.version_id, now,
            ),
        )

    suspected = [draft for draft in result.suspected if draft.unit.shot_id == shot_id]
    for draft in suspected:
        unit = draft.unit
        index = await _next_number(conn, "suspected_issues", "SUS")
        await conn.execute(
            """
            INSERT INTO suspected_issues (
                id, task_id, shot_id, judgement_id, attribute_id, attribute_name,
                expected, observed, evidence, confidence, reason, status,
                version_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (
                f"SUS-{index:03d}", task_id, unit.shot_id, unit_ids[id(unit)],
                unit.attribute_id, draft.attribute_name, unit.expected,
                unit.observed, unit.evidence, unit.confidence, unit.reason,
                unit.version_id, now,
            ),
        )

    # 本地旧建议引用的是旧问题/旧提示词，复检后清理；生成记录仍保留凭证。
    await conn.execute(
        "DELETE FROM suggestions WHERE task_id = ? AND shot_id = ?",
        (task_id, shot_id),
    )

    conclusion = result.shot_conclusions.get(shot_id)
    await conn.execute(
        "UPDATE shots SET conclusion_status = ?, updated_at = ? WHERE id = ?",
        (conclusion, now, shot_id),
    )
    return {
        "verdict": conclusion,
        "issues": len(issues),
        "unknown": len(unknowns),
        "waived": len(waivers),
        "suspected": len(suspected),
    }
