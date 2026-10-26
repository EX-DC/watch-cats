# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.3] - 2026-10-24
### Fixed
- Logos that carry their own colours or a background (for example files downloaded from a website) were turned into a white square by the white-recolouring filter. Only plain one-colour icons are recoloured now; the others are shown as they are on a light badge. `GET /api/logos` reports `mono` for each file.
- Logo file names with capital letters (for example `Nintendo.svg`) are accepted.
- RAM is written as "used از total" so it cannot be read backwards in right-to-left text.

### Added
- Service logos in the clients table (`top_service_key` in `/api/summary`) and logos for the Windows, PlayStation and Xbox devices.

## [0.4.2] - 2026-10-18
### Added
- Service logos: the dashboard shows an image instead of the letters for every service that has a file in `src/watchcats/web/logos/<key>.svg|png|webp` (letters remain the fallback).
  - `python -m watchcats install-logos --from <folder>` copies logos from a Simple Icons folder (rejects files that contain scripts).
  - `GET /api/logos` lists the available logos; files are served with a strict file-name pattern and a sandboxing Content-Security-Policy.
- `HEAD` requests are supported (for example `curl -I`).

### Notes
- Logo and font files are not stored in git (`.gitignore`). Logos belong to their owners and are only used to identify each service.

## [0.4.1] - 2026-10-13
### Fixed
- HIT/MISS gauges: a first download from the internet no longer shows up as "served from cache". A cache MISS is proxied (it is counted in both the NIC's rx and tx), so the cache-serve speed is now `tx - rx` and the download speed is `rx`.
- Error buttons were drawn with black text on a dark background and are readable now.
- Numbers with units are displayed in the right order inside right-to-left text.
- "Clients receiving" now counts every active client and says whether each one is served from the cache or downloading from the internet (amber).
- The 60-second chart no longer draws a line before the page was opened.

### Changed
- Both charts show MISS as amber columns and HIT as a green line on the same axis (they are no longer stacked). The 24-hour chart has a linear/logarithmic switch so small hours stay visible.
- Clients table: "live" with a blinking green dot for recent activity, and a relative time plus date and clock for older activity. Error groups show date and clock too.
- Lighter font weights and a better Persian font stack.

### Added
- `python -m watchcats install-font` downloads the Vazirmatn font (optional, not stored in git).
- More error kinds (`upstream_unavailable`, `upstream_connect_failed`, `upstream_closed`, `upstream_reset`, `upstream_ssl`) and readable names for `upstream_<status>`.
- Heuristic (unverified): an unrecognised client that downloads from the Xbox CDN list is shown as an Xbox console.

## [0.4.0] - 2026-10-10
### Added
- Web dashboard served by the app itself at `/` (dark, Persian right-to-left, no build step, no external resources).
  - Live gauges (5 second average plus the instant value), clients receiving from the cache, per-service cards with fill/serve bars, server resources, KPIs, 24-hour chart, 60-second chart, clients table and clickable error logs.
- Each client row shows its main service (`top_service` in `/api/summary`).
- The server's own addresses are hidden from clients and live data (`--show-server-ip` to keep them).
- Security headers on pages (Content-Security-Policy, nosniff) and a whitelist of served files.
- Front-end unit tests (Node.js `node --test`) and a CI step that runs them.

### Notes
- Alerts shown in the page are real (disk 90%, connection, log reading); DNS, container and Telegram alerts arrive in 0.5.0.
- The 60-second chart fills from the moment the page is opened.

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
