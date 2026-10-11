"""Invented controls for descriptive event accounting and scope boundaries."""
import unittest
from audit_visible_repeats import audit_records, _unique, _finite_float


def board(changed=False):
    x = [[0] * 10 for _ in range(10)]
    if changed: x[0][0] = 1
    return x


def initial(level=2):
    return {"type":"initial", "board":board(), "level":level}


def event(num, *, changed=False, level=2, action="UP", **kw):
    return {"type":"action", "board":board(changed), "level":level,
            "action_display":action, "action_num":num, **kw}


class AccountingControls(unittest.TestCase):
    def test_changed_after_unchanged_same_visible_key(self):
        c = audit_records([initial(), event(1), event(2, changed=True)])
        self.assertEqual(c["action_records"], 2)
        self.assertEqual(c["revisited_after_previous_unchanged"], 1)
        self.assertEqual(c["changed_after_previous_unchanged"], 1)
        self.assertEqual(c["level2plus_changed_after_unchanged"], 1)

    def test_crop4_is_only_hypothetical(self):
        c = audit_records([initial(), event(1, changed=True)])
        self.assertEqual(c["crop4_same_but_full_frame_changed"], 1)
        self.assertEqual(c["unchanged_final_visible_frame"], 0)

    def test_reset_breaks_key_history(self):
        c = audit_records([initial(), event(1), event(2, action="RESET"), event(3, changed=True)])
        self.assertEqual(c.get("changed_after_previous_unchanged", 0), 0)
        self.assertEqual(c["recovery_terminal_or_level_boundaries"], 1)

    def test_undo_breaks_key_history(self):
        c = audit_records([initial(), event(1), event(2, action="UNDO"), event(3, changed=True)])
        self.assertEqual(c.get("changed_after_previous_unchanged", 0), 0)

    def test_level_boundary_is_excluded(self):
        c = audit_records([initial(), event(1, level=3)])
        self.assertEqual(c.get("eligible_same_level_nonterminal_transitions", 0), 0)

    def test_terminal_boundary_is_excluded(self):
        for flag in ("done", "game_over", "run_complete", "level_completed"):
            c = audit_records([initial(), event(1, **{flag:True})])
            self.assertEqual(c.get("eligible_same_level_nonterminal_transitions", 0), 0)

    def test_analysis_never_counts_as_action(self):
        c = audit_records([initial(), {"type":"analysis", "board":board(True)}, event(1)])
        self.assertEqual(c["action_records"], 1)
        self.assertEqual(c["unchanged_final_visible_frame"], 1)

    def test_missing_predecessor_is_counted(self):
        c = audit_records([event(1)])
        self.assertEqual(c["actions_without_predecessor"], 1)

    def test_animation_summary_does_not_become_complete_chain(self):
        c = audit_records([initial(), event(1, animation={"frames":1,"unique_frames":1})])
        self.assertEqual(c["animation_summary_present"], 1)
        self.assertEqual(c["complete_animation_chains_available"], 0)

    def test_duplicate_or_reverse_action_number_rejected(self):
        for num in (1, 0, True):
            with self.assertRaises(ValueError): audit_records([initial(), event(1), event(num)])

    def test_flag_string_rejected(self):
        with self.assertRaises(ValueError): audit_records([initial(), event(1, done="false")])

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError): _unique([("level",2),("level",3)])

    def test_nonfinite_exponent_rejected(self):
        for v in ("1e999", "-1e999"):
            with self.assertRaises(ValueError): _finite_float(v)


if __name__ == "__main__":
    unittest.main()
