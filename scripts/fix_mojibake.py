import argparse
import asyncio
import re
from typing import Iterable

from sqlalchemy import select

import core.db.database as db
from core.events.models import Event
from telegram_bot.text_utils import looks_like_mojibake, repair_mojibake


FIELDS = ("title", "description", "location")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def iter_repairs(event: Event) -> Iterable[tuple[str, str, str]]:
    for field in FIELDS:
        original = getattr(event, field)
        if not isinstance(original, str) or not original:
            continue
        if not looks_like_mojibake(original):
            continue
        fixed = repair_mojibake(original)
        if not fixed or fixed == original:
            continue
        if not CYRILLIC_RE.search(fixed):
            continue
        if looks_like_mojibake(fixed):
            continue
        yield field, original, fixed


async def run(apply: bool, limit: int | None) -> None:
    db.init_db()
    assert db.async_session is not None

    changed_rows = 0
    changed_fields = 0
    checked_rows = 0

    async with db.async_session() as session:
        query = select(Event).order_by(Event.id.asc())
        if limit:
            query = query.limit(limit)
        rows = await session.execute(query)
        events = rows.scalars().all()

        for event in events:
            checked_rows += 1
            field_repairs = list(iter_repairs(event))
            if not field_repairs:
                continue

            changed_rows += 1
            print(f"[event:{event.id}]")
            for field, original, fixed in field_repairs:
                changed_fields += 1
                print(f"  {field}: {original!r} -> {fixed!r}")
                if apply:
                    setattr(event, field, fixed)

        if apply and changed_fields:
            await session.commit()
            print(f"Applied {changed_fields} field updates in {changed_rows} events.")
        else:
            print(f"Dry-run: {changed_fields} field updates detected in {changed_rows} events.")
        print(f"Checked events: {checked_rows}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix mojibake in events.title/description/location safely."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to DB. Default is dry-run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of checked events (for diagnostics).",
    )
    args = parser.parse_args()

    asyncio.run(run(apply=args.apply, limit=args.limit))


if __name__ == "__main__":
    main()
