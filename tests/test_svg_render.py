import pytest

pytest.importorskip("playwright.sync_api")

from shared.svg_render import Renderer, l2_check  # noqa: E402

BASE = '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">{}</svg>'
CIRCLE = BASE.format('<circle cx="32" cy="32" r="20" fill="#f00" stroke="#000" stroke-width="2"/>')
TEXT = BASE.format('<text x="32" y="36" text-anchor="middle" font-family="Noto Sans CJK JP" font-size="8">図</text>')


@pytest.fixture(scope="module")
def renderer():
    try:
        r = Renderer()
    except Exception as exc:  # no browser in this environment
        pytest.skip(f"chromium unavailable: {exc}")
    yield r
    r.close()


def test_same_drawing_renders_to_same_pixels(renderer):
    report = l2_check(CIRCLE, renderer)
    assert report["ok"] and report["deterministic"]


def test_source_and_canonical_render_identically(renderer):
    messy = '<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">' \
            '<!-- x --><circle r="20.00" cy="32" cx="32" stroke-width="2" stroke="#000000" fill="#FF0000"/></svg>'
    report = l2_check(messy, renderer)
    assert report["source_matches_canonical"]


def test_different_drawings_give_different_pixels(renderer):
    a = l2_check(CIRCLE, renderer)["png_sha256"]
    b = l2_check(TEXT, renderer)["png_sha256"]
    assert a != b


def test_provenance_is_recorded(renderer):
    prov = l2_check(CIRCLE, renderer)["provenance"]
    assert prov["renderer"] == "chromium"
    assert prov["font_sha256"] and prov["font_package"]
