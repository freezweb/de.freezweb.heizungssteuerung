from pathlib import Path

from heizung.__main__ import _apply_pump_group_vl_controls
from heizung.lib.config import AppConfig, ChannelConfig, IoMap
from heizung.lib.iohw import HardwareSnapshot
from heizung.lib.mqtt_bridge import Demand, MqttBridge
from heizung.lib.pumpengruppe import PumpGroupConfig, PumpGroupSnapshot, pump_group_configs_from_settings


def test_pump_group_config_ignores_disabled_groups():
    configs = pump_group_configs_from_settings(
        {
            "pumpengruppen": {
                "nebengeb": {
                    "enabled": False,
                    "host": "10.1.20.189",
                }
            }
        }
    )

    assert configs == {}


def test_pump_group_config_maps_nebengebaeude_components():
    configs = pump_group_configs_from_settings(
        {
            "pumpengruppen": {
                "nebengeb": {
                    "enabled": True,
                    "host": "10.1.20.189",
                    "unit_id": 30,
                    "pump_component": "pumpe_nebengeb",
                    "mixer_component": "sv_nebengeb_pct",
                    "vl_component": "vl_nebengeb",
                    "rl_component": "rl_nebengeb",
                }
            }
        }
    )

    assert configs["nebengeb"] == PumpGroupConfig(
        name="nebengeb",
        enabled=True,
        host="10.1.20.189",
        unit_id=30,
        pump_component="pumpe_nebengeb",
        mixer_component="sv_nebengeb_pct",
        vl_component="vl_nebengeb",
        rl_component="rl_nebengeb",
    )


def test_pump_group_snapshot_decodes_status_bits():
    snapshot = PumpGroupSnapshot(online=True, status=(1 << 2) | (1 << 3))

    assert snapshot.moving is True
    assert snapshot.pump_on is True


def test_nebengebaeude_mixer_closes_when_flow_is_too_hot():
    app_config = _pump_group_app_config()
    mqtt = _mqtt_with_nebengeb_demand(31.0)
    auto_ao = {"AO04": 100.0}

    _apply_pump_group_vl_controls(
        app_config,
        mqtt,
        HardwareSnapshot(rtd={"RTD13": 33.0}),
        {"DO18": True},
        auto_ao,
        applied_ao={},
        pump_group_snapshots={"nebengeb": PumpGroupSnapshot(online=True, position_pct=100.0)},
    )

    assert auto_ao["AO04"] == 84.0


def test_nebengebaeude_mixer_opens_when_flow_is_too_cold():
    app_config = _pump_group_app_config()
    mqtt = _mqtt_with_nebengeb_demand(35.0)
    auto_ao = {"AO04": 40.0}

    _apply_pump_group_vl_controls(
        app_config,
        mqtt,
        HardwareSnapshot(rtd={"RTD13": 33.0}),
        {"DO18": True},
        auto_ao,
        applied_ao={},
        pump_group_snapshots={"nebengeb": PumpGroupSnapshot(online=True, position_pct=40.0)},
    )

    assert auto_ao["AO04"] == 56.0


def test_nebengebaeude_mixer_holds_inside_hysteresis():
    app_config = _pump_group_app_config()
    mqtt = _mqtt_with_nebengeb_demand(31.0)
    auto_ao = {"AO04": 75.0}

    _apply_pump_group_vl_controls(
        app_config,
        mqtt,
        HardwareSnapshot(rtd={"RTD13": 31.2}),
        {"DO18": True},
        auto_ao,
        applied_ao={},
        pump_group_snapshots={"nebengeb": PumpGroupSnapshot(online=True, position_pct=75.0)},
    )

    assert auto_ao["AO04"] == 75.0


def test_nebengebaeude_mixer_does_not_open_when_pump_route_is_inactive():
    app_config = _pump_group_app_config()
    mqtt = _mqtt_with_nebengeb_demand(35.0)
    auto_ao = {"AO04": 0.0}

    _apply_pump_group_vl_controls(
        app_config,
        mqtt,
        HardwareSnapshot(rtd={"RTD13": 30.0}),
        {"DO18": False},
        auto_ao,
        applied_ao={},
        pump_group_snapshots={"nebengeb": PumpGroupSnapshot(online=True, position_pct=0.0)},
    )

    assert auto_ao["AO04"] == 0.0


def _pump_group_app_config() -> AppConfig:
    return AppConfig(
        root_dir=Path("."),
        config_dir=Path("config"),
        io_map=IoMap(
            revpi={},
            do={
                "DO18": ChannelConfig(
                    "DO18",
                    "do",
                    "O_4_i17",
                    "pumpe_nebengeb",
                )
            },
            di={},
            ai={},
            ao={
                "AO04": ChannelConfig(
                    "AO04",
                    "ao",
                    "OutputValue_2_i13",
                    "sv_nebengeb_pct",
                )
            },
            rtd={
                "RTD13": ChannelConfig(
                    "RTD13",
                    "rtd",
                    "RTDValue_1_i09",
                    "vl_nebengeb",
                )
            },
        ),
        settings={
            "pumpengruppen": {
                "nebengeb": {
                    "enabled": True,
                    "host": "10.1.20.189",
                    "pump_component": "pumpe_nebengeb",
                    "mixer_component": "sv_nebengeb_pct",
                    "vl_component": "vl_nebengeb",
                    "rl_component": "rl_nebengeb",
                }
            },
            "mischer": {
                "nebengeb": {
                    "hysterese_k": 0.3,
                    "kp_pct_pro_k": 8.0,
                    "max_step_pct": 20.0,
                }
            },
        },
        mqtt={},
        modbus_map={},
    )


def _mqtt_with_nebengeb_demand(vl_soll: float) -> MqttBridge:
    mqtt = MqttBridge({})
    mqtt.demands["nebengeb"] = Demand(aktiv=True, vl_soll=vl_soll)
    return mqtt
