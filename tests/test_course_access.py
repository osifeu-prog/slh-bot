import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def test_free_and_paid_course_flags():
    c = json.loads((ROOT / "courses.json").read_text(encoding="utf-8"))
    assert c["bitcoin_mastery"]["access"] == "free"
    assert c["ai_tokens"]["access"] == "free"
    items = json.loads((ROOT / "store" / "items.json").read_text(encoding="utf-8"))
    for cid in ("ethereum", "slh_vs_eth_sol"):
        assert c[cid]["access"] == "paid"
        item = items[c[cid]["store_item"]]
        assert item["grant"] == {"course": cid} and item["stars_only"] is True
    assert "course_bitcoin_101" not in items and "ai_tokens_course" not in items


def test_stars_only_item_cannot_be_bought_with_credits():
    from store import purchase_service
    items = {"course_ethereum": {"name": "x", "price": 0, "stars_only": True, "type": "course", "grant": {"course": "ethereum"}}}
    with patch.object(purchase_service, "load_items", return_value=items):
        ok, err = purchase_service.purchase("100", "course_ethereum", request_id="t1")
    assert ok is False and err == "STARS_ONLY"


def test_paid_course_locked_until_enrolled():
    from handlers import academy_handler as ah
    with patch("core.authority.is_owner", return_value=False), \
         patch.object(ah.academy_manager, "get_course", return_value=None):
        assert "buystars course_ethereum" in ah._paid_course_lock("100", "ethereum")
        assert ah._paid_course_lock("100", "bitcoin_mastery") is None
    with patch("core.authority.is_owner", return_value=False), \
         patch.object(ah.academy_manager, "get_course", return_value={"stage": 1}):
        assert ah._paid_course_lock("100", "ethereum") is None


def test_active_vip_unlocks_paid_course():
    import time
    from handlers import academy_handler as ah
    with patch("core.authority.is_owner", return_value=False), \
         patch.object(ah.academy_manager, "get_course", return_value=None), \
         patch("core.profile_manager.get_user", return_value={"vip_access_until": int(time.time()) + 3600}):
        assert ah._paid_course_lock("100", "ethereum") is None
    with patch("core.authority.is_owner", return_value=False), \
         patch.object(ah.academy_manager, "get_course", return_value=None), \
         patch("core.profile_manager.get_user", return_value={"vip_access_until": int(time.time()) - 10}):
        assert ah._paid_course_lock("100", "ethereum") is not None
