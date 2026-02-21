from __future__ import annotations

import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.ai.ai_service import AIService


async def main() -> int:
    service = AIService()
    ok, reply = await service.ping()
    if not ok:
        print(f"FAIL {reply}")
        return 1
    print(f"OK {len(reply)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))