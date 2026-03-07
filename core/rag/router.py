from __future__ import annotations

import re
from dataclasses import dataclass

_SPACES_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-zA-Z\u0410-\u042f\u0430-\u044f\u0401\u04510-9\s:/_-]")
_RAG_FOCUS_PREFIX_RE = re.compile(r"^\s*\[FOCUS:(?P<name>[A-Z0-9_/-]+)\]\s*", re.IGNORECASE)

_FOCUS_ALIAS = {
    "default": "default",
    "game10": "game10",
    "gestalt": "gestalt",
    "event": "events",
    "events": "events",
    "course": "getcourse_programs",
    "courses": "getcourse_programs",
    "getcourse": "getcourse_programs",
    "getcourse_programs": "getcourse_programs",
    "menu": "menu_navigation",
    "menu_navigation": "menu_navigation",
    "payment": "payment_routes",
    "payments": "payment_routes",
    "payment_routes": "payment_routes",
}

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "game10": (
        "игра 10",
        "10:0",
        "10 0",
        "закрытый канал",
        "закрытый клуб",
        "game10",
    ),
    "getcourse_programs": (
        "авторский курс",
        "курс лекций",
        "лекции",
        "программа",
        "getcourse",
        "геткурс",
        "личный кабинет",
    ),
    "events": (
        "мероприят",
        "событи",
        "вебинар",
        "эфир",
        "ивент",
        "event",
    ),
    "gestalt": (
        "гештальт",
        "первая ступень",
        "1 ступень",
        "постоянн",
        "группа",
        "консультац",
        "терапи",
        "индивидуал",
        "записаться на консультацию",
    ),
    "menu_navigation": (
        "меню",
        "кнопк",
        "куда нажать",
        "как перейти",
        "куда перейти",
        "как открыть",
        "как вернуться",
        "где раздел",
        "где найти",
        "связаться с менеджером",
        "помощь",
        "assistant mode",
    ),
    "payment_routes": (
        "оплат",
        "как оплатить",
        "я оплатил",
        "доступ",
        "после оплаты",
        "что после оплаты",
        "обновить ссылку",
        "чек",
        "не получил доступ",
        "не пришел доступ",
        "не пришёл доступ",
        "payment",
    ),
}

_CONFLICT_GROUPS = (("events", "gestalt"), ("game10", "getcourse_programs"))
_PRIMARY_COLLECTIONS = {"game10", "getcourse_programs", "events", "gestalt"}


def _normalize(value: str) -> str:
    text = (value or "").lower().replace("ё", "е")
    text = _NON_ALNUM_RE.sub(" ", text)
    return _SPACES_RE.sub(" ", text).strip()


def _score_collection(normalized_query: str, collection: str) -> int:
    if not normalized_query:
        return 0
    score = 0
    for marker in _KEYWORDS.get(collection, ()):
        marker_norm = _normalize(marker)
        if not marker_norm:
            continue
        if marker_norm in normalized_query:
            score += 2
            if normalized_query.startswith(marker_norm):
                score += 1
    return score


@dataclass(slots=True)
class RagRouteResult:
    query: str
    requested_collection: str
    selected_collections: list[str]
    reason: str


class RagRouter:
    def parse_focus_prefix(self, query: str) -> tuple[str, str]:
        raw = (query or "").strip()
        match = _RAG_FOCUS_PREFIX_RE.match(raw)
        if not match:
            return raw, ""
        focus = (match.group("name") or "").strip().lower()
        mapped = _FOCUS_ALIAS.get(focus, focus)
        clean = raw[match.end() :].lstrip() or raw
        return clean, mapped

    def route(self, query: str, *, available_collections: set[str] | None = None, max_collections: int = 2) -> RagRouteResult:
        clean_query, focused_collection = self.parse_focus_prefix(query)
        normalized_query = _normalize(clean_query)
        available = {str(name).strip().lower() for name in (available_collections or set()) if str(name).strip()}
        if "default" not in available:
            available.add("default")

        if focused_collection and focused_collection in available:
            selected = [focused_collection]
            if focused_collection not in {"menu_navigation", "payment_routes"}:
                if _score_collection(normalized_query, "payment_routes") > 0 and "payment_routes" in available:
                    selected.append("payment_routes")
                elif _score_collection(normalized_query, "menu_navigation") > 0 and "menu_navigation" in available:
                    selected.append("menu_navigation")
            return RagRouteResult(
                query=clean_query,
                requested_collection=focused_collection,
                selected_collections=selected[: max(1, min(max_collections, 3))],
                reason="focus_prefix",
            )
        if focused_collection and focused_collection not in available:
            return RagRouteResult(
                query=clean_query,
                requested_collection=focused_collection,
                selected_collections=["default"],
                reason="focus_prefix_missing",
            )

        scored: list[tuple[int, str]] = []
        for collection in available:
            if collection == "default":
                continue
            score = _score_collection(normalized_query, collection)
            if score > 0:
                scored.append((score, collection))
        scored.sort(key=lambda item: (-item[0], item[1]))
        score_map = {collection: score for score, collection in scored}
        selected = [name for _, name in scored]

        for left, right in _CONFLICT_GROUPS:
            if left in selected and right in selected:
                left_score = score_map.get(left, 0)
                right_score = score_map.get(right, 0)
                if left_score >= right_score:
                    selected = [name for name in selected if name != right]
                else:
                    selected = [name for name in selected if name != left]

        if selected:
            primary = [name for name in selected if name in _PRIMARY_COLLECTIONS]
            if primary:
                primary.sort(key=lambda name: (-score_map.get(name, 0), name))
                secondary = [name for name in selected if name not in _PRIMARY_COLLECTIONS]
                selected = primary + secondary

        if not selected:
            selected = ["default"]
            reason = "default"
        else:
            reason = "keyword"
            if "payment_routes" in selected and "menu_navigation" not in selected and "menu_navigation" in available:
                if _score_collection(normalized_query, "menu_navigation") > 0:
                    selected.append("menu_navigation")
            if "menu_navigation" in selected and "payment_routes" not in selected and "payment_routes" in available:
                if _score_collection(normalized_query, "payment_routes") > 0:
                    selected.append("payment_routes")

        selected = [name for name in selected if name in available]
        if not selected:
            selected = ["default"]
            reason = "default"
        requested = selected[0]
        selected = selected[: max(1, min(max_collections, 3))]
        return RagRouteResult(
            query=clean_query,
            requested_collection=requested,
            selected_collections=selected,
            reason=reason,
        )
