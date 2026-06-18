from heizung.lib.tor import entscheide_tor_command


def test_close_is_blocked_when_both_wings_are_closed():
    decision = entscheide_tor_command("schliessen", links_zu=True, rechts_zu=True)

    assert decision.ausfuehren is False
    assert decision.ausgang is None


def test_close_right_wing_uses_half_button_when_only_right_is_open():
    decision = entscheide_tor_command("schliessen", links_zu=True, rechts_zu=False)

    assert decision.ausfuehren is True
    assert decision.ausgang == "tor_halb"


def test_close_both_wings_uses_full_button_when_left_is_open():
    decision = entscheide_tor_command("schliessen", links_zu=False, rechts_zu=False)

    assert decision.ausfuehren is True
    assert decision.ausgang == "tor_ganz"


def test_half_open_is_blocked_when_right_wing_is_not_closed():
    decision = entscheide_tor_command("oeffnen_halb", links_zu=True, rechts_zu=False)

    assert decision.ausfuehren is False
    assert decision.ausgang is None


def test_half_open_uses_half_button_when_right_wing_is_closed():
    decision = entscheide_tor_command("oeffnen_halb", links_zu=True, rechts_zu=True)

    assert decision.ausfuehren is True
    assert decision.ausgang == "tor_halb"


def test_full_open_is_blocked_when_both_wings_are_not_closed():
    decision = entscheide_tor_command("oeffnen_ganz", links_zu=False, rechts_zu=False)

    assert decision.ausfuehren is False
    assert decision.ausgang is None


def test_full_open_uses_full_button_when_at_least_one_wing_is_closed():
    decision = entscheide_tor_command("oeffnen_ganz", links_zu=True, rechts_zu=False)

    assert decision.ausfuehren is True
    assert decision.ausgang == "tor_ganz"
