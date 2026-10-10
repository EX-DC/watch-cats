# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-10-08
### Added
- `python -m watchcats serve`: live, read-only API with a 1 second refresh.
  - `GET /api/live` (snapshot), `GET /api/stream` (Server-Sent Events), `GET /api/summary?hours=N`, `GET /api/errors?kind=...`, `GET /api/version`, `GET /api/health`.
- Server metrics read from `/proc` and `/sys`: CPU, RAM, network speed (rx/tx and link speed), disk usage and disk I/O, cache folder size (refreshed in the background).
- Live per-service and per-client speeds from a 10 second sliding window (estimates, because nginx logs a request when it finishes).
- Xbox traffic is split between console and Windows when the device type is known.
- Access control: only private networks are accepted by default (`--allow private|any|CIDR,...`). There is no login yet.
- Old data is purged automatically (default 30 days).

### Changed
- `Storage` can be opened read-only for the API (`init=False`).
- Cache folder size is `null` (with `cache_unreadable` > 0) when some files cannot be read, instead of a misleading partial number.

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
