"""Konfiguration aus den YAML-Dateien laden und typisiert zugreifbar machen."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Fehler in fehlender oder ungueltiger Konfiguration."""


def load_yaml(path: Path) -> dict[str, Any]:
    """Laedt eine YAML-Datei als Mapping."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - wird auf dem RevPi durch Dependency abgedeckt
        raise ConfigError("PyYAML ist nicht installiert. Bitte `pip install -e .` ausfuehren.") from exc

    if not path.exists():
        raise ConfigError(f"Konfigurationsdatei fehlt: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"Konfigurationsdatei muss ein YAML-Mapping enthalten: {path}")
    return data


def resolve_config_file(config_dir: Path, name: str) -> Path:
    """Nimmt Live-Config, faellt fuer Entwicklung auf .example zurueck."""
    live = config_dir / name
    if live.exists():
        return live
    example = config_dir / f"{name}.example"
    if example.exists():
        return example
    raise ConfigError(f"Weder {live} noch {example} gefunden")


@dataclass(frozen=True)
class ChannelConfig:
    id: str
    kind: str
    pictory_name: str
    komponente: str
    module: str | None = None
    channel: str | None = None
    beschreibung: str = ""
    phase: str = "-"
    hand_timeout_min: int | None = None
    impuls_ms: int | None = None
    einheit: str | None = None
    sensor: str | None = None
    signal: str | None = None
    polaritaet: str | None = None
    bereich: tuple[float, float] | None = None

    @classmethod
    def from_mapping(cls, channel_id: str, kind: str, raw: dict[str, Any]) -> "ChannelConfig":
        bereich = raw.get("bereich")
        parsed_range = None
        if isinstance(bereich, (list, tuple)) and len(bereich) == 2:
            parsed_range = (float(bereich[0]), float(bereich[1]))

        return cls(
            id=channel_id,
            kind=kind,
            pictory_name=str(raw["pictory_name"]),
            komponente=str(raw["komponente"]),
            module=raw.get("module"),
            channel=raw.get("channel"),
            beschreibung=str(raw.get("beschreibung", "")),
            phase=str(raw.get("phase", "-")),
            hand_timeout_min=raw.get("hand_timeout_min"),
            impuls_ms=raw.get("impuls_ms"),
            einheit=raw.get("einheit"),
            sensor=raw.get("sensor"),
            signal=raw.get("signal") or raw.get("ausgangssignal"),
            polaritaet=raw.get("polaritaet"),
            bereich=parsed_range,
        )


@dataclass(frozen=True)
class IoMap:
    revpi: dict[str, Any]
    do: dict[str, ChannelConfig]
    di: dict[str, ChannelConfig]
    ai: dict[str, ChannelConfig]
    ao: dict[str, ChannelConfig]
    rtd: dict[str, ChannelConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "IoMap":
        return cls(
            revpi=dict(raw.get("revpi", {})),
            do=_parse_channels(raw, "do"),
            di=_parse_channels(raw, "di"),
            ai=_parse_channels(raw, "ai"),
            ao=_parse_channels(raw, "ao"),
            rtd=_parse_channels(raw, "rtd"),
        )

    @property
    def output_channels(self) -> dict[str, ChannelConfig]:
        return {**self.do, **self.ao}

    @property
    def input_channels(self) -> dict[str, ChannelConfig]:
        return {**self.di, **self.ai, **self.rtd}

    def by_component(self, component: str) -> ChannelConfig | None:
        for channel in [
            *self.do.values(),
            *self.ao.values(),
            *self.di.values(),
            *self.ai.values(),
            *self.rtd.values(),
        ]:
            if channel.komponente == component:
                return channel
        return None


def _parse_channels(raw: dict[str, Any], kind: str) -> dict[str, ChannelConfig]:
    section = raw.get(kind, {})
    if not isinstance(section, dict):
        raise ConfigError(f"io_map.yaml: Abschnitt {kind!r} muss ein Mapping sein")
    return {
        channel_id: ChannelConfig.from_mapping(channel_id, kind, channel_raw)
        for channel_id, channel_raw in section.items()
    }


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path
    config_dir: Path
    io_map: IoMap
    settings: dict[str, Any]
    mqtt: dict[str, Any]
    modbus_map: dict[str, Any]

    @classmethod
    def load(cls, root_dir: Path | None = None) -> "AppConfig":
        root = (root_dir or Path.cwd()).resolve()
        config_dir = root / "config"
        io_map = IoMap.from_dict(load_yaml(resolve_config_file(config_dir, "io_map.yaml")))
        settings = load_yaml(resolve_config_file(config_dir, "settings.yaml"))
        mqtt = load_yaml(resolve_config_file(config_dir, "mqtt.yaml"))
        modbus_map = load_yaml(resolve_config_file(config_dir, "modbus_map.yaml"))
        return cls(root, config_dir, io_map, settings, mqtt, modbus_map)

    def setting(self, path: str, default: Any = None) -> Any:
        node: Any = self.settings
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def state_path(self, configured_path: str) -> Path:
        path = Path(configured_path)
        if path.is_absolute():
            return path
        return self.root_dir / path
