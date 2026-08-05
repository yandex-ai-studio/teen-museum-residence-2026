#!/usr/bin/env python3
"""Prepare pre-split JSONL chunks for Yandex File Search."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "pushkin.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "pushkin.jsonl"
MAX_CHUNK_LENGTH = 8000


class JsonlPreparationError(RuntimeError):
    """Raised when source data cannot be transformed into JSONL chunks."""


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Pushkin Museum JSONL chunks for Yandex File Search."
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Input JSON path; relative paths are resolved from the project root.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSONL path; relative paths are resolved from the project root.",
    )
    return parser.parse_args(argv)


def load_records(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise JsonlPreparationError(f"input file not found: {path}") from error
    except OSError as error:
        raise JsonlPreparationError(f"failed to read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise JsonlPreparationError(f"invalid JSON in {path}: {error}") from error

    if not isinstance(data, list):
        raise JsonlPreparationError(
            f"unexpected JSON root in {path}: expected a list, got {type(data).__name__}"
        )

    records: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise JsonlPreparationError(
                f"unexpected record at index {index}: expected an object, "
                f"got {type(item).__name__}"
            )
        records.append(item)
    return records


def text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def list_text(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    return ", ".join(text_value(value) for value in values if text_value(value))


def location_name(location: Any) -> str:
    if not isinstance(location, dict):
        return ""

    names: list[str] = []
    for field in ("building", "hall"):
        item = location.get(field)
        if isinstance(item, dict):
            name = text_value(item.get("name"))
            if name:
                names.append(name)
    return ", ".join(names)


def build_body(record: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Title: {text_value(record.get('title'))}",
            f"Artist: {list_text(record.get('authors'))}",
            f"Location: {location_name(record.get('location'))}",
            f"Url: {text_value(record.get('source_url'))}",
            f"Tags: {list_text(record.get('tags'))}",
            "---",
            text_value(record.get("description")),
        ]
    )


def build_chunks(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for index, record in enumerate(records):
        body = build_body(record)
        if len(body) > MAX_CHUNK_LENGTH:
            item_id = text_value(record.get("id")) or f"index {index}"
            raise JsonlPreparationError(
                f"chunk for record {item_id} is {len(body)} characters; "
                f"maximum is {MAX_CHUNK_LENGTH}"
            )
        chunks.append({"body": body})
    return chunks


def atomic_write_jsonl(path: Path, chunks: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
            for chunk in chunks:
                line = json.dumps(chunk, ensure_ascii=False, separators=(",", ":"))
                temporary_file.write(line + "\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = resolve_project_path(args.input)
    output_path = resolve_project_path(args.output)

    try:
        records = load_records(input_path)
        chunks = build_chunks(records)
        atomic_write_jsonl(output_path, chunks)
    except (JsonlPreparationError, OSError) as error:
        print(f"prepare-jsonl: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {len(chunks)} chunks to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
