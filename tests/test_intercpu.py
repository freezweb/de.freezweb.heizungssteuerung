from heizung.lib.config import ChannelConfig, IoMap
from heizung.lib.intercpu import (
    HR_AO_BASE,
    HR_DO_MASK,
    IR_AI_BASE,
    IR_AO_BASE,
    IR_DO_FEEDBACK,
    IR_RTD_BASE,
    decode_output_registers,
    encode_input_registers,
)
from heizung.lib.iohw import HardwareSnapshot


def _io_map():
    return IoMap(
        revpi={},
        do={
            "K-DO01": ChannelConfig("K-DO01", "do", "O_1", "pumpe_fbh_eg"),
            "K-DO02": ChannelConfig("K-DO02", "do", "O_2", "pumpe_klima_og"),
        },
        di={},
        ai={"K-AI01": ChannelConfig("K-AI01", "ai", "InputValue_1", "brunnen_druck")},
        ao={
            "K-AO01": ChannelConfig("K-AO01", "ao", "OutputValue_1", "brunnen_fu_soll"),
            "K-AO02": ChannelConfig("K-AO02", "ao", "OutputValue_2", "mischer_fbh_eg_pct"),
        },
        rtd={"K-RTD01": ChannelConfig("K-RTD01", "rtd", "RTDValue_1", "fbh_eg_vl")},
    )


def test_decode_output_registers_uses_keller_channel_order():
    registers = [0] * 160
    registers[0] = 17
    registers[1] = 1
    registers[HR_DO_MASK] = 0b01
    registers[HR_AO_BASE] = 455
    registers[HR_AO_BASE + 1] = 1000

    command_counter, enabled, do, ao = decode_output_registers(_io_map(), registers)

    assert command_counter == 17
    assert enabled is True
    assert do == {"K-DO01": True, "K-DO02": False}
    assert ao == {"K-AO01": 45.5, "K-AO02": 100.0}


def test_encode_input_registers_reports_feedback_and_sensors():
    values = encode_input_registers(
        _io_map(),
        HardwareSnapshot(ai={"K-AI01": 3.25}, rtd={"K-RTD01": 28.4}),
        {"K-DO01": False, "K-DO02": True},
        {"K-AO01": 12.3, "K-AO02": 99.9},
        status=7,
        command_counter=18,
    )

    assert values[0] == 7
    assert values[1] == 18
    assert values[IR_DO_FEEDBACK] == 0b10
    assert values[IR_AO_BASE] == 123
    assert values[IR_AO_BASE + 1] == 999
    assert values[IR_AI_BASE] == 325
    assert values[IR_RTD_BASE] == 284
