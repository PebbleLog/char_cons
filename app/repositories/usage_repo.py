"""AI 调用用量登记（NFR-08 / 技术方案 6.3.16）。"""

from __future__ import annotations

from ..core.timeutil import now_iso
from .database import Database


async def record_usage(
    db: Database,
    *,
    task_id: str | None,
    kind: str,
    provider: str | None,
    model: str | None,
    request_id: str | None,
    input_images: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    image_count: int = 0,
    estimated_cost: float | None = None,
) -> None:
    await db.execute(
        """
        INSERT INTO usage_records (
            task_id, kind, provider, model, request_id, input_images,
            input_tokens, output_tokens, image_count, estimated_cost,
            currency, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CNY', ?)
        """,
        (
            task_id,
            kind,
            provider,
            model,
            request_id,
            input_images,
            input_tokens,
            output_tokens,
            image_count,
            estimated_cost,
            now_iso(),
        ),
    )


async def summary_for_task(db: Database, task_id: str) -> dict:
    rows = await db.fetchall(
        """
        SELECT kind, COUNT(*) AS calls,
               COALESCE(SUM(input_tokens), 0) AS input_tokens,
               COALESCE(SUM(output_tokens), 0) AS output_tokens,
               COALESCE(SUM(image_count), 0) AS images,
               COALESCE(SUM(estimated_cost), 0) AS cost
        FROM usage_records WHERE task_id = ? GROUP BY kind
        """,
        (task_id,),
    )
    return {row["kind"]: dict(row) for row in rows}
