import pathlib

from app_gateways.gui.animation.anim_state import AnimState
from app_gateways.gui.animation.piece_animator import PieceAnimator

_PW_DIR = pathlib.Path(__file__).parents[1] / "assets" / "pieces_mine" / "PW"


class TestPieceAnimator:
    def _animator(self) -> PieceAnimator:
        return PieceAnimator(_PW_DIR, cell_size=16)

    def test_starts_idle(self):
        anim = self._animator()
        assert anim.current_state == AnimState.IDLE

    def test_transition_to_resets_frame(self):
        anim = self._animator()
        anim.update(2000)  # advance idle frames first
        anim.transition_to(AnimState.MOVE)
        assert anim.current_state == AnimState.MOVE
        assert anim.get_frame() is not None

    def test_transition_to_same_state_is_a_no_op(self):
        anim = self._animator()
        anim.transition_to(AnimState.MOVE)
        anim.update(100)
        frame_before = anim.get_frame()
        anim.transition_to(AnimState.MOVE)
        assert anim.get_frame() is frame_before

    def test_non_loop_state_transitions_to_next_state_when_finished(self):
        anim = self._animator()
        anim.transition_to(AnimState.LONG_REST)
        # long_rest: 5 frames @ 2fps => 2000ms to fully finish
        anim.update(2500)
        assert anim.current_state == AnimState.IDLE

    def test_loop_state_wraps_instead_of_transitioning(self):
        anim = self._animator()
        assert anim.current_state == AnimState.IDLE
        # idle is a loop state; running it well past its total duration
        # should never leave IDLE
        anim.update(10_000)
        assert anim.current_state == AnimState.IDLE
