"""Invented controls; these are not ARC scores or native game experiments."""
import unittest
from repeat_adviser import RepeatAdviser, visible_digest, grid_from_ascii


def grid():
    return [[0] * 8 for _ in range(8)]


def observe(g, before=None, after=None, action="UP", level=2, chain=True, **kw):
    b = before if before is not None else grid()
    a = after if after is not None else grid()
    return g.observe(level_before=level, before=b, action=action,
                     level_after=level, after=a,
                     animation_frames=[a] if chain is True else chain, **kw)


class Controls(unittest.TestCase):
    def advice(self, g, b=None, action="UP", level=2):
        return g.advise(level=level, board=grid() if b is None else b, action=action)

    def test_two_observations_then_single_advisory(self):
        g = RepeatAdviser(); observe(g)
        self.assertFalse(self.advice(g).warn)
        observe(g)
        x = self.advice(g)
        self.assertTrue(x.warn); self.assertTrue(x.permits_execution)
        self.assertIn("hidden", x.message)
        self.assertFalse(self.advice(g).warn)

    def test_missing_capture_never_qualifies(self):
        g = RepeatAdviser()
        for _ in range(8): observe(g, chain=None)
        self.assertFalse(self.advice(g).warn)

    def test_transient_bounce_is_not_unchanged(self):
        g = RepeatAdviser(); b = grid(); t = grid(); t[3][3] = 1
        for _ in range(3): observe(g, chain=[t, b])
        self.assertFalse(self.advice(g).warn)

    def test_border_changes_invalidate_full_frame_key(self):
        g = RepeatAdviser(); observe(g); observe(g)
        b = grid(); b[0][0] = 1
        self.assertNotEqual(visible_digest(grid()), visible_digest(b))
        self.assertFalse(self.advice(g, b).warn)

    def test_delayed_visible_effect_is_always_executable(self):
        g = RepeatAdviser(); b = grid(); changed = grid(); changed[3][3] = 1
        # An invented cooldown: the third execution is the useful one.
        executed = 0
        for i in range(3):
            x = self.advice(g)
            self.assertTrue(x.permits_execution)
            executed += 1
            observe(g, after=changed if i == 2 else b)
        self.assertEqual(executed, 3)
        self.assertFalse(self.advice(g).warn)

    def test_contradiction_retires_even_after_more_unchanged(self):
        g = RepeatAdviser(); observe(g); observe(g)
        a = grid(); a[2][2] = 1; observe(g, after=a)
        for _ in range(5): observe(g)
        self.assertEqual(self.advice(g).reason, "contradictory_visible_outcome")

    def test_same_level_reset_clears_attempt(self):
        g = RepeatAdviser(); observe(g); observe(g); observe(g, action="RESET")
        self.assertFalse(self.advice(g).warn)

    def test_undo_clears_evidence(self):
        g = RepeatAdviser(); observe(g); observe(g); observe(g, action="UNDO")
        self.assertFalse(self.advice(g).warn)

    def test_level_change_clears_evidence(self):
        g = RepeatAdviser(); observe(g); observe(g)
        self.assertFalse(self.advice(g, level=3).warn)

    def test_terminal_clears_evidence(self):
        g = RepeatAdviser(); observe(g); observe(g); observe(g, terminal=True)
        self.assertFalse(self.advice(g).warn)

    def test_mouse_coordinates_have_distinct_keys(self):
        g = RepeatAdviser(); observe(g, action="MOUSE(2,3)"); observe(g, action="MOUSE(2,3)")
        self.assertFalse(self.advice(g, action="MOUSE(3,2)").warn)
        self.assertTrue(self.advice(g, action=" MOUSE(02,03) ").warn)

    def test_labelled_mouse_display_is_same_action(self):
        g = RepeatAdviser(); observe(g, action="MOUSE(row=2, col=3)"); observe(g, action="MOUSE(2,3)")
        self.assertTrue(self.advice(g, action="MOUSE(row=02, col=03)").warn)

    def test_expiration_and_unknown_does_not_refresh(self):
        g = RepeatAdviser(ttl_actions=1); observe(g); observe(g)
        observe(g, action="DOWN", chain=None); observe(g, action="DOWN", chain=None)
        self.assertEqual(self.advice(g).reason, "expired_evidence")

    def test_expired_count_starts_again(self):
        g = RepeatAdviser(ttl_actions=1); observe(g); observe(g)
        for _ in range(2): observe(g, action="DOWN", chain=None)
        observe(g); self.assertFalse(self.advice(g).warn)
        observe(g); self.assertTrue(self.advice(g).warn)

    def test_entry_count_bound(self):
        g = RepeatAdviser(max_entries=1)
        observe(g); observe(g); observe(g, action="DOWN")
        self.assertFalse(self.advice(g).warn)
        self.assertLessEqual(len(g._entries), 1)

    def test_invalid_config(self):
        for args in ({"observations_required":1},{"observations_required":True},{"ttl_actions":0},{"max_entries":4097}):
            with self.assertRaises(ValueError): RepeatAdviser(**args)

    def test_bad_grid_does_not_mutate(self):
        g = RepeatAdviser(); observe(g); observe(g)
        for b in ([[True]], [[16]], [[]], [[0], [0, 1]], [[0]*65]):
            with self.assertRaises(ValueError): self.advice(g, b)
        self.assertTrue(self.advice(g).warn)

    def test_endpoint_mismatch(self):
        g = RepeatAdviser(); t = grid(); t[1][1] = 1
        with self.assertRaises(ValueError): observe(g, chain=[t])
        self.assertEqual(g._step, 0)

    def test_animation_frame_bound(self):
        with self.assertRaises(ValueError): observe(RepeatAdviser(), chain=[grid()]*129)

    def test_invalid_action(self):
        for act in ("ACTION1", "MOUSE(64,0)", "MOUSE(-1,0)", "UP;secret", None):
            with self.assertRaises(ValueError): self.advice(RepeatAdviser(), action=act)

    def test_inspection_does_not_age_evidence(self):
        g = RepeatAdviser(ttl_actions=1); observe(g); observe(g)
        for _ in range(100): self.assertTrue(self.advice(g).permits_execution)
        self.assertEqual(g._step, 2)

    def test_ascii_only_adapter(self):
        self.assertEqual(grid_from_ascii("WW\nWb\n"), [[0, 0], [0, 9]])
        self.assertEqual(len(set(grid_from_ascii("WwgGcBMPRbSYOrNp")[0])), 16)

    def test_bad_ascii_view(self):
        for text in ("", "W?", "WW\nW", " " * 5000, None):
            with self.assertRaises(ValueError): grid_from_ascii(text)


if __name__ == "__main__":
    unittest.main()
