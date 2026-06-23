import sys

from heizung.lib.config import ChannelConfig, IoMap
from heizung.lib.iohw import RevPiIO, SimulatedIO, _raw_ai_value, _raw_ao_output_value, create_io_backend


async def test_simulated_io_writes_outputs():
    io_map = IoMap(
        revpi={},
        do={"DO01": ChannelConfig("DO01", "do", "O_01", "brenner")},
        di={},
        ai={},
        ao={"AO01": ChannelConfig("AO01", "ao", "AO_01", "wp1_vl_soll", bereich=(20.0, 55.0))},
    )
    io = SimulatedIO(io_map)

    await io.write_do(io_map.do["DO01"], True)
    await io.write_ao(io_map.ao["AO01"], 0.0)
    snapshot = await io.read_all()

    assert snapshot.ao["AO01"] == 0.0

    await io.write_ao(io_map.ao["AO01"], 80.0)
    snapshot = await io.read_all()

    assert snapshot.do["DO01"] is True
    assert snapshot.ao["AO01"] == 55.0


async def test_revpi_ao_writes_integer_values():
    class FakeOutput:
        def __init__(self):
            self.written = None

        @property
        def value(self):
            return self.written

        @value.setter
        def value(self, new_value):
            if not isinstance(new_value, int):
                raise TypeError("RevPi AO expects int")
            self.written = new_value

    fake_output = FakeOutput()
    io = object.__new__(RevPiIO)
    io.io_map = IoMap(revpi={}, do={}, di={}, ai={}, ao={})
    io._revpi = type("FakeRevPi", (), {"io": {"AO": fake_output}, "writeprocimg": lambda self: True})()
    io._missing_ios = set()

    channel = ChannelConfig("AO01", "ao", "AO", "wp1_vl_soll", bereich=(20.0, 55.0))

    await io.write_ao(channel, 35.4)

    assert fake_output.written == 35


async def test_revpi_writes_process_image_after_do_write():
    class FakeOutput:
        value = False

    class FakeRevPi:
        io = {"O_1": FakeOutput()}

        def __init__(self):
            self.write_calls = 0

        def writeprocimg(self):
            self.write_calls += 1
            return True

    fake_revpi = FakeRevPi()
    io = object.__new__(RevPiIO)
    io.io_map = IoMap(revpi={}, do={}, di={}, ai={}, ao={})
    io._revpi = fake_revpi
    io._missing_ios = set()

    channel = ChannelConfig("DO01", "do", "O_1", "brenner")

    await io.write_do(channel, True)

    assert fake_revpi.io["O_1"].value is True
    assert fake_revpi.write_calls == 1


def test_revpi_aio_percent_output_is_scaled_to_millivolt():
    channel = ChannelConfig(
        "K-AO01",
        "ao",
        "OutputValue_465_1",
        "brunnen_fu_soll",
        bereich=(0.0, 100.0),
        einheit="%",
        signal="0-10V",
    )

    assert _raw_ao_output_value(channel, 0.0) == 0.0
    assert _raw_ao_output_value(channel, 50.0) == 5000.0
    assert _raw_ao_output_value(channel, 100.0) == 10000.0


def test_revpi_aio_temperature_output_is_scaled_over_configured_range():
    channel = ChannelConfig(
        "AO01",
        "ao",
        "OutputValue_1",
        "wp1_vl_soll",
        bereich=(20.0, 55.0),
        einheit="C",
        signal="0-10V",
    )

    assert round(_raw_ao_output_value(channel, 37.5)) == 5000


def test_revpi_aio_current_output_uses_microampere():
    channel = ChannelConfig(
        "K-AO01",
        "ao",
        "OutputValue_465_1",
        "brunnen_fu_soll",
        bereich=(0.0, 100.0),
        einheit="%",
        signal="4-20mA",
    )

    assert _raw_ao_output_value(channel, 0.0) == 4000.0
    assert _raw_ao_output_value(channel, 50.0) == 12000.0
    assert _raw_ao_output_value(channel, 100.0) == 20000.0


