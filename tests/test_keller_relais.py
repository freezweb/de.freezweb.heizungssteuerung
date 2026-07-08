from __future__ import annotations

from pathlib import Path

import pytest

from heizung.lib.config import AppConfig, ChannelConfig, IoMap
from heizung.lib.keller_relais import KellerRelayClient, KellerRelayConfig, _modbus_crc
from heizung.lib.state import StateStore


def _app_config() -> AppConfig:
    io_map = IoMap(
        revpi={},
        di={},
        ai={},
        rtd={},
        do={
            "K-DO01": ChannelConfig("K-DO01", "do", "R1", "pumpe_fbh_eg"),
            "K-DO02": ChannelConfig("K-DO02", "do", "R7", "pumpe_klima_og"),
            "K-DO03": ChannelConfig("K-DO03", "do", "R4", "pumpe_hk_backup"),
        },
        ao={},
    )
    return AppConfig(
        root_dir=Path("."),
        config_dir=Path("config"),
        io_map=io_map,
        settings={},
        mqtt={},
        modbus_map={},
    )


def test_modbus_crc_write_single_coil_on() -> None:
    frame_without_crc = bytes.fromhex("01 06 00 01 01 00")
    assert _modbus_crc(frame_without_crc).hex(" ") == "d9 9a"


def test_modbus_crc_write_channel_one_close() -> None:
    frame_without_crc = bytes.fromhex("01 06 00 01 02 00")
    assert _modbus_crc(frame_without_crc).hex(" ") == "d9 6a"


def test_config_defaults_match_r421b16_relay_plan() -> None:
    config = KellerRelayConfig.from_settings({"keller_relais": {"enabled": True}})
    assert config.enabled is True
    assert config.test_mode_enabled is False
    assert config.host == "10.1.100.169"
    assert config.port == 26
    assert config.protocol == "modbus_tcp"
    assert config.groups["fbh_eg"].pump_relay == 1
    assert config.groups["fbh_eg"].enable_relay == 2
    assert config.groups["fbh_eg"].direction_relay == 3
    assert config.groups["fbh_eg"].target_channel_id == "K-AO02"
    assert config.groups["fbh_eg"].vl_component == "fbh_eg_vl"
    assert config.groups["hk_backup"].pump_relay == 4
    assert config.groups["hk_backup"].vl_component == "hk_backup_vl"
    assert config.groups["klima_og"].pump_relay == 7
    assert config.groups["klima_og"].vl_component == "klima_og_vl"


@pytest.mark.asyncio
async def test_test_mode_forces_all_groups_active(tmp_path: Path) -> None:
    config = KellerRelayConfig.from_settings(
        {"keller_relais": {"enabled": True, "test_mode": {"enabled": True, "target_pct": 100}}}
    )
    client = KellerRelayClient(config, StateStore(tmp_path / "state.json"))
    writes: list[tuple[int, bool]] = []

    async def fake_write(relay: int, on: bool) -> None:
        writes.append((relay, on))

    client._write_single_relay = fake_write  # type: ignore[method-assign]

    await client.write_outputs(_app_config(), {}, {})

    assert (1, True) in writes
    assert (2, True) in writes
    assert (3, True) in writes
    assert (4, True) in writes
    assert (5, True) in writes
    assert (6, True) in writes
    assert (7, True) in writes
    assert (8, True) in writes
    assert (9, True) in writes


@pytest.mark.asyncio
async def test_write_outputs_maps_pump_enable_and_direction(tmp_path: Path) -> None:
    config = KellerRelayConfig.from_settings(
        {
            "keller_relais": {
                "enabled": True,
                "runtime_s": 120,
                "groups": {"fbh_eg": {"tolerance_pct": 0.5}},
            }
        }
    )
    client = KellerRelayClient(config, StateStore(tmp_path / "state.json"))
    client.positions["fbh_eg"] = 20.0
    writes: list[tuple[int, bool]] = []

    async def fake_write(relay: int, on: bool) -> None:
        writes.append((relay, on))

    client._write_single_relay = fake_write  # type: ignore[method-assign]

    await client.write_outputs(
        _app_config(),
        {"K-DO01": True, "K-DO02": False, "K-DO03": False},
        {"K-AO02": 50.0, "K-AO03": 0.0, "K-AO04": 0.0},
    )

    assert (1, True) in writes
    assert (2, True) in writes
    assert (3, True) in writes
    assert (4, False) in writes
    assert (5, False) in writes
    assert (7, False) in writes
    assert (8, False) in writes


@pytest.mark.asyncio
async def test_write_outputs_closes_when_target_is_below_position(tmp_path: Path) -> None:
    config = KellerRelayConfig.from_settings({"keller_relais": {"enabled": True}})
    client = KellerRelayClient(config, StateStore(tmp_path / "state.json"))
    client.positions["hk_backup"] = 80.0
    writes: list[tuple[int, bool]] = []

    async def fake_write(relay: int, on: bool) -> None:
        writes.append((relay, on))

    client._write_single_relay = fake_write  # type: ignore[method-assign]

    await client.write_outputs(
        _app_config(),
        {"K-DO01": False, "K-DO02": False, "K-DO03": True},
        {"K-AO02": 0.0, "K-AO03": 0.0, "K-AO04": 20.0},
    )

    assert (4, True) in writes
    assert (5, True) in writes
    assert (6, False) in writes


@pytest.mark.asyncio
async def test_failed_write_does_not_advance_virtual_position(tmp_path: Path) -> None:
    config = KellerRelayConfig.from_settings(
        {"keller_relais": {"enabled": True, "test_mode": {"enabled": True, "target_pct": 100}}}
    )
    client = KellerRelayClient(config, StateStore(tmp_path / "state.json"))
    client.positions["fbh_eg"] = 0.0

    async def broken_write(relay: int, on: bool) -> None:
        raise TimeoutError

    client._write_single_relay = broken_write  # type: ignore[method-assign]

    with pytest.raises(TimeoutError):
        await client.write_outputs(_app_config(), {}, {})

    assert client.positions["fbh_eg"] == 0.0
