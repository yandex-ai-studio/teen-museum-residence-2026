#!/usr/bin/env python3
"""Prepare a compact, recommendation-friendly Pushkin Museum dataset."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


DEFAULT_SOURCE_URL = "https://pushkinmuseum.art/json/masterpieces.json"
DEFAULT_BUILDINGS_URL = "https://pushkinmuseum.art/json/buildings.json"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "pushkin.json"

TYPE_ALIASES = {
    "painting": "painting",
    "живопись": "painting",
    "graphics": "graphics",
    "графика": "graphics",
    "decorative, applied and folk art": "decorative_applied_art",
    "декоративно-прикладное и народное искусство": "decorative_applied_art",
    "декоративно-прикладное искусство": "decorative_applied_art",
    "numismatics": "numismatics",
    "нумизматика": "numismatics",
    "sculpture": "sculpture",
    "скульптура": "sculpture",
    "archeology": "archaeology",
    "archaeology": "archaeology",
    "археология": "archaeology",
    "casts": "casts",
    "слепки": "casts",
}

TAG_SEPARATOR_RE = re.compile(r"[,;|\n]+")
WHITESPACE_RE = re.compile(r"[\t\r\f\v ]+")


class DataPreparationError(RuntimeError):
    """Raised when a source cannot be loaded or has an unexpected shape."""


class _HTMLTextExtractor(HTMLParser):
    """Extract readable text while retaining useful paragraph boundaries."""

    BLOCK_TAGS = {"br", "div", "li", "p", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        lines = []
        for line in "".join(self.parts).splitlines():
            normalized = WHITESPACE_RE.sub(" ", line).strip()
            if normalized:
                lines.append(normalized)
        return "\n".join(lines)


def clean_text(value: Any) -> str | None:
    """Return cleaned plain text, or None for an absent value."""

    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    if not value.strip():
        return None

    parser = _HTMLTextExtractor()
    parser.feed(value)
    parser.close()
    text = parser.text()
    return text or None


def russian(value: Any) -> str | None:
    """Read and clean a Russian localized value."""

    if not isinstance(value, dict):
        return None
    return clean_text(value.get("ru"))


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    """Download a JSON object and validate its root shape."""

    request = Request(
        url,
        headers={"User-Agent": "teen-museum-residence-data-preparer/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
        data = json.loads(payload.decode("utf-8"))
    except HTTPError as error:
        raise DataPreparationError(
            f"failed to download {url}: HTTP {error.code} {error.reason}"
        ) from error
    except (URLError, TimeoutError) as error:
        raise DataPreparationError(f"failed to download {url}: {error}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DataPreparationError(f"invalid UTF-8 JSON from {url}: {error}") from error

    if not isinstance(data, dict):
        raise DataPreparationError(
            f"unexpected JSON root from {url}: expected an object, got {type(data).__name__}"
        )
    return data


def sortable_key(value: Any) -> tuple[int, int | str]:
    """Sort numeric identifiers numerically and everything else lexically."""

    text = str(value)
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)


def sorted_mapping_values(value: Any) -> Iterable[Any]:
    if not isinstance(value, dict):
        return ()
    return (value[key] for key in sorted(value, key=sortable_key))


def deduplicate_strings(values: Iterable[str | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        key = WHITESPACE_RE.sub(" ", value).strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value.strip())
    return result


def normalize_type(value: Any) -> str:
    ru_value = russian(value)
    en_value = clean_text(value.get("en")) if isinstance(value, dict) else None

    for candidate in (en_value, ru_value):
        if candidate and candidate.casefold() in TYPE_ALIASES:
            return TYPE_ALIASES[candidate.casefold()]

    source = en_value or ru_value or "unknown"
    ascii_value = (
        unicodedata.normalize("NFKD", source).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value.casefold()).strip("_")
    return slug or "unknown"


def normalize_year(value: Any) -> int | None:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if year != 0 else None


def build_description(record: dict[str, Any]) -> str | None:
    """Combine the available Russian descriptions without repeated excerpts."""

    fragments: list[tuple[str, str]] = []
    for field in ("text", "annotation", "searcha"):
        candidate = russian(record.get(field))
        if not candidate:
            continue
        if field == "searcha" and len(candidate.split()) < 4:
            # Some records use searcha as a one-word object-class marker
            # (for example, "Картина"), not as meaningful short information.
            continue
        normalized = " ".join(candidate.split()).casefold()

        if any(normalized == existing or normalized in existing for _, existing in fragments):
            continue

        fragments = [
            (text, existing)
            for text, existing in fragments
            if existing not in normalized
        ]
        fragments.append((candidate, normalized))

    return "\n\n".join(text for text, _ in fragments) or None


def build_authors(record: dict[str, Any]) -> list[str]:
    authors = (
        russian(author)
        for author in sorted_mapping_values(record.get("authors"))
    )
    return deduplicate_strings(authors)


def build_tags(record: dict[str, Any]) -> list[str]:
    values: list[str | None] = []

    keyword_text = russian(record.get("seakeys"))
    if keyword_text:
        values.extend(clean_text(part) for part in TAG_SEPARATOR_RE.split(keyword_text))

    period = record.get("period")
    period_name = russian(period.get("name")) if isinstance(period, dict) else None
    values.extend(
        [
            russian(record.get("type")),
            russian(record.get("country")),
            period_name,
            russian(record.get("paint_school")),
            russian(record.get("graphics_type")),
        ]
    )
    return deduplicate_strings(values)


def source_origin(source_url: str) -> str:
    parsed = urlsplit(source_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/"
    return "https://pushkinmuseum.art/"


def build_image_url(record: dict[str, Any], origin: str) -> str | None:
    gallery = record.get("gallery")
    if not isinstance(gallery, dict) or not gallery:
        return None

    group_key = "1" if "1" in gallery else min(gallery, key=sortable_key)
    group = gallery.get(group_key)
    if not isinstance(group, dict):
        return None

    for variant in ("id03", "id02", "id01"):
        path = clean_text(group.get(variant))
        if path:
            return urljoin(origin, path)
    return None


def build_location_indexes(
    buildings: dict[str, Any],
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    building_names: dict[str, str | None] = {}
    hall_names: dict[str, str | None] = {}

    for building_id, building in buildings.items():
        if not isinstance(building, dict):
            continue
        building_names[str(building_id)] = russian(building.get("name"))

        floors = building.get("floors")
        if not isinstance(floors, dict):
            continue
        for floor in floors.values():
            if not isinstance(floor, dict):
                continue
            halls = floor.get("halls")
            if not isinstance(halls, dict):
                continue
            for hall_id, hall in halls.items():
                hall_names[str(hall_id)] = (
                    russian(hall.get("name")) if isinstance(hall, dict) else None
                )

    return building_names, hall_names


def location_entry(
    identifier: Any, names: dict[str, str | None]
) -> dict[str, str | None] | None:
    if identifier is None or str(identifier).strip() == "":
        return None
    normalized_id = str(identifier)
    return {"id": normalized_id, "name": names.get(normalized_id)}


def transform_record(
    item_id: str,
    record: dict[str, Any],
    origin: str,
    building_names: dict[str, str | None],
    hall_names: dict[str, str | None],
) -> dict[str, Any]:
    period = record.get("period")
    period_name = russian(period.get("name")) if isinstance(period, dict) else None
    period_details = russian(period.get("text")) if isinstance(period, dict) else None

    item_path = clean_text(record.get("path"))
    return {
        "id": str(item_id),
        "type": normalize_type(record.get("type")),
        "title": russian(record.get("name")),
        "country": russian(record.get("country")),
        "period": {
            "year": normalize_year(record.get("year")),
            "name": period_name,
            "details": period_details,
        },
        "authors": build_authors(record),
        "material": russian(record.get("material")),
        "image_url": build_image_url(record, origin),
        "description": build_description(record),
        "location": {
            "building": location_entry(record.get("building"), building_names),
            "hall": location_entry(record.get("hall"), hall_names),
            "show_in_hall": str(record.get("show_in_hall", "0")) == "1",
        },
        "tags": build_tags(record),
        "inventory_number": clean_text(record.get("inv_num")),
        "source_url": urljoin(origin, item_path) if item_path else None,
    }


def prepare_records(
    masterpieces: dict[str, Any], buildings: dict[str, Any], source_url: str
) -> list[dict[str, Any]]:
    building_names, hall_names = build_location_indexes(buildings)
    origin = source_origin(source_url)
    records: list[dict[str, Any]] = []

    for item_id in sorted(masterpieces, key=sortable_key):
        source_record = masterpieces[item_id]
        if not isinstance(source_record, dict):
            raise DataPreparationError(
                f"unexpected record {item_id!r}: expected an object, "
                f"got {type(source_record).__name__}"
            )
        records.append(
            transform_record(
                str(item_id),
                source_record,
                origin,
                building_names,
                hall_names,
            )
        )

    return records


def atomic_write_json(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(serialized)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a recommendation-friendly Pushkin Museum JSON dataset."
    )
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--buildings-url", default=DEFAULT_BUILDINGS_URL)
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output path; relative paths are resolved from the project root.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    return args


def resolve_output_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = resolve_output_path(args.output)

    try:
        masterpieces = fetch_json(args.source_url, args.timeout)
        buildings = fetch_json(args.buildings_url, args.timeout)
        records = prepare_records(masterpieces, buildings, args.source_url)
        atomic_write_json(output_path, records)
    except (DataPreparationError, OSError) as error:
        print(f"prepare-data: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {len(records)} exhibits to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
