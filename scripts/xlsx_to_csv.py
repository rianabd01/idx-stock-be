#!/usr/bin/env python3
"""
Convert .xlsx files to CSV using only Python standard library.

Usage:
  python xlsx_to_csv.py input.xlsx
  python xlsx_to_csv.py input.xlsx output_dir
  python xlsx_to_csv.py input.xlsx output.csv --sheet "Sheet1"

Notes:
- If workbook has multiple sheets, the script writes one CSV per sheet into output_dir.
- Formula cells are exported using cached values stored in the workbook, if available.
- Dates are exported as their raw Excel serial values because .xlsx date formatting lives in styles.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree as ET

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "sheet"


def col_to_index(cell_ref: str) -> int:
    """Return zero-based column index from an Excel cell reference like 'C12'."""
    letters = re.match(r"[A-Z]+", cell_ref.upper())
    if not letters:
        return 0
    idx = 0
    for ch in letters.group(0):
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def read_xml(zf: zipfile.ZipFile, path: str) -> ET.Element:
    with zf.open(path) as f:
        return ET.parse(f).getroot()


def read_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    path = "xl/sharedStrings.xml"
    if path not in zf.namelist():
        return []

    root = read_xml(zf, path)
    strings: List[str] = []
    for si in root.findall(f"{NS_MAIN}si"):
        parts: List[str] = []
        # Shared strings may be plain <t> or rich text <r><t>...</t></r>
        for t in si.iter(f"{NS_MAIN}t"):
            parts.append(t.text or "")
        strings.append("".join(parts))
    return strings


def read_workbook_sheets(zf: zipfile.ZipFile) -> List[Tuple[str, str]]:
    """Return list of (sheet_name, sheet_xml_path)."""
    wb_root = read_xml(zf, "xl/workbook.xml")
    rels_root = read_xml(zf, "xl/_rels/workbook.xml.rels")

    rel_targets: Dict[str, str] = {}
    for rel in rels_root.findall(f"{NS_PKG_REL}Relationship"):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if not rel_id:
            continue
        # Targets are usually 'worksheets/sheet1.xml'. Make them absolute within xl/.
        if target.startswith("/"):
            target_path = target.lstrip("/")
        else:
            target_path = "xl/" + target
        rel_targets[rel_id] = target_path

    sheets: List[Tuple[str, str]] = []
    sheets_node = wb_root.find(f"{NS_MAIN}sheets")
    if sheets_node is None:
        return sheets

    for sheet in sheets_node.findall(f"{NS_MAIN}sheet"):
        name = sheet.attrib.get("name", "Sheet")
        rel_id = sheet.attrib.get(f"{NS_REL}id")
        if rel_id and rel_id in rel_targets:
            sheets.append((name, rel_targets[rel_id]))
    return sheets


def cell_text(cell: ET.Element, shared_strings: List[str]) -> str:
    cell_type = cell.attrib.get("t")

    if cell_type == "inlineStr":
        inline = cell.find(f"{NS_MAIN}is")
        if inline is None:
            return ""
        return "".join(t.text or "" for t in inline.iter(f"{NS_MAIN}t"))

    value_node = cell.find(f"{NS_MAIN}v")
    if value_node is None or value_node.text is None:
        return ""

    value = value_node.text

    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value
    if cell_type == "b":
        return "TRUE" if value == "1" else "FALSE"

    # For numeric/date/formula cached values, keep the stored value.
    return value


def iter_sheet_rows(
    zf: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: List[str],
) -> Iterable[List[str]]:
    root = read_xml(zf, sheet_path)
    sheet_data = root.find(f"{NS_MAIN}sheetData")
    if sheet_data is None:
        return []

    rows: List[List[str]] = []
    for row in sheet_data.findall(f"{NS_MAIN}row"):
        values: List[str] = []
        for cell in row.findall(f"{NS_MAIN}c"):
            ref = cell.attrib.get("r", "A1")
            col_idx = col_to_index(ref)
            while len(values) <= col_idx:
                values.append("")
            values[col_idx] = cell_text(cell, shared_strings)
        rows.append(values)

    # Normalize all rows to the same width so CSV columns line up.
    max_cols = max((len(row) for row in rows), default=0)
    for row in rows:
        row.extend([""] * (max_cols - len(row)))
    return rows


def trim_rows(rows: List[List[str]], skip_rows: Optional[int]) -> List[List[str]]:
    if skip_rows is not None:
        return rows[skip_rows:]

    for idx, row in enumerate(rows):
        if row[:4] == ["DATE", "SHARE_CODE", "ISSUER_NAME", "INVESTOR_NAME"]:
            return rows[idx:]
    return rows


def convert_xlsx_to_csv(
    input_xlsx: Path,
    output: Optional[Path] = None,
    sheet_name: Optional[str] = None,
    delimiter: str = ",",
    encoding: str = "utf-8-sig",
    skip_rows: Optional[int] = None,
) -> List[Path]:
    if not input_xlsx.exists():
        raise FileNotFoundError(f"File not found: {input_xlsx}")

    written: List[Path] = []
    with zipfile.ZipFile(input_xlsx) as zf:
        shared_strings = read_shared_strings(zf)
        sheets = read_workbook_sheets(zf)
        if not sheets:
            raise ValueError("No worksheets found in the workbook.")

        if sheet_name:
            matches = [(name, path) for name, path in sheets if name == sheet_name]
            if not matches:
                available = ", ".join(name for name, _ in sheets)
                raise ValueError(f"Sheet '{sheet_name}' not found. Available sheets: {available}")
            sheets = matches

        if output is None:
            output = input_xlsx.with_suffix("")

        single_sheet_to_file = len(sheets) == 1 and output.suffix.lower() == ".csv"
        if single_sheet_to_file:
            output.parent.mkdir(parents=True, exist_ok=True)
        else:
            output.mkdir(parents=True, exist_ok=True)

        for name, path in sheets:
            rows = trim_rows(list(iter_sheet_rows(zf, path, shared_strings)), skip_rows)
            if single_sheet_to_file:
                csv_path = output
            else:
                csv_path = output / f"{safe_filename(name)}.csv"

            with csv_path.open("w", newline="", encoding=encoding) as f:
                writer = csv.writer(f, delimiter=delimiter)
                writer.writerows(rows)
            written.append(csv_path)

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert .xlsx workbook sheets to CSV files.")
    parser.add_argument("input_xlsx", type=Path, help="Path to the input .xlsx file")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=None,
        help="Output CSV file for one sheet, or output directory for multiple sheets",
    )
    parser.add_argument("--sheet", help="Export only one sheet by exact sheet name")
    parser.add_argument("--delimiter", default=",", help="CSV delimiter, default: comma")
    parser.add_argument("--encoding", default="utf-8-sig", help="Output encoding, default: utf-8-sig")
    parser.add_argument("--skip-rows", type=int, default=None, help="Rows to skip from the top of each sheet. By default, auto-detects the header row.")

    args = parser.parse_args()

    try:
        written = convert_xlsx_to_csv(
            input_xlsx=args.input_xlsx,
            output=args.output,
            sheet_name=args.sheet,
            delimiter=args.delimiter,
            encoding=args.encoding,
            skip_rows=args.skip_rows,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
