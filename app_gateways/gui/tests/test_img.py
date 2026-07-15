import numpy as np

from app_gateways.gui.img import Img


def _solid(color: tuple[int, int, int, int], size: int = 4) -> Img:
    img = Img()
    img.img = np.zeros((size, size, 4), dtype=np.uint8)
    img.img[:, :] = color
    return img


class TestDrawOnAlpha:
    def test_opaque_sprite_makes_destination_opaque(self):
        canvas = _solid((0, 0, 0, 0))  # fully transparent, as a fresh frame starts
        sprite = _solid((10, 20, 30, 255))
        sprite.draw_on(canvas, 0, 0)
        assert canvas.img[0, 0, 3] == 255
        assert tuple(canvas.img[0, 0, :3]) == (10, 20, 30)

    def test_transparent_sprite_leaves_destination_unchanged(self):
        canvas = _solid((5, 6, 7, 255))
        sprite = _solid((10, 20, 30, 0))
        sprite.draw_on(canvas, 0, 0)
        assert canvas.img[0, 0, 3] == 255
        assert tuple(canvas.img[0, 0, :3]) == (5, 6, 7)

    def test_partial_alpha_blends_and_accumulates_alpha(self):
        canvas = _solid((0, 0, 0, 0))
        sprite = _solid((100, 100, 100, 128))
        sprite.draw_on(canvas, 0, 0)
        # alpha should move from 0 toward ~128, not stay at 0
        assert canvas.img[0, 0, 3] > 0
