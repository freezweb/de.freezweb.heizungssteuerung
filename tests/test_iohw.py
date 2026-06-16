import sys

from heizung.lib.config import ChannelConfig, IoMap
from heizung.lib.iohw import RevPiIO, SimulatedIO, create_io_backend


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
    await io.write_ao(io_map.ao["AO01"], 80.0)
    snapshot = await io.read_all()

    assert snapshot.do["DO01"] is True
    assert snapshot.ao["AO01"] == 55.0


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
