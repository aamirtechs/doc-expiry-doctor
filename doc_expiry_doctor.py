"""doc-expiry-doctor: track document expiries from a JSON file.

Zero-dependency Python CLI. It reads a JSON file of documents (one per
record), sorts them by expiry date, and reports what is already expired
and what expires soon. Typical records are driver documents: a CDL, a
medical card, insurance, and vehicle registration, each with a holder.

Input format: a JSON list, or an object with a "documents" list. Each
record needs:

    holder:        who the document belongs to (string, required)
    type:          document type, for example "CDL" (string, required)
    expiry:        expiry date in ISO format YYYY-MM-DD (required)
    reminder_days: optional per-record reminder window in days

"document_type" is accepted as an alias for "type", and "expiry_date"
is accepted as an alias for "expiry".

A record's own reminder_days, when set, overrides the global --within
window for that record. So a CDL with reminder_days 60 shows up in a
default 30 day report once it is 60 days from expiry.

Exit codes: 0 success, 2 usage, input, or validation error. A report
that lists expired documents still exits 0: it is a report, not a gate.
Use --check when you want validation to fail a build.
"""

import argparse
import json
import re
import sys
from datetime import date

__version__ = "1.0.0"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(text):
    """Parse a strict ISO date (YYYY-MM-DD) or raise ValueError."""
    if not isinstance(text, str) or not _DATE_RE.match(text):
        raise ValueError("not an ISO date (expected YYYY-MM-DD): %r" % (text,))
    year, month, day = (int(part) for part in text.split("-"))
    try:
        return date(year, month, day)
    except ValueError:
        raise ValueError("not a real calendar date: %r" % (text,))


def _field(record, *names):
    """Return the first present, non-None field among names, else None."""
    for name in names:
        if name in record and record[name] is not None:
            return record[name]
    return None


def normalize_record(raw, index):
    """Validate one raw record.

    Returns (record, error). Exactly one of the two is None. The
    normalized record has keys: holder, type, expiry (a date), expiry
    (ISO string kept as "expiry"), and reminder_days (int or None).
    """
    label = "record %d" % (index + 1,)
    if not isinstance(raw, dict):
        return None, "%s: expected an object, got %s" % (
            label,
            type(raw).__name__,
        )
    holder = _field(raw, "holder")
    doc_type = _field(raw, "type", "document_type")
    expiry_raw = _field(raw, "expiry", "expiry_date")
    reminder = _field(raw, "reminder_days")
    if not isinstance(holder, str) or not holder.strip():
        return None, "%s: missing or empty required field 'holder'" % label
    if not isinstance(doc_type, str) or not doc_type.strip():
        return None, "%s: missing or empty required field 'type'" % label
    if expiry_raw is None:
        return None, "%s: missing required field 'expiry'" % label
    try:
        expiry = parse_date(expiry_raw)
    except ValueError as exc:
        return None, "%s: invalid 'expiry': %s" % (label, exc)
    if reminder is not None:
        if isinstance(reminder, bool) or not isinstance(reminder, int):
            return None, "%s: 'reminder_days' must be a whole number" % label
        if reminder < 0:
            return None, "%s: 'reminder_days' must not be negative" % label
    return {
        "holder": holder.strip(),
        "type": doc_type.strip(),
        "expiry": expiry.isoformat(),
        "reminder_days": reminder,
    }, None


def load_documents(path):
    """Load and validate a documents file.

    Returns (records, errors). Records are normalized dicts in file
    order; errors is a list of strings, empty when the file is valid.
    Raises ValueError for file-level problems (unreadable JSON, wrong
    top-level shape), which the CLI turns into an exit code 2 error.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise ValueError("cannot read %s: %s" % (path, exc))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON in %s: %s" % (path, exc))
    if isinstance(data, dict):
        raw_records = data.get("documents")
        if raw_records is None:
            raise ValueError(
                "%s: expected a list, or an object with a 'documents' list"
                % path
            )
    else:
        raw_records = data
    if not isinstance(raw_records, list):
        raise ValueError("%s: expected a list of records" % path)
    records = []
    errors = []
    for index, raw in enumerate(raw_records):
        record, error = normalize_record(raw, index)
        if error is not None:
            errors.append(error)
        else:
            records.append(record)
    return records, errors


def days_until(record, today):
    """Days from today until a record's expiry (negative if expired)."""
    return (parse_date(record["expiry"]) - today).days


