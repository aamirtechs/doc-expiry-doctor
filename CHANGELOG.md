# Changelog

All notable changes to this project will be documented in this file.
The format is based on Keep a Changelog, and this project adheres to
Semantic Versioning.

## [1.0.0] - 2026-11-02

### Added
- JSON documents input: a list, or an object with a "documents" list.
  Each record has holder, type, and expiry (strict ISO YYYY-MM-DD),
  plus optional reminder_days. "document_type" and "expiry_date" are
  accepted as aliases.
- Default report: already-expired section plus documents expiring
  within N days via --within (default 30). --all shows the full list
  sorted by expiry date; --expired shows only expired documents.
- Per-record reminder_days overrides the global --within window for
  that record, and is flagged in text output.
- Filters: --type (exact, case-insensitive, repeatable) and --holder
  (case-insensitive substring, repeatable); the two combine with AND.
- --json machine-readable report with counts (expired, expiring_soon,
  later, total) and per-record status and days_until.
- --check validation mode: validates dates and required fields, exits
  0 when clean and 2 on any bad record. Normal modes also reject a
  file with bad records with exit code 2 instead of skipping them.
- --today override for reproducible reports and tests.
- Exit codes: 0 success, 2 usage, input, or validation error.
- 45-test suite covering strict date parsing, validation and aliases,
  reminder overrides, window boundaries, filters, sorting, every CLI
  mode, exit codes, and an em dash scan of repo text.
