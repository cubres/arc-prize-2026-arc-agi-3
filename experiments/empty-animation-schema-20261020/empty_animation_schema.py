"""Prospective pure response adapter; not installed in any campaign notebook.

Idea credit: Heliosli V5/native359864604 (Apache-2.0), on the credited
Daniel Franzen/Tufa Labs baseline. This independent helper changes only the
exact legacy empty-animation result. It executes no action or fallback.
"""

EMPTY_ANIMATION_ERROR = (
    "No animation is available: the last executed action returned a single frame."
)


def complete_empty_animation_view(
    view: dict[str, object], record: dict[str, object] | None,
) -> dict[str, object]:
    """Complete the legacy empty view; preserve every other result by identity.

    ``frames=0`` means no animation timeline is reported. It says nothing
    about engine observation count or the cost of the preceding game action.
    Pass the same record used by the existing renderer. An absent record has
    unknown action provenance; never manufacture an action label for it.
    """
    if type(view) is not dict:
        raise TypeError("Animation view must be a built-in dictionary")
    if len(view) != 1 or view.get("error") != EMPTY_ANIMATION_ERROR:
        return view
    if record is not None and type(record) is not dict:
        raise TypeError("Animation record must be a built-in dictionary or None")
    return {
        "action": record.get("action_display") if record else None,
        "frames": 0,
        "steps": [],
        "error": EMPTY_ANIMATION_ERROR,
    }
