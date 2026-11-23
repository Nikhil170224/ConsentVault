from app.services.dsr_service import ALLOWED_TRANSITIONS, can_transition


def test_happy_path_transitions():
    assert can_transition("RECEIVED", "VERIFYING")
    assert can_transition("VERIFYING", "IN_PROGRESS")
    assert can_transition("IN_PROGRESS", "COMPLETED")


def test_reject_from_any_active_state():
    for state in ("RECEIVED", "VERIFYING", "IN_PROGRESS"):
        assert can_transition(state, "REJECTED")


def test_illegal_transitions():
    assert not can_transition("RECEIVED", "COMPLETED")
    assert not can_transition("RECEIVED", "IN_PROGRESS")
    assert not can_transition("COMPLETED", "VERIFYING")
    assert not can_transition("REJECTED", "RECEIVED")
    assert not can_transition("COMPLETED", "REJECTED")


def test_terminal_states_have_no_exits():
    assert ALLOWED_TRANSITIONS["COMPLETED"] == set()
    assert ALLOWED_TRANSITIONS["REJECTED"] == set()
