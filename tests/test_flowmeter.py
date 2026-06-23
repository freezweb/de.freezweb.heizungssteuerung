import pytest

from heizung.lib.flowmeter import FlowmeterModbusConfig


def test_flowmeter_modbus_config_defaults_to_disabled():
    config = FlowmeterModbusConfig.from_settings({})

    assert config.enabled is False
    assert config.host == "wasserverbrauch-pumpe.local"
    assert config.function == 4
    assert config.scale == 100.0


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
