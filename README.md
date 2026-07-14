# biobank

A lightweight **biobank management system** for tracking donors and their
biological samples. Written in pure Python — **no third-party dependencies**
(standard library `sqlite3` + `http.server` only), so it runs on any stock
Python 3.9+ install.

## Features

- Register **donors** (code, name, birth year, sex) with validation.
- Collect **samples** per donor (type, volume, storage temperature, location).
- Track sample **lifecycle**: `stored → in_use → depleted / discarded`.
- Cascade delete: removing a donor removes their samples.
- **JSON REST API** + a self-contained **web UI** (single HTML page, no build step).
- Live **stats** dashboard (counts by status and type).

## Quick start

```bash
# Start the server (defaults to http://127.0.0.1:8000)
python3 -m biobank.server
```

Then open <http://127.0.0.1:8000> in a browser, or use the API directly:

```bash
# Register a donor
curl -X POST http://127.0.0.1:8000/api/donors \
  -d '{"code":"D-001","full_name":"Sara Ali","sex":"F","birth_year":1988}'

# Collect a sample
curl -X POST http://127.0.0.1:8000/api/samples \
  -d '{"donor_id":1,"sample_type":"blood","volume_ml":5,"storage_temp":-80,"location":"Freezer-A1"}'

# Move it into use
curl -X PATCH http://127.0.0.1:8000/api/samples/1 -d '{"status":"in_use"}'

# Overview
curl http://127.0.0.1:8000/api/stats
```

### Configuration

| Variable        | Default        | Description                     |
| --------------- | -------------- | ------------------------------- |
| `BIOBANK_DB`    | `biobank.db`   | Path to the SQLite database.    |
| `BIOBANK_PORT`  | `8000`         | Port to listen on.              |
| `BIOBANK_VERBOSE` | *(unset)*    | Set to enable request logging.  |

## API reference

| Method   | Path                     | Description                        |
| -------- | ------------------------ | ---------------------------------- |
| `GET`    | `/api/health`            | Health check.                      |
| `GET`    | `/api/stats`             | Aggregate counts.                  |
| `GET`    | `/api/donors`            | List donors.                       |
| `POST`   | `/api/donors`            | Create a donor.                    |
| `GET`    | `/api/donors/{id}`       | Get one donor.                     |
| `DELETE` | `/api/donors/{id}`       | Delete a donor (and its samples).  |
| `GET`    | `/api/samples`           | List samples (`?donor_id=`, `?status=`). |
| `POST`   | `/api/samples`           | Create a sample.                   |
| `PATCH`  | `/api/samples/{id}`      | Update a sample's status.          |
| `DELETE` | `/api/samples/{id}`      | Delete a sample.                   |

## Project layout

```
biobank/
  __init__.py     package metadata
  db.py           SQLite data layer (donors, samples, stats)
  server.py       HTTP server: JSON API + web UI
tests/
  test_biobank.py end-to-end tests (DB layer + live HTTP API)
```

## Running the tests

```bash
python3 -m unittest discover -s tests -v
```
