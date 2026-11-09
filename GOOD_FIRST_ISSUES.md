# Good first issues

Small, well-scoped tasks for new contributors. Each one can be done in a
single pull request. Comment on the issue before starting so two people do
not pick up the same one.

## 1. Add a --fail-on-expired gate for CI

**What:** Today a report that lists expired documents still exits 0.
Add a `--fail-on-expired` flag: when any record is expired, exit 1
after printing the normal report. It must work in text and `--json`
mode, and must not change the exit code when nothing is expired. Add
tests for both cases and document the flag in the README exit code
table.

**Why:** A morning report a human reads is one thing; a scheduled job
that should page someone is another. Teams want the same tool to act
as a gate in CI without parsing its output.

**Files:** `doc_expiry_doctor.py` (`main`, `build_parser`), `README.md`,
`tests/`.

## 2. Support CSV input alongside JSON

**What:** Add a `--format csv` option (auto-detect by `.csv` file
extension when no format is given). Columns: holder, type, expiry,
reminder_days (optional, may be empty). Reuse the existing
`normalize_record` validation so CSV rows get the same error messages
and the same `--check` behavior. Add a sample CSV under `examples/`
and tests for a valid file, a bad date row, and a missing column.

**Why:** The people who track driver documents usually live in
spreadsheets, not JSON. CSV input removes the conversion step that
keeps them from adopting the tool.

**Files:** `doc_expiry_doctor.py` (`load_documents`), `examples/`,
`README.md`, `tests/`.

## 3. Add an --urgency sort that puts expired first, then soonest

**What:** Today `--all` sorts strictly by expiry date, which already
puts expired records first. Add an `--urgency` flag that changes the
sort to: expired first (most overdue first), then expiring soon
(soonest first), then later (soonest first). Keep the default sort
unchanged. Add tests proving the ordering with a mixed fixture.

**Why:** For a dispatcher triaging a fleet at 7am, "most overdue
first" reads faster than a pure date sort when the list mixes expired
and soon-to-expire documents across many drivers.

**Files:** `doc_expiry_doctor.py` (`sort_records`, `render_text`,
`render_json`), `README.md`, `tests/`.

## 4. Warn on duplicate holder plus type records

**What:** In `--check` mode, and as a warning line in normal reports,
flag records that share the same holder and type (case-insensitive)
but have different expiry dates, for example two CDL rows for one
driver. Print each duplicate group once, with both expiry dates, and
keep the exit code unchanged: this is a warning, not an error. Add
tests for a duplicate pair, for same holder with different types
(no warning), and for exact duplicate rows.

**Why:** Duplicate rows usually mean someone re-entered a renewal
without deleting the old row, and the stale row then looks like an
expired document. A warning catches the data entry mistake before it
causes a false alarm.

**Files:** `doc_expiry_doctor.py` (`load_documents` or a new
`find_duplicates` helper, `render_check_text`, `render_text`),
`README.md`, `tests/`.
