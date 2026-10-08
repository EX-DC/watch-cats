# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-08
### Added
- Log parsers for LanCache `access.log`, `stream-access.log`, `error.log` and BIND `default.log` (request paths and tokens are never stored).
- Incremental log reader that resumes after restarts and survives log rotation.
- Hostname to service mapping from the `cache-domains` lists (wildcards supported).
- Automatic device detection from User-Agent (PS5, PS4, Windows, PC; Xbox console rule is unverified).
- SQLite storage with per-minute aggregation, atomic writes and retention purge.
- CLI: `python -m watchcats ingest` and `python -m watchcats report`.
- 22 unit tests using real, sanitized log lines.

## [0.1.0] - 2026-10-07
### Added
- Project skeleton: README, MIT license, CONTRIBUTING, version plumbing, CI.
- `design/`: reference copy of the approved dashboard mockup.
- `tools/windows/epic-http-fix.ps1`: helper that makes Epic Games Launcher use HTTP so LanCache can cache it (not tested on real Windows yet).
