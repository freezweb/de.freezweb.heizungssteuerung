import pytest

from heizung.lib.flowmeter import FlowmeterModbusConfig, WatermeterHttpConfig, parse_watermeter_http_payload


def test_flowmeter_modbus_config_defaults_to_disabled():
    config = FlowmeterModbusConfig.from_settings({})

    assert config.enabled is False
    assert config.host == "wasserverbrauch-pumpe.local"
    assert config.function == 4
    assert config.scale == 100.0
    assert config.total_register == 1
    assert config.total_scale == 1000.0


def test_flowmeter_modbus_config_accepts_holding_registers():
    config = FlowmeterModbusConfig.from_settings(
        {
            "brunnen": {
                "flow_modbus": {
                    "enabled": True,
                    "host": "10.1.25.50",
                    "register_type": "holding",
                    "register": 7,
                    "scale": 10,
                }
            }
        }
    )

    assert config.enabled is True
    assert config.host == "10.1.25.50"
    assert config.function == 3
    assert config.register == 7
    assert config.scale == 10.0


@pytest.mark.asyncio
async def test_flowmeter_modbus_config_rejects_invalid_function_in_client():
    config = FlowmeterModbusConfig(enabled=True, function=6)

    from heizung.lib.flowmeter import FlowmeterModbusClient

    with pytest.raises(ValueError):
        await FlowmeterModbusClient(config)._read_register(6, 0)


def test_watermeter_http_config_defaults_to_disabled():
    config = WatermeterHttpConfig.from_settings({})

    assert config.enabled is False
    assert config.url == "http://10.1.20.191/value?all=true&type=value"
    assert config.number_name == "zaehlerstand"
    assert config.total_scale_l_per_unit == 1000.0
    assert config.mqtt_mirror_enabled is True
    assert config.mqtt_topic_base == "watermeter/zaehlerstand"


def test_watermeter_http_config_reads_settings():
    config = WatermeterHttpConfig.from_settings(
        {
            "brunnen": {
                "watermeter_http": {
                    "enabled": True,
                    "url": "http://water/value",
                    "number_name": "main",
                    "total_scale_l_per_unit": 1,
                    "timeout_s": 5,
                    "poll_interval_s": 30,
                    "mqtt_mirror_enabled": False,
                    "mqtt_topic_base": "/custom/base/",
                }
            }
        }
    )

    assert config.enabled is True
    assert config.url == "http://water/value"
    assert config.number_name == "main"
    assert config.total_scale_l_per_unit == 1.0
    assert config.timeout_s == 5.0
    assert config.poll_interval_s == 30.0
    assert config.mqtt_mirror_enabled is False
    assert config.mqtt_topic_base == "custom/base"


def test_parse_watermeter_http_payload_converts_m3_to_liters():
    snapshot = parse_watermeter_http_payload("zaehlerstand\t58.5766\n", "zaehlerstand", 1000)

    assert snapshot.value == 58.5766
    assert snapshot.raw == "58.5766"
    assert snapshot.total_l == pytest.approx(58576.6)
