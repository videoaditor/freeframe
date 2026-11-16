"""The embed preview of a module request shows its separate parts: each carries its role and place (2026-11-16)."""
from apps.api.routers.share import part_roles

MANIFEST = {"slots": [
    {"id": "h1", "role": "hook"}, {"id": "h2", "role": "hook"}, {"id": "h3", "role": "hook"},
    {"id": "b1", "role": "body"}, {"id": "c1", "role": "cta"},
]}
STATE = {"slots": {k: {"asset_id": f"asset-{k}"} for k in ("h1", "h2", "h3", "b1", "c1")}}


def test_each_part_gets_role_and_order_within_its_role():
    assert part_roles(MANIFEST, STATE) == {
        "asset-h1": ("hook", 0), "asset-h2": ("hook", 1), "asset-h3": ("hook", 2),
        "asset-b1": ("body", 0), "asset-c1": ("cta", 0)}


def test_a_slot_without_an_upload_yet_is_skipped_but_still_counts_for_order():
    state = {"slots": {"h2": {"asset_id": "asset-h2"}}}
    assert part_roles(MANIFEST, state) == {"asset-h2": ("hook", 1)}


def test_no_module_data_means_no_roles():
    assert part_roles(None, None) == {}
    assert part_roles({"slots": []}, {}) == {}
    assert part_roles({"slots": [{"id": "x"}]}, {"slots": {"x": {"asset_id": "a"}}}) == {}
