from pathlib import Path

from heizung.lib.state import StateStore
from heizung.lib.tor import TorRuntime, entscheide_tor_command


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


def _runtime(path: Path) -> TorRuntime:
    return TorRuntime(StateStore(path), fahrzeit_s=30, initial_position="geschlossen", halb_aktiv=False)


def test_virtual_gate_starts_closed_and_blocks_duplicate_pulses(tmp_path):
    runtime = _runtime(tmp_path / "tor.json")

    assert runtime.snapshot(100)["status"] == "Tor Geschlossen"
    first = runtime.entscheide("oeffnen_ganz", 100)
    duplicate = runtime.entscheide("oeffnen_ganz", 110)

    assert first.ausfuehren is True
    assert first.ausgang == "tor_ganz"
    assert runtime.snapshot(110)["status"] == "Tor Oeffnet"
    assert duplicate.ausfuehren is False
    assert duplicate.grund == "tor_faehrt_bereits"


def test_virtual_gate_requires_camera_confirmation_after_travel(tmp_path):
    runtime = _runtime(tmp_path / "tor.json")
    runtime.entscheide("oeffnen_ganz", 100)

    assert runtime.bestaetige_position("offen", 129) is False
    assert runtime.snapshot(130)["status"] == "Kamerapruefung ausstehend"
    assert runtime.entscheide("schliessen", 130).grund == "kamerapruefung_ausstehend"
    assert runtime.bestaetige_position("offen", 130) is True
    assert runtime.snapshot(130)["status"] == "Tor Offen"
    assert runtime.entscheide("oeffnen_ganz", 131).grund == "tor_bereits_offen"


def test_virtual_gate_can_close_after_verified_open_position(tmp_path):
    runtime = _runtime(tmp_path / "tor.json")
    runtime.entscheide("oeffnen_ganz", 100)
    runtime.bestaetige_position("offen", 130)

    decision = runtime.entscheide("schliessen", 131)

    assert decision.ausfuehren is True
    assert decision.ausgang == "tor_ganz"
    assert runtime.snapshot(140)["status"] == "Tor Schliesst"
    assert runtime.bestaetige_position("geschlossen", 161) is True
    assert runtime.snapshot(161)["status"] == "Tor Geschlossen"


def test_virtual_gate_rejects_half_gate_and_persists_state(tmp_path):
    path = tmp_path / "tor.json"
    runtime = _runtime(path)

    assert runtime.entscheide("oeffnen_halb", 100).grund == "tor_halb_nicht_angeschlossen"
    runtime.entscheide("oeffnen_ganz", 100)
    reloaded = _runtime(path)

    assert reloaded.snapshot(110)["status"] == "Tor Oeffnet"
    assert reloaded.entscheide("schliessen", 110).grund == "tor_faehrt_bereits"
