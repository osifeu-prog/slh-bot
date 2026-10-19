from io import BytesIO

import pytest
from PIL import Image

from core.social_asset_library import asset_ids, get_asset, list_assets, render_social_asset


def test_builtin_gallery_has_curated_share_safe_assets():
    ids = asset_ids()
    assert {"brand", "academy", "agents", "community", "ecosystem"} <= set(ids)
    for asset in list_assets("https://example.test"):
        assert asset["image_url"].startswith("https://example.test/api/v1/social/assets/")
        assert asset["content_type"] == "image/png"
        assert asset["width"] == 1200
        assert asset["height"] == 630
        assert "רווח מהיר" in asset["caption"] or "רווח" in asset["caption"] or asset["id"] in {"brand", "academy", "agents", "ecosystem"}


def test_generated_creative_is_valid_png_with_open_graph_dimensions():
    for asset_id in asset_ids():
        payload = render_social_asset(asset_id)
        image = Image.open(BytesIO(payload))
        assert image.format == "PNG"
        assert image.size == (1200, 630)
        assert len(payload) > 10_000


def test_asset_catalog_returns_copies_and_rejects_unknown_asset():
    first = get_asset("brand")
    first["title"] = "MUTATED"
    assert get_asset("brand")["title"] == "SLH SPARK"
    with pytest.raises(KeyError, match="SOCIAL_ASSET_NOT_FOUND"):
        get_asset("not-a-real-asset")


def test_render_cache_is_deterministic_and_read_only():
    first = render_social_asset("academy")
    second = render_social_asset("academy")
    assert first == second
