import pytest

from heizung.lib.oelverbrauch import (
    OelverbrauchConfig,
    OelverbrauchTracker,
    parse_clever_tanken_dieselpreis,
)
from heizung.lib.state import StateStore


def test_oelverbrauch_counts_only_when_burner_running(tmp_path):
    tracker = OelverbrauchTracker(
        OelverbrauchConfig(brenner_kw=25.0, kwh_per_liter=10.0, max_update_interval_s=7200.0),
        StateStore(tmp_path / "oel.json"),
    )

    first = tracker.update(1000.0, True)
    stopped = tracker.update(2800.0, False)
    running = tracker.update(4600.0, True)

    assert first.total_liter == 0.0
    assert first.current_liter_per_hour == pytest.approx(2.5)
    assert first.current_kw == pytest.approx(25.0)
    assert stopped.total_liter == 0.0
    assert stopped.current_liter_per_hour == 0.0
    assert stopped.current_kw == 0.0
    assert running.total_liter == pytest.approx(1.25)
    assert running.total_kwh == pytest.approx(12.5)
    assert running.runtime_h == pytest.approx(0.5)
    assert running.current_cost_eur_per_hour == pytest.approx(2.5 * 2.079)


def test_oelverbrauch_limits_large_elapsed_time_after_pause(tmp_path):
    tracker = OelverbrauchTracker(
        OelverbrauchConfig(brenner_kw=25.0, kwh_per_liter=10.0, max_update_interval_s=300.0),
        StateStore(tmp_path / "oel.json"),
    )

    tracker.update(1000.0, True)
    snapshot = tracker.update(4600.0, True)

    assert snapshot.total_liter == pytest.approx(2.5 * 300.0 / 3600.0)


def test_oelverbrauch_persists_totals_and_price(tmp_path):
    state = StateStore(tmp_path / "oel.json")
    tracker = OelverbrauchTracker(OelverbrauchConfig(max_update_interval_s=7200.0), state)
    tracker.update(1000.0, True)
    tracker.update(1360.0, True)
    tracker.update_dieselpreis(
        parse_clever_tanken_dieselpreis(_CLEVER_TANKEN_HTML, "https://example.test/tankstelle"),
        1400.0,
    )

    loaded = OelverbrauchTracker(OelverbrauchConfig(), state).snapshot(False)

    assert loaded.total_liter == pytest.approx(0.25)
    assert loaded.dieselpreis_eur_l == pytest.approx(2.079)
    assert loaded.dieselpreis_remote_updated == "12.07.2026 13:30"


def test_parse_clever_tanken_dieselpreis():
    snapshot = parse_clever_tanken_dieselpreis(_CLEVER_TANKEN_HTML, "https://example.test/tankstelle")

    assert snapshot.price_eur_l == pytest.approx(2.079)
    assert snapshot.remote_updated == "12.07.2026 13:30"


_CLEVER_TANKEN_HTML = """
<div class="price-row row d-flex align-items-center">
  <div class="price-type col-6 d-flex flex-column justify-content-start headline">
    <div class="price-type-name">Diesel</div>
    <div class="price-type-mtsk"> MTS-K Preis</div>
  </div>
  <div class="price-box col-6">
    <div class="price-field">
      <span id="current-price-1">2.07</span>
      <sup id="suffix-price-1">9</sup>
    </div>
  </div>
</div>
<span>Letzte MTS-K Preisänderung: 12.07.2026 13:30</span>
"""