def effective_window(record, within):
    """Reminder window for a record: its own reminder_days, else within."""
    if record.get("reminder_days") is not None:
        return record["reminder_days"]
    return within


def classify(record, today, within):
    """Return (status, days_until) for a record.

    Status is one of "expired", "expiring_soon", or "later".
    """
    days = days_until(record, today)
    if days < 0:
        return "expired", days
    if days <= effective_window(record, within):
        return "expiring_soon", days
    return "later", days


def apply_filters(records, types, holders):
    """Filter by type (exact, case-insensitive) and holder (substring).

    Each filter list is OR within itself; the two filters combine
    with AND. Empty lists mean no filtering on that field.
    """
    result = records
    if types:
        wanted = {value.lower() for value in types}
        result = [r for r in result if r["type"].lower() in wanted]
    if holders:
        wanted = [value.lower() for value in holders]
        result = [
            r
            for r in result
            if any(w in r["holder"].lower() for w in wanted)
        ]
    return result


def sort_records(records):
    """Sort by expiry date, then holder, then type."""
    return sorted(
        records,
        key=lambda r: (r["expiry"], r["holder"].lower(), r["type"].lower()),
    )


def describe_days(days):
    """Human phrase for a days-until value."""
    if days == 0:
        return "expires today"
    if days == 1:
        return "in 1 day"
    if days == -1:
        return "1 day ago"
    if days > 0:
        return "in %d days" % days
    return "%d days ago" % (-days)


def record_view(record, today, within):
    """JSON-ready view of a record with status and days until expiry."""
    status, days = classify(record, today, within)
    view = dict(record)
    view["status"] = status
    view["days_until"] = days
    return view


def partition(records, today, within):
    """Split sorted records into expired, expiring_soon, and later."""
    buckets = {"expired": [], "expiring_soon": [], "later": []}
    for record in sort_records(records):
        status, _days = classify(record, today, within)
        buckets[status].append(record)
    return buckets


def render_text(records, today, within, path, show_all, expired_only):
    """Render the text report. Records shown depend on the mode."""
    buckets = partition(records, today, within)
    lines = [
        "doc-expiry-doctor %s | today %s | within %d days"
        % (__version__, today.isoformat(), within),
        "input: %s (%d records)" % (path, len(records)),
        "",
    ]
    if show_all:
        lines.append(
            "All documents, sorted by expiry (%d):" % len(records)
        )
        lines.append("")
        labels = {
            "expired": "EXPIRED",
            "expiring_soon": "EXPIRING SOON",
            "later": "LATER",
        }
        for record in sort_records(records):
            status, days = classify(record, today, within)
            lines.append(
                "  %-13s %s  %s  %s  (%s)"
                % (
                    labels[status],
                    record["expiry"],
                    record["holder"],
                    record["type"],
                    describe_days(days),
                )
            )
        lines.append("")
    else:
        shown = buckets["expired"]
        if not expired_only:
            shown = shown + buckets["expiring_soon"]
        if buckets["expired"]:
            lines.append("Already expired (%d):" % len(buckets["expired"]))
            for record in buckets["expired"]:
                days = days_until(record, today)
                lines.append(
                    "  EXPIRED       %s  %s  %s  (%s)"
                    % (
                        record["expiry"],
                        record["holder"],
                        record["type"],
                        describe_days(days),
                    )
                )
            lines.append("")
        if not expired_only:
            lines.append(
                "Expiring within %d days (%d):"
                % (within, len(buckets["expiring_soon"]))
            )
            for record in buckets["expiring_soon"]:
                days = days_until(record, today)
                note = ""
                if record["reminder_days"] is not None:
                    note = "  [reminder %d days]" % record["reminder_days"]
                lines.append(
                    "  EXPIRING SOON %s  %s  %s  (%s)%s"
                    % (
                        record["expiry"],
                        record["holder"],
                        record["type"],
                        describe_days(days),
                        note,
                    )
                )
            lines.append("")
        if not shown:
            if expired_only:
                lines.append("No expired documents.")
            else:
                lines.append(
                    "No documents expired and none expiring within %d days."
                    % within
                )
            lines.append("")
    lines.append(
        "Summary: %d expired, %d expiring soon, %d later, %d total"
        % (
            len(buckets["expired"]),
            len(buckets["expiring_soon"]),
            len(buckets["later"]),
            len(records),
        )
    )
    return "\n".join(lines) + "\n"


