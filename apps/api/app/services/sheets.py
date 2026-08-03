"""Reading target lists out of CSV and Excel files.

Unused in v1. Bulk import is a later milestone; this is here because the
parsing is sound and worth not rewriting, and because it is the one piece of
the old CLI that survives without being deliverability logic.

Two things need attention before it is wired up: the alias table in
`suggest_mapping` still names the old contact columns (first_name, last_name,
title) rather than the target model's name / company / role / hook / intent,
and nothing here enforces the per-target caps - a bulk importer that skips
`may_schedule_touch` would be a way around the limits that make this tool safe.

An .xlsx is a zip of XML, so this needs no openpyxl. What is supported is
deliberately narrow: the first worksheet, a header row, and cell values as
text. Formulas resolve to their last cached value, which is what the
spreadsheet showed when it was saved.

Numbers and dates are returned as whatever string the file stored, because a
merge field is going into an email either way - reformatting a phone number or
a date here would only surprise the person who typed it.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from xml.etree import ElementTree

MAX_ROWS = 5000


class SheetError(Exception):
    pass


def _column_index(ref: str) -> int:
    """'A' -> 0, 'Z' -> 25, 'AA' -> 26."""
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return max(0, index - 1)


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    out = []
    for item in root:
        # Rich text splits one string across several <t> runs.
        out.append("".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")))
    return out


def _first_sheet_path(archive: zipfile.ZipFile) -> str:
    names = [n for n in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)]
    if not names:
        raise SheetError("that .xlsx has no worksheets")
    return sorted(names, key=lambda n: int(re.search(r"(\d+)", n).group(1)))[0]


def _read_xlsx(data: bytes) -> list[list[str]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SheetError(
            "that file isn't a readable .xlsx. If it's an old .xls, open it in "
            "Excel and Save As .xlsx or .csv first."
        ) from exc

    with archive:
        shared = _shared_strings(archive)
        root = ElementTree.fromstring(archive.read(_first_sheet_path(archive)))

        rows: list[list[str]] = []
        for row in root.iter():
            if not row.tag.endswith("}row"):
                continue
            cells: dict[int, str] = {}
            for cell in row:
                if not cell.tag.endswith("}c"):
                    continue
                kind = cell.get("t")
                value = ""
                if kind == "inlineStr":
                    value = "".join(
                        node.text or "" for node in cell.iter() if node.tag.endswith("}t")
                    )
                else:
                    node = cell.find("{*}v")
                    raw = node.text if node is not None else None
                    if raw is not None:
                        if kind == "s":
                            try:
                                value = shared[int(raw)]
                            except (ValueError, IndexError):
                                value = ""
                        else:
                            value = raw
                cells[_column_index(cell.get("r", "A"))] = value.strip()

            width = max(cells) + 1 if cells else 0
            rows.append([cells.get(i, "") for i in range(width)])
            if len(rows) > MAX_ROWS:
                break
        return rows


def _read_csv(data: bytes) -> list[list[str]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SheetError("could not decode that CSV - save it as UTF-8 and retry")

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [
        [(cell or "").strip() for cell in row]
        for row in list(csv.reader(io.StringIO(text), dialect))[: MAX_ROWS + 1]
    ]


def read_table(data: bytes, filename: str) -> tuple[list[str], list[dict[str, str]]]:
    """Return (headers, rows) from a CSV or XLSX file.

    Headers keep their original spelling for display; rows are keyed by the
    same strings, so the caller maps them onto merge fields explicitly rather
    than guessing from a normalised name.
    """
    lowered = filename.lower()
    if lowered.endswith(".xlsx") or lowered.endswith(".xlsm"):
        grid = _read_xlsx(data)
    elif lowered.endswith(".csv") or lowered.endswith(".tsv") or lowered.endswith(".txt"):
        grid = _read_csv(data)
    elif lowered.endswith(".xls"):
        raise SheetError(
            "the old .xls format isn't supported - open it in Excel and Save As "
            ".xlsx or .csv"
        )
    else:
        raise SheetError(f"don't know how to read {filename!r} - use .csv or .xlsx")

    grid = [row for row in grid if any(cell.strip() for cell in row)]
    if not grid:
        raise SheetError("that file is empty")

    headers = [cell.strip() for cell in grid[0]]
    if not any(headers):
        raise SheetError("the first row must be column headers")

    # Excel files often carry trailing formatted-but-empty columns.
    while headers and not headers[-1]:
        headers.pop()
    for index, name in enumerate(headers):
        if not name:
            headers[index] = f"column_{index + 1}"

    rows: list[dict[str, str]] = []
    for raw in grid[1:]:
        row = {
            headers[i]: (raw[i].strip() if i < len(raw) else "")
            for i in range(len(headers))
        }
        if any(row.values()):
            rows.append(row)
    return headers, rows


def suggest_mapping(headers: list[str], targets: list[str]) -> dict[str, str]:
    """Guess which column feeds which merge field.

    Exact match first, then a loose match ignoring case, spaces and
    punctuation, so "First Name" and "first_name" line up without the operator
    having to rename anything.
    """
    def key(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", text.lower())

    by_key = {key(t): t for t in targets}
    aliases = {
        "emailaddress": "email", "mail": "email", "e": "email",
        "firstname": "first_name", "fname": "first_name", "given": "first_name",
        "lastname": "last_name", "lname": "last_name", "surname": "last_name",
        "organisation": "company", "organization": "company", "org": "company",
        "employer": "company", "jobtitle": "title", "role": "title",
    }

    mapping: dict[str, str] = {}
    for header in headers:
        k = key(header)
        target = by_key.get(k) or (aliases.get(k) if aliases.get(k) in targets else None)
        if target and target not in mapping.values():
            mapping[header] = target
    return mapping
