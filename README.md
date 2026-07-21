# biobank

A **biobank management system** for tracking animal biological samples, with
user accounts and role-based access control. Written in pure Python — **no
third-party dependencies** (standard library only: `sqlite3` + `http.server`) —
so it runs on any stock Python 3.9+ install.

## Features

- **Sample registry** matching a real lab data form: lab/sample numbers, storage
  date, storage method (`-20 / -80 / -190 °C`), physical location (freezer, shelf,
  plate), area, animal type, sample type, quantity, concentration, disease, strain,
  department and barcode.
- **Ready-made option lists** for area, animal type, sample type, disease, strain
  and department — pick a value or type a new one.
- **Accounts & roles**, enforced on the server:
  - **admin** (`admin1`, `admin2`) — full access: all fields, delete, import, and
    user management (add/remove accounts, assign roles).
  - **staff** (`user1`–`user4`) — view everything and create records, **except** the
    barcode, freezer, shelf and plate fields (stripped server-side on write); no
    delete, no import.
- **Cookie-based auth** with salted **PBKDF2-SHA256** password hashes and expiring
  server-side sessions.
- **Excel/CSV import** (admin only) — reads native `.xlsx` (via stdlib `zipfile` +
  `xml.etree`) and CSV, auto-detects the header row beneath title rows, converts
  Excel date serials, and maps many column-name spellings.
- **Edit and delete** records (staff edits leave the restricted fields intact),
  **CSV export** of the current view, and **self-service password change**.
- **Sample reception form (PDF)** auto-filled from each record — offered right
  after a sample is saved and from a per-row button (generated with the standard
  library, no PDF packages).
- **Your own Word form, auto-filled**: point `BIOBANK_FORM_TEMPLATE` at a `.docx`
  storage-request form and each sample can be downloaded as that exact form with
  its fields populated (stdlib `zipfile`/`xml`, template kept out of the repo).
- **Admin-only** (admin1/admin2): an **audit log** recording every create, edit,
  delete, import and export, plus native **Excel (`.xlsx`) export** of the current
  view (written with the standard library — no third-party packages).
- **JSON REST API** plus a single-page **web UI** (login screen, live stats, search
  and department filter), light/dark themed.

## Quick start

```bash
# First run seeds the six accounts. Choose the seed password up front:
BIOBANK_SEED_PASSWORD='ChooseAStrongOne' python3 -m biobank.server
# → serves http://127.0.0.1:8000  (the password is printed once on first run)
```

Open <http://127.0.0.1:8000>, sign in as `admin1` (full access) or `user1`
(data entry).

### Configuration

| Variable                | Default        | Description                                  |
| ----------------------- | -------------- | -------------------------------------------- |
| `BIOBANK_HOST`          | `127.0.0.1`    | Bind address (`0.0.0.0` to accept remote connections). |
| `BIOBANK_PORT`          | `8000`         | Port to listen on.                           |
| `BIOBANK_DB`            | `biobank.db`   | SQLite database path.                        |
| `BIOBANK_SEED_PASSWORD` | `ChangeMe@123` | Password for the six accounts, seeded once.  |
| `BIOBANK_SECURE_COOKIE` | *(unset)*      | Set to `1` behind HTTPS to add the `Secure` cookie flag. |
| `BIOBANK_VERBOSE`       | *(unset)*      | Set to enable HTTP request logging.          |

## Deploying to a server

To run Biobank on a server for your team (with HTTPS), see **[DEPLOY.md](DEPLOY.md)**.
It covers three paths:

- **Free, no credit card:** the **PythonAnywhere** free tier via the included WSGI
  adapter (`biobank/wsgi.py`) — a free HTTPS address with persistent storage.
- **Docker Compose** with automatic Let's Encrypt certificates (`Dockerfile`,
  `docker-compose.yml`, `Caddyfile`).
- **systemd** on a plain VPS behind a reverse proxy (`deploy/biobank.service`).

Accounts are seeded only when the database has no users. Change the seed password
before first run, or manage users directly in the database.

## API reference

All `/api` routes except `/health` and `/login` require the session cookie set by
`POST /api/login`.

| Method   | Path                  | Role   | Description                              |
| -------- | --------------------- | ------ | ---------------------------------------- |
| `POST`   | `/api/login`          | any    | Sign in; sets the session cookie.        |
| `POST`   | `/api/logout`         | auth   | Invalidate the session.                  |
| `GET`    | `/api/me`             | auth   | Current user + role.                     |
| `GET`    | `/api/options`        | auth   | Option lists, fields, restricted fields. |
| `GET`    | `/api/samples`        | auth   | List samples (`?department=`, `?search=`).|
| `POST`   | `/api/samples`        | auth   | Create a sample (staff: restricted fields ignored). |
| `PATCH`  | `/api/samples/{id}`   | auth   | Edit a sample (staff: restricted fields left intact). |
| `GET`    | `/api/samples/{id}/receipt.pdf` | auth | Reception form PDF for a sample.       |
| `GET`    | `/api/samples/{id}/form.docx`   | auth | Your Word form filled for a sample (needs `BIOBANK_FORM_TEMPLATE`). |
| `DELETE` | `/api/samples/{id}`   | admin  | Delete a sample.                         |
| `POST`   | `/api/change-password`| auth   | Change your own password.                |
| `POST`   | `/api/import`         | admin  | Import `.xlsx`/`.csv` (`?filename=`).    |
| `GET`    | `/api/export.xlsx`    | admin  | Export the current view as `.xlsx` (`?department=`, `?search=`). |
| `GET`    | `/api/audit`          | admin  | Recent audit-log events.                 |
| `GET`    | `/api/users`          | admin  | List user accounts.                      |
| `POST`   | `/api/users`          | admin  | Create an account (username, name, role, password). |
| `DELETE` | `/api/users/{id}`     | admin  | Delete an account (not self / last admin). |
| `GET`    | `/api/health`         | public | Health check.                            |

## Project layout

```
biobank/
  __init__.py       package metadata
  options.py        schema, option lists, import aliases
  db.py             SQLite layer: users, sessions, samples, stats
  importer.py       CSV + native .xlsx parsing (stdlib only)
  exporter.py       native .xlsx writing (stdlib only)
  pdf.py            sample reception form PDF writer (stdlib only)
  docx_form.py      fills an external Word storage-request form (stdlib only)
  server.py         HTTP server: auth, RBAC, audit log, API, static files
  wsgi.py           WSGI adapter (for hosts like PythonAnywhere)
  static/
    index.html      single-page web UI
    app.js          UI logic (talks to the REST API)
tests/
  test_biobank.py   DB, importer and HTTP/RBAC tests
```

## Running the tests

```bash
python3 -m unittest discover -s tests -v
```

## Security notes

Passwords are stored only as salted PBKDF2-SHA256 hashes; sessions are opaque
random tokens with an 8-hour expiry, delivered as `HttpOnly`, `SameSite=Lax`
cookies. Role restrictions are enforced in the server, not the browser. For a
public deployment, run behind HTTPS (add the `Secure` cookie flag) and set a
strong `BIOBANK_SEED_PASSWORD`.