def render_json(records, today, within, show_all, expired_only):
    """Render the machine-readable report as a JSON string."""
    buckets = partition(records, today, within)
    if show_all:
        shown = sort_records(records)
    elif expired_only:
        shown = buckets["expired"]
    else:
        shown = buckets["expired"] + buckets["expiring_soon"]
    shown = sort_records(shown)
    payload = {
        "tool": "doc-expiry-doctor",
        "version": __version__,
        "today": today.isoformat(),
        "within_days": within,
        "counts": {
            "expired": len(buckets["expired"]),
            "expiring_soon": len(buckets["expiring_soon"]),
            "later": len(buckets["later"]),
            "total": len(records),
        },
        "records": [
            record_view(record, today, within) for record in shown
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_check_text(path, records, errors):
    """Render the --check validation report."""
    lines = [
        "doc-expiry-doctor %s | check: %s" % (__version__, path),
        "",
    ]
    if not errors:
        lines.append("OK: %d valid record(s), no errors." % len(records))
    else:
        lines.append("ERRORS (%d):" % len(errors))
        for error in errors:
            lines.append("  %s" % error)
        lines.append("")
        lines.append(
            "%d valid record(s), %d invalid record(s)."
            % (len(records), len(errors))
        )
    return "\n".join(lines) + "\n"


def build_parser():
    parser = argparse.ArgumentParser(
        prog="doc-expiry-doctor",
        description=(
            "Track document expiries from a JSON file: CDLs, medical "
            "cards, insurance, registrations, and more."
        ),
    )
    parser.add_argument("file", help="JSON documents file to read")
    parser.add_argument(
        "--within",
        type=int,
        default=30,
        metavar="N",
        help="expiring-soon window in days (default: 30)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--all",
        action="store_true",
        help="show the full list, sorted by expiry date",
    )
    group.add_argument(
        "--expired",
        action="store_true",
        help="show only already-expired documents",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON instead of text",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "validate dates and required fields only; "
            "exit non-zero on bad records"
        ),
    )
    parser.add_argument(
        "--type",
        action="append",
        default=[],
        metavar="TYPE",
        help="only show this document type (repeatable, case-insensitive)",
    )
    parser.add_argument(
        "--holder",
        action="append",
        default=[],
        metavar="NAME",
        help="only show holders matching this text (repeatable, substring)",
    )
    parser.add_argument(
        "--today",
        default=None,
        metavar="YYYY-MM-DD",
        help="treat this date as today (default: real today; for tests)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="doc-expiry-doctor %s" % __version__,
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.within < 0:
        parser.error("--within must not be negative")
    if args.today is None:
        today = date.today()
    else:
        try:
            today = parse_date(args.today)
        except ValueError as exc:
            parser.error("--today: %s" % exc)
    try:
        records, errors = load_documents(args.file)
    except ValueError as exc:
        print("doc-expiry-doctor: error: %s" % exc, file=sys.stderr)
        return 2
    if args.check:
        if args.json:
            payload = {
                "tool": "doc-expiry-doctor",
                "version": __version__,
                "file": args.file,
                "valid": not errors,
                "valid_records": len(records),
                "errors": errors,
            }
            print(json.dumps(payload, indent=2))
        else:
            print(render_check_text(args.file, records, errors), end="")
        return 2 if errors else 0
    if errors:
        print(
            "doc-expiry-doctor: error: %d invalid record(s) in %s:"
            % (len(errors), args.file),
            file=sys.stderr,
        )
        for error in errors:
            print("  %s" % error, file=sys.stderr)
        print(
            "Fix the file or run with --check to see all errors.",
            file=sys.stderr,
        )
        return 2
    records = apply_filters(records, args.type, args.holder)
    if args.json:
        print(
            render_json(
                records, today, args.within, args.all, args.expired
            ),
            end="",
        )
    else:
        print(
            render_text(
                records,
                today,
                args.within,
                args.file,
                args.all,
                args.expired,
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
