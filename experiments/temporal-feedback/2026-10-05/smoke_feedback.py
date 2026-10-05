"""Source-free synthetic CPU demonstration; no engine/model/score evidence.

Run with Python 3.10+ and the adjacent feedback_watermark.py. The larger
source-aware contracts additionally require the exact source pair they attest.
"""
from feedback_watermark import ActionEvent, FeedbackWatermark


def main():
    ledger = FeedbackWatermark()
    summary = {"start_action_num": 1, "end_action_num": 1, "executed_count": 1,
               "level": 2, "run_complete": False, "level_transition": True,
               "game_over": False}
    prompt = ("The code executed 1 action in the previous sequence.\n"
              "You have progressed to a new level!\n"
              "Current state: step 2, level 2.\nPreserved knowledge.")
    history = [ActionEvent(1, "UP", 2, level_completed=True)]
    print("Synthetic CPU demonstration; no engine/model/score evidence.")
    for expected in ("newly observed", "historical, already shown"):
        output = ledger.render(prompt, scope=("demo-session", "pass-0"),
            history=history, frame_step=1, frame_level=2, summary=summary)
        assert output.summary_status == expected
        assert output.prompt.endswith("Preserved knowledge.")
        print(output.prompt)
    failed = {**summary, "level": 1, "level_transition": False, "game_over": True}
    failed_prompt = ("The code executed 1 action in the previous sequence.\n"
                     "You are still on the same level.\nThe game is over.\n"
                     "Current state: step 3, level 1.")
    reset_history = [ActionEvent(1, "UP", 1, game_over=True), ActionEvent(2, "RESET", 1)]
    output = ledger.render(failed_prompt, scope=("demo-session", "pass-1"),
        history=reset_history, frame_step=2, frame_level=1, summary=failed)
    assert output.current_phase == "nonterminal"
    assert "nonterminal RESET" in output.prompt
    assert "The game is over." not in output.prompt
    print(output.prompt)


if __name__ == "__main__":
    main()