async def test_revpi_writes_grouped_dio_bits_without_overwriting_word():
    class FakeOutput:
        value = 0b0010

    class FakeRevPi:
        io = {"Output_0": FakeOutput()}

        def __init__(self):
            self.write_calls = 0

        def writeprocimg(self):
            self.write_calls += 1
            return True

    fake_revpi = FakeRevPi()
    io = object.__new__(RevPiIO)
    io.io_map = IoMap(revpi={}, do={}, di={}, ai={}, ao={})
    io._revpi = fake_revpi
    io._missing_ios = set()

    await io.write_do(ChannelConfig("K-DO01", "do", "Output_0", "pumpe", channel="O_1"), True)
    await io.write_do(ChannelConfig("K-DO02", "do", "Output_0", "pumpe2", channel="O_2"), False)
    await io.write_do(ChannelConfig("K-DO04", "do", "Output_0", "freigabe", channel="O_4"), True)

    assert fake_revpi.io["Output_0"].value == 0b1001
    assert fake_revpi.write_calls == 3


async def test_revpi_sets_cpu_leds_with_color_values():
    class FakeCore:
        def __init__(self):
            self.values = {}

        def __setattr__(self, key, value):
            if key == "values":
                object.__setattr__(self, key, value)
            else:
                self.values[key] = value

    class FakeRevPi:
        def __init__(self):
            self.core = FakeCore()
            self.write_calls = 0

        def writeprocimg(self):
            self.write_calls += 1
            return True

    fake_revpi = FakeRevPi()
    io = object.__new__(RevPiIO)
    io.io_map = IoMap(revpi={}, do={}, di={}, ai={}, ao={})
    io._revpi = fake_revpi
    io._missing_ios = set()

    await io.set_cpu_leds({"A1": "blue", "A2": "gelb", "A3": "rot"})

    assert fake_revpi.core.values == {"A1": 4, "A2": 3, "A3": 2}
    assert fake_revpi.write_calls == 1


async def test_simulated_io_stores_cpu_leds():
    io = SimulatedIO(IoMap(revpi={}, do={}, di={}, ai={}, ao={}))

    await io.set_cpu_leds({"a1": "gruen", "A2": "unknown"})

    assert io.cpu_leds == {"A1": "green", "A2": "off"}


def test_revpi_missing_io_attribute_error_is_ignored():
    class MissingIo:
        def __getitem__(self, key):
            raise AttributeError(f"can not find io {key}")

    io = object.__new__(RevPiIO)
    io._revpi = type("FakeRevPi", (), {"io": MissingIo()})()
    io._missing_ios = set()

    channel = ChannelConfig("DI01", "di", "DIO_I_1", "reserve")

    assert io._try_get_io(channel) is None
    assert io._missing_ios == {"DI01->DIO_I_1"}


def test_ai_pressure_channel_converts_microampere_to_milliampere():
    channel = ChannelConfig("AI01", "ai", "AI", "brunnen_druck", einheit="bar", sensor="4-20mA Drucksensor")

    assert _raw_ai_value(4000, channel) == 4.0
    assert _raw_ai_value(12000, channel) == 12.0
    assert _raw_ai_value(20000, channel) == 20.0


def test_ai_pressure_channel_can_convert_shunt_millivolt_to_milliampere():
    channel = ChannelConfig(
        "AI01",
        "ai",
        "AI",
        "brunnen_druck",
        einheit="bar",
        sensor="4-20mA Drucksensor",
        signal="shunt-mv",
    )

    assert _raw_ai_value(1000, channel) == 4.0
    assert _raw_ai_value(3000, channel) == 12.0
    assert _raw_ai_value(5000, channel) == 20.0


def test_auto_backend_falls_back_when_revpi_init_fails(monkeypatch):
    class BrokenRevPiModIO:
        def __init__(self, *args, **kwargs):
            raise AttributeError("attribute Output_ already exists")

    class BrokenRevPiModule:
        RevPiModIO = BrokenRevPiModIO

    monkeypatch.setitem(sys.modules, "revpimodio2", BrokenRevPiModule)
    io_map = IoMap(revpi={}, do={}, di={}, ai={}, ao={})

    io = create_io_backend(io_map, "auto")

    assert isinstance(io, SimulatedIO)
