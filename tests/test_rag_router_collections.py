from __future__ import annotations

from core.rag import RagRouter


def test_router_routes_game10_keywords_to_game10():
    router = RagRouter()
    result = router.route("что такое игра 10:0", available_collections={"default", "game10", "events"})
    assert result.selected_collections == ["game10"]
    assert result.reason == "keyword"


def test_router_routes_getcourse_keywords_to_getcourse_programs():
    router = RagRouter()
    result = router.route(
        "расскажи про авторский курс лекций",
        available_collections={"default", "getcourse_programs", "game10"},
    )
    assert result.selected_collections == ["getcourse_programs"]


def test_router_does_not_mix_events_and_gestalt_when_gestalt_is_clear():
    router = RagRouter()
    result = router.route(
        "что относится к гештальту и постоянным направлениям",
        available_collections={"default", "events", "gestalt"},
    )
    assert "gestalt" in result.selected_collections
    assert "events" not in result.selected_collections


def test_router_can_add_payment_and_menu_collections_for_cross_queries():
    router = RagRouter()
    result = router.route(
        "как оплатить и где в меню найти курс",
        available_collections={"default", "payment_routes", "menu_navigation"},
    )
    assert "payment_routes" in result.selected_collections
    assert "menu_navigation" in result.selected_collections


def test_router_keeps_primary_product_collection_before_payment_support():
    router = RagRouter()
    result = router.route(
        "как оплатить игру 10:0",
        available_collections={"default", "game10", "payment_routes"},
    )
    assert result.selected_collections[0] == "game10"
    assert "payment_routes" in result.selected_collections


def test_router_routes_qr_and_yookassa_query_to_payment_routes():
    router = RagRouter()
    result = router.route(
        "где qr и ссылка на оплату yookassa",
        available_collections={"default", "payment_routes", "game10"},
    )
    assert result.selected_collections[0] == "payment_routes"


def test_router_routes_consultation_query_to_gestalt():
    router = RagRouter()
    result = router.route(
        "как записаться на консультацию",
        available_collections={"default", "events", "gestalt"},
    )
    assert result.selected_collections[0] == "gestalt"
    assert "events" not in result.selected_collections


def test_router_routes_open_getcourse_query_to_getcourse_and_menu():
    router = RagRouter()
    result = router.route(
        "как открыть getcourse",
        available_collections={"default", "getcourse_programs", "menu_navigation", "payment_routes"},
    )
    assert "getcourse_programs" in result.selected_collections
    assert "menu_navigation" in result.selected_collections
    assert len(result.selected_collections) <= 2
