"""Reader for OPALX's single-page, row-oriented ASCII SDDS statistics.

This deliberately is not a general SDDS implementation: binary, row-counted,
array and string-column layouts are rejected. One parameter value occupies one
line, as in OPALX's output (unquoted revision strings may contain spaces).
"""

from pathlib import Path
import re
import shlex

import numpy as np

from ..models import FieldMetadata, SourceMetadata, StatisticsTable


_DTYPES = {"double": "float64", "float": "float32", "short": "int16",
           "int": "int32", "long": "int32", "long64": "int64"}
_END = re.compile(r'"(?:\\.|[^"\\])*"|&end\b', re.IGNORECASE)
_ENTRY = re.compile(r'\s*(\w+)\s*=\s*("(?:\\.|[^"\\])*"|[^,]+)\s*(?:,|$)')


def _attributes(text: str) -> dict[str, str]:
    result = {}
    while text.strip():
        match = _ENTRY.match(text)
        if not match:
            raise ValueError(f"Malformed SDDS header attributes: {text!r}")
        key, value = match.groups()
        value = value.strip()
        if value.startswith('"'):
            value = shlex.split(value, comments=False)[0]
        if key in result:
            raise ValueError(f"Duplicate SDDS attribute: {key}")
        result[key] = value
        text = text[match.end():]
    return result


def _number(token: str, type_name: str):
    if type_name not in _DTYPES:
        raise ValueError(f"Unsupported SDDS numeric type: {type_name}")
    dtype = np.dtype(_DTYPES[type_name])
    if dtype.kind == "i":
        value = int(token)  # Never round integer identifiers through float.
        bounds = np.iinfo(dtype)
        if not bounds.min <= value <= bounds.max:
            raise ValueError(f"Integer out of range for {type_name}: {token}")
        return value
    return float(token)


def read_stat(path: str | Path) -> StatisticsTable:
    """Load all statistics columns, retaining units, descriptions and parameters.

    Empty tables and nonfinite floating values are retained for later physical
    validation. Malformed rows are errors, never silently skipped. Header
    definitions are retained in source.attributes['sdds_header']; parameter
    values are directly accessible there by their original names.
    """
    path = Path(path).resolve()
    try:
        return _read_stat(path)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError(f"{path}: {error}") from error


def _read_stat(path: Path) -> StatisticsTable:
    lines = iter(enumerate(path.read_text(encoding="utf-8").splitlines(), 1))
    if next(lines, (0, ""))[1].strip() != "SDDS1":
        raise ValueError("Expected SDDS1 header")
    header = []
    for line_number, line in lines:
        if not line.strip() or line.lstrip().startswith("!"):
            continue
        match = re.match(r"\s*&(\w+)\b(.*)", line)
        if not match:
            raise ValueError(f"Expected SDDS header block at line {line_number}")
        kind, body = match.groups()
        while True:
            end = next((m for m in _END.finditer(body) if m.group().lower() == "&end"), None)
            if end:
                if body[end.end():].strip():
                    raise ValueError("Unexpected text after &end")
                attrs = _attributes(body[:end.start()])
                break
            try:
                _, continuation = next(lines)
            except StopIteration:
                raise ValueError(f"Unterminated &{kind} block") from None
            if not continuation.lstrip().startswith("!"):
                body += "\n" + continuation
        kind = kind.lower()
        if kind not in ("description", "parameter", "column", "data"):
            raise ValueError(f"Unsupported SDDS block: &{kind}")
        header.append((kind, attrs))
        if kind == "data":
            break
    else:
        raise ValueError("Missing &data block")

    data = header[-1][1]
    supported = {"mode": "ascii", "no_row_counts": "1", "lines_per_row": "1",
                 "column_major_order": "0", "additional_header_lines": "0"}
    if data.get("mode") != "ascii" or data.get("no_row_counts") != "1":
        raise ValueError("Only ASCII SDDS with no_row_counts=1 is supported")
    if any(key not in supported or value != supported[key] for key, value in data.items()):
        raise ValueError(f"Unsupported SDDS data layout: {data}")

    definitions = [attrs for kind, attrs in header if kind == "column"]
    parameters = [attrs for kind, attrs in header if kind == "parameter"]
    if not definitions:
        raise ValueError("No SDDS columns declared")
    names = [item.get("name") for item in definitions + parameters]
    if None in names or len(set(names)) != len(names) or "sdds_header" in names:
        raise ValueError("Missing, duplicate or reserved SDDS column/parameter name")
    for item in definitions:
        if item.get("type") not in _DTYPES or "field_length" in item:
            raise ValueError(f"Unsupported SDDS column definition: {item}")

    # Consume parameter lines before interpreting any line as a table row.
    content = ((n, line.strip()) for n, line in lines
               if line.strip() and not line.lstrip().startswith("!"))
    metadata = {"sdds_header": header}
    for item in parameters:
        type_name = item.get("type")
        if type_name not in _DTYPES and type_name != "string":
            raise ValueError(f"Unsupported SDDS parameter type: {type_name}")
        if "fixed_value" in item:
            value = item["fixed_value"]
        else:
            try:
                _, value = next(content)
            except StopIteration:
                raise ValueError(f"Missing SDDS parameter value: {item['name']}") from None
        if type_name == "string":
            if value.startswith('"'):
                tokens = shlex.split(value, comments=False)
                if len(tokens) != 1:
                    raise ValueError(f"Malformed string parameter: {item['name']}")
                value = tokens[0]
        else:
            value = _number(value, type_name)
        metadata[item["name"]] = value

    columns = {item["name"]: [] for item in definitions}
    for line_number, line in content:
        tokens = line.split()
        if len(tokens) != len(definitions):
            raise ValueError(f"Wrong column count at line {line_number}: expected {len(definitions)}, got {len(tokens)}")
        for item, token in zip(definitions, tokens):
            try:
                columns[item["name"]].append(_number(token, item["type"]))
            except ValueError as error:
                raise ValueError(f"Invalid {item['name']} at line {line_number}: {error}") from error
    arrays = {item["name"]: np.asarray(columns[item["name"]], dtype=_DTYPES[item["type"]])
              for item in definitions}
    version = metadata.get("revision")
    return StatisticsTable(
        columns=arrays,
        source=SourceMetadata(path, version if isinstance(version, str) else None, metadata),
        fields={item["name"]: FieldMetadata(item.get("units"), item.get("description"))
                for item in definitions},
    )
