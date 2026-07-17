from app_gateways.gui.gui_runner import letterbox_transform, window_to_native

_NATIVE_W, _NATIVE_H = 1140, 928


def _assert_roundtrip(window_w: int, window_h: int, native_x: int, native_y: int) -> None:
    scale, offset_x, offset_y = letterbox_transform(_NATIVE_W, _NATIVE_H, window_w, window_h)

    window_x = int(native_x * scale) + offset_x
    window_y = int(native_y * scale) + offset_y

    back_x, back_y = window_to_native(
        window_x, window_y, scale, offset_x, offset_y, _NATIVE_W, _NATIVE_H
    )

    assert back_x is not None and back_y is not None
    assert abs(back_x - native_x) <= 2
    assert abs(back_y - native_y) <= 2


class TestLetterboxRoundTrip:
    def test_same_aspect_ratio(self):
        _assert_roundtrip(_NATIVE_W * 2, _NATIVE_H * 2, 500, 400)

    def test_wider_window_letterboxes_sides(self):
        _assert_roundtrip(2000, 928, 500, 400)

    def test_narrower_window_letterboxes_top_bottom(self):
        _assert_roundtrip(1140, 2000, 500, 400)

    def test_smaller_than_native(self):
        _assert_roundtrip(600, 500, 100, 100)

    def test_corner_points(self):
        _assert_roundtrip(1500, 1200, 0, 0)
        _assert_roundtrip(1500, 1200, _NATIVE_W - 1, _NATIVE_H - 1)


class TestLetterboxBars:
    def test_click_in_letterbox_bar_is_rejected(self):
        scale, offset_x, offset_y = letterbox_transform(_NATIVE_W, _NATIVE_H, 2000, 928)
        assert offset_x > 0

        cx, cy = window_to_native(0, 0, scale, offset_x, offset_y, _NATIVE_W, _NATIVE_H)

        assert cx is None
        assert cy is None
