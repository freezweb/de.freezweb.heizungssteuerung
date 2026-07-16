"""Lokale, fehlersichere Hoftor-Endlagenerkennung fuer Home Assistant."""

from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path
from statistics import fmean

import voluptuous as vol
from PIL import Image, ImageChops, ImageFilter, ImageOps

from homeassistant.components.camera import async_get_image
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
import homeassistant.helpers.config_validation as cv

DOMAIN = "hoftor_vision"
SERVICE_CLASSIFY = "classify"
SERVICE_CAPTURE = "capture_reference"
CONF_POSITION = "position"
VALID_POSITIONS = {"offen", "geschlossen"}
REFERENCE_DIR = "hoftor_vision"

_LOGGER = logging.getLogger(__name__)

CAMERA_SCHEMA = vol.Schema({vol.Required(CONF_ENTITY_ID): cv.entity_id})
CAPTURE_SCHEMA = CAMERA_SCHEMA.extend(
    {vol.Required(CONF_POSITION): vol.In(sorted(VALID_POSITIONS))}
)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    async def classify(call: ServiceCall) -> dict:
        entity_id = call.data[CONF_ENTITY_ID]
        try:
            last_result = {"position": "unklar", "reason": "keine_auswertung"}
            votes = {"offen": 0, "geschlossen": 0}
            last_recognized = {}
            # Manche Kameras liefern beim Abruf zunächst ein älteres I-Frame.
            # Einzelne alte oder verrauschte Bilder werden verworfen. Eine
            # Endlage gilt erst nach einer stabilen Serie oder einer sehr
            # deutlichen Mehrheit als bestätigt. Nur wenn über rund 20 Sekunden
            # nichts Belastbares entsteht, meldet der Dienst wirklich unklar.
            max_attempts = 30
            for attempt in range(1, max_attempts + 1):
                image = await async_get_image(hass, entity_id, timeout=15)
                last_result = await hass.async_add_executor_job(
                    _classify_bytes,
                    image.content,
                    _reference_path(hass, "offen"),
                    _reference_path(hass, "geschlossen"),
                )
                position = last_result["position"]
                if position in VALID_POSITIONS:
                    votes[position] += 1
                    last_recognized[position] = last_result
                    other = "geschlossen" if position == "offen" else "offen"
                    stable = votes[position] >= 4 and votes[other] == 0
                    robust_majority = votes[position] >= 6 and votes[other] <= 1
                    if stable or robust_majority:
                        result = dict(last_recognized[position])
                        result["samples"] = attempt
                        result["discarded_samples"] = attempt - votes[position]
                        return result
                if attempt < max_attempts:
                    await asyncio.sleep(0.7)
            last_result["position"] = "unklar"
            last_result["reason"] = (
                "widerspruechliche_endlage"
                if votes["offen"] and votes["geschlossen"]
                else "keine_stabile_endlage"
            )
            last_result["samples"] = max_attempts
            last_result["discarded_samples"] = (
                max_attempts - max(votes["offen"], votes["geschlossen"])
            )
            result = last_result
        except Exception as exc:  # Ein Fehler darf nie als Endlage gelten.
            _LOGGER.exception("Hoftor-Bildklassifizierung fehlgeschlagen")
            return {"position": "unklar", "reason": str(exc)}
        return result

    async def capture_reference(call: ServiceCall) -> None:
        entity_id = call.data[CONF_ENTITY_ID]
        position = call.data[CONF_POSITION]
        image = await async_get_image(hass, entity_id, timeout=15)
        await hass.async_add_executor_job(
            _write_reference, image.content, _reference_path(hass, position)
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLASSIFY,
        classify,
        schema=CAMERA_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CAPTURE, capture_reference, schema=CAPTURE_SCHEMA
    )
    return True


def _reference_path(hass: HomeAssistant, position: str) -> Path:
    return Path(hass.config.path(REFERENCE_DIR, f"{position}.jpg"))


def _write_reference(content: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _feature(content: bytes) -> Image.Image:
    with Image.open(io.BytesIO(content)) as image:
        gray = ImageOps.grayscale(image)
        # Nur der feste Torbereich; Autos, Pflanzen im Vordergrund und Zeitstempel
        # werden bewusst ausgeschlossen.
        width, height = gray.size
        crop = gray.crop(
            (int(width * 0.39), int(height * 0.16), int(width * 0.76), int(height * 0.49))
        )
        crop = crop.resize((296, 148), Image.Resampling.LANCZOS)
        crop = ImageOps.autocontrast(crop, cutoff=1)
        edges = crop.filter(ImageFilter.FIND_EDGES)
        return ImageOps.autocontrast(edges, cutoff=2)


def _distance(left: Image.Image, right: Image.Image) -> float:
    diff = ImageChops.difference(left, right)
    return fmean(diff.getdata())


def _classify_bytes(content: bytes, open_path: Path, closed_path: Path) -> dict:
    if not open_path.exists() or not closed_path.exists():
        return {"position": "unklar", "reason": "referenz_fehlt"}
    current = _feature(content)
    open_feature = _feature(open_path.read_bytes())
    closed_feature = _feature(closed_path.read_bytes())
    separation = _distance(open_feature, closed_feature)
    open_score = _distance(current, open_feature)
    closed_score = _distance(current, closed_feature)
    best = min(open_score, closed_score)
    margin = abs(open_score - closed_score)

    # Fail closed: Teilfahrt, starke Beleuchtungsabweichung oder Verdeckung wird
    # niemals auf eine Endlage geraten.
    # Sonnenstand und belaubte Umgebung veraendern die Kantenstaerke stark.
    # Die Positionsentscheidung beruht deshalb primaer auf dem Abstand beider
    # Referenzen; bei weniger als 18 % Trennabstand bleibt das Ergebnis unklar.
    if separation < 3 or best > separation * 1.10 or margin < separation * 0.18:
        position = "unklar"
        reason = "keine_eindeutige_endlage"
    elif open_score < closed_score:
        position = "offen"
        reason = "offen_referenz"
    else:
        position = "geschlossen"
        reason = "geschlossen_referenz"
    return {
        "position": position,
        "reason": reason,
        "open_score": round(open_score, 3),
        "closed_score": round(closed_score, 3),
        "reference_separation": round(separation, 3),
    }
