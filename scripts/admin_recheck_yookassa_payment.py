from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

from fastapi import HTTPException

import core.db.database as db
from core.api.payments import _recheck_yookassa_payment_internal


logger = logging.getLogger(__name__)


def _safe_output(payload: dict[str, Any], *, payment_id: str) -> dict[str, Any]:
    value_tg_id = payload.get("tg_id")
    tg_id: int | None = None
    try:
        tg_id = int(value_tg_id) if value_tg_id is not None else None
    except Exception:
        tg_id = None

    return {
        "payment_id": str(payload.get("payment_id") or payment_id),
        "tg_id": tg_id,
        "status": str(payload.get("status") or "unknown"),
        "outcome": str(payload.get("result") or ""),
        "error_type": (str(payload.get("error_type") or "") or None),
    }


async def _run(payment_id: str) -> dict[str, Any]:
    db.init_db()
    if db.async_session is None:
        raise RuntimeError("DB session factory is not initialized")
    async with db.async_session() as session:
        result = await _recheck_yookassa_payment_internal(
            db=session,
            payment_id=payment_id,
            tg_id=None,
        )
        await session.commit()
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Admin recheck for YooKassa payment by payment_id.")
    parser.add_argument("payment_id", help="YooKassa payment id")
    args = parser.parse_args(argv)

    payment_id = str(args.payment_id or "").strip()
    if not payment_id:
        print(json.dumps({"payment_id": "", "error": "invalid_payment_id"}, ensure_ascii=False))
        return 2

    try:
        result = asyncio.run(_run(payment_id))
        print(json.dumps(_safe_output(result, payment_id=payment_id), ensure_ascii=False))
        return 0
    except HTTPException as exc:
        print(
            json.dumps(
                {"payment_id": payment_id, "error": f"http_{int(exc.status_code)}"},
                ensure_ascii=False,
            )
        )
        return 1
    except Exception as exc:
        logger.warning("Admin recheck failed: %s", exc.__class__.__name__)
        print(
            json.dumps(
                {"payment_id": payment_id, "error": exc.__class__.__name__},
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
