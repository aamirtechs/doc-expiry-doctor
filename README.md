# doc-expiry-doctor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/aamirtechs/doc-expiry-doctor/blob/main/LICENSE) [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/aamirtechs/doc-expiry-doctor/issues)

A zero-dependency Python CLI that tracks document expiries from a JSON
file: CDLs, medical cards, insurance, registrations, and anything else
with an expiry date. It tells you what is already expired, what expires
soon, and what is still fine, sorted by expiry date.

An expired CDL or medical card can park a truck and a driver. This tool
is the smallest possible safety net for that: one JSON file, one
command, run it every morning or in CI, and nothing slips past quietly.

## Install

Requires Python 3.9 or newer. No dependencies beyond the standard library.

```bash
pip install doc-expiry-doctor
```

Or run it straight from the source checkout:

```bash
python3 doc_expiry_doctor.py examples/documents.json
```

## Input format

A JSON list, or an object with a `documents` list. Each record needs
`holder`, `type`, and `expiry` (ISO format `YYYY-MM-DD`). `reminder_days`
is optional: a per-record reminder window that overrides `--within` for
that record. `document_type` and `expiry_date` are accepted as aliases
for `type` and `expiry`.

```json
[
  {"holder": "Maria Lopez", "type": "CDL", "expiry": "2026-11-20"},
  {"holder": "Sam Ortiz", "type": "CDL", "expiry": "2026-12-20",
   "reminder_days": 60}
]
```

The sample file in `examples/documents.json` holds 7 records for 4
holders. The examples below use `--today 2026-11-02` so the output is
reproducible; in real use, leave it out and the tool uses today.

## Usage

Default report: already-expired documents plus everything expiring
within 30 days (Sam Ortiz appears here even though his CDL is 48 days
out, because his own `reminder_days` of 60 overrides the 30 day window):

```bash
python3 doc_expiry_doctor.py examples/documents.json --today 2026-11-02
```

Captured output:

```
doc-expiry-doctor 1.0.0 | today 2026-11-02 | within 30 days
input: examples/documents.json (7 records)

Already expired (1):
  EXPIRED       2026-10-15  James Carter  CDL  (18 days ago)

Expiring within 30 days (3):
  EXPIRING SOON 2026-11-02  Priya Patel  Registration  (expires today)
  EXPIRING SOON 2026-11-20  Maria Lopez  CDL  (in 18 days)
  EXPIRING SOON 2026-12-20  Sam Ortiz  CDL  (in 48 days)  [reminder 60 days]

Summary: 1 expired, 3 expiring soon, 3 later, 7 total
```

Widen the window to 60 or 90 days:

```bash
python3 doc_expiry_doctor.py examples/documents.json --today 2026-11-02 --within 60
```

Captured output:

```
doc-expiry-doctor 1.0.0 | today 2026-11-02 | within 60 days
input: examples/documents.json (7 records)

Already expired (1):
  EXPIRED       2026-10-15  James Carter  CDL  (18 days ago)

Expiring within 60 days (4):
  EXPIRING SOON 2026-11-02  Priya Patel  Registration  (expires today)
  EXPIRING SOON 2026-11-20  Maria Lopez  CDL  (in 18 days)
  EXPIRING SOON 2026-12-15  Maria Lopez  Medical card  (in 43 days)
  EXPIRING SOON 2026-12-20  Sam Ortiz  CDL  (in 48 days)  [reminder 60 days]

Summary: 1 expired, 4 expiring soon, 2 later, 7 total
```

With `--within 90`, the insurance record expiring 2027-01-30 (in 89 days)
joins the list, for 5 expiring soon.

Full sorted list, already-expired section on its own, and filters:

```bash
python3 doc_expiry_doctor.py examples/documents.json --today 2026-11-02 --all
python3 doc_expiry_doctor.py examples/documents.json --today 2026-11-02 --expired
python3 doc_expiry_doctor.py examples/documents.json --today 2026-11-02 --all --type CDL
python3 doc_expiry_doctor.py examples/documents.json --today 2026-11-02 --all --holder priya
```

Captured output of `--all`:

```
doc-expiry-doctor 1.0.0 | today 2026-11-02 | within 30 days
input: examples/documents.json (7 records)

All documents, sorted by expiry (7):

  EXPIRED       2026-10-15  James Carter  CDL  (18 days ago)
  EXPIRING SOON 2026-11-02  Priya Patel  Registration  (expires today)
  EXPIRING SOON 2026-11-20  Maria Lopez  CDL  (in 18 days)
  LATER         2026-12-15  Maria Lopez  Medical card  (in 43 days)
  EXPIRING SOON 2026-12-20  Sam Ortiz  CDL  (in 48 days)
  LATER         2027-01-30  James Carter  Insurance  (in 89 days)
  LATER         2027-03-01  Priya Patel  Medical card  (in 119 days)

Summary: 1 expired, 3 expiring soon, 3 later, 7 total
```

Captured output of `--all --type CDL` (3 records, the other types drop out):

```
doc-expiry-doctor 1.0.0 | today 2026-11-02 | within 30 days
input: examples/documents.json (3 records)

All documents, sorted by expiry (3):

  EXPIRED       2026-10-15  James Carter  CDL  (18 days ago)
  EXPIRING SOON 2026-11-20  Maria Lopez  CDL  (in 18 days)
  EXPIRING SOON 2026-12-20  Sam Ortiz  CDL  (in 48 days)

Summary: 1 expired, 2 expiring soon, 0 later, 3 total
```

`--type` matches exactly (case-insensitive) and is repeatable.
`--holder` matches as a case-insensitive substring and is repeatable.
The two filters combine: a record must pass both to be shown.

## Machine-readable output

```bash
python3 doc_expiry_doctor.py examples/documents.json --today 2026-11-02 --json
```

Captured output:

```json
{
  "tool": "doc-expiry-doctor",
  "version": "1.0.0",
  "today": "2026-11-02",
  "within_days": 30,
  "counts": {
    "expired": 1,
    "expiring_soon": 3,
    "later": 3,
    "total": 7
  },
  "records": [
    {
      "holder": "James Carter",
      "type": "CDL",
      "expiry": "2026-10-15",
      "reminder_days": null,
      "status": "expired",
      "days_until": -18
    },
    {
      "holder": "Priya Patel",
      "type": "Registration",
      "expiry": "2026-11-02",
      "reminder_days": null,
      "status": "expiring_soon",
      "days_until": 0
    },
    {
      "holder": "Maria Lopez",
      "type": "CDL",
      "expiry": "2026-11-20",
      "reminder_days": null,
      "status": "expiring_soon",
      "days_until": 18
    },
    {
      "holder": "Sam Ortiz",
      "type": "CDL",
      "expiry": "2026-12-20",
      "reminder_days": 60,
      "status": "expiring_soon",
      "days_until": 48
    }
  ]
}
```

`counts` always describe the filtered set; `records` holds only the
records shown in the current mode (expired plus expiring soon by
default, everything with `--all`, only expired with `--expired`).

## Validation with --check

`--check` validates dates and required fields and nothing else. It
exits 0 when the file is clean and 2 when any record is bad, so it
works as a CI gate on the documents file itself:

```bash
python3 doc_expiry_doctor.py examples/documents.json --check
```

Captured output (exit code 0):

```
doc-expiry-doctor 1.0.0 | check: examples/documents.json

OK: 7 valid record(s), no errors.
```

The bad sample in `examples/bad-documents.json` has an impossible date,
a missing holder, and a non-ISO date:

```bash
python3 doc_expiry_doctor.py examples/bad-documents.json --check
```

Captured output (exit code 2):

```
doc-expiry-doctor 1.0.0 | check: examples/bad-documents.json

ERRORS (3):
  record 2: invalid 'expiry': not a real calendar date: '2026-02-30'
  record 3: missing or empty required field 'holder'
  record 4: invalid 'expiry': not an ISO date (expected YYYY-MM-DD): '20 Nov 2026'

1 valid record(s), 3 invalid record(s).
```

Without `--check`, a file with bad records is also rejected with exit
code 2 and the same per-record errors on stderr. Invalid dates are
never silently skipped: a typo like `2026-02-30` must be fixed, not
ignored, because a silently skipped CDL is exactly how a truck gets
parked.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (a report listing expired documents still exits 0) |
| 2 | Usage error, unreadable or invalid JSON, or invalid records |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

45 tests, covering strict ISO date parsing, record validation and
aliases, reminder window overrides, window boundaries, filters,
sorting, every CLI mode, exit codes, and an em dash scan of the repo
text files.

## Contributing

See [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md) for small, well-scoped
tasks. Comment on an issue before starting so two people do not pick
up the same one.

## License

MIT. See [LICENSE](LICENSE).
