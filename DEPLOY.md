# Deploying Biobank to a server

Biobank is a pure-Python app (no third-party packages) that stores everything in
a single SQLite file. Two supported ways to run it in production, both serving
over **HTTPS** so login cookies are protected.

Choosing an option:

- **No budget / no credit card?** Use **Option C — PythonAnywhere free tier**. It
  gives you a free `*.pythonanywhere.com` address with HTTPS already set up, keeps
  your data on persistent storage, and needs no payment card or domain.
- Have a server (or a few dollars for a small VPS) and want your own domain? Use
  **Option A** (Docker) or **Option B** (systemd).

Options A and B need:

- A server/VPS with a public IP (any small instance is plenty).
- A **domain name** (or subdomain) with a DNS `A` record pointing at the server.
- Ports **80** and **443** open in the firewall.

---

## Option A — Docker Compose with automatic HTTPS (recommended)

This runs the app plus [Caddy](https://caddyserver.com), which obtains and renews
a free Let's Encrypt TLS certificate for your domain automatically.

1. Install Docker (includes Compose): <https://docs.docker.com/engine/install/>.

2. Copy the project to the server and enter it:

   ```bash
   git clone https://github.com/Amer-omran/biobank.git
   cd biobank
   git checkout claude/try-now-5sg4z8      # omit once merged into main
   ```

3. Point your domain's DNS `A` record at the server's IP, then start it:

   ```bash
   export SITE_ADDRESS=biobank.example.com          # your domain
   export BIOBANK_SEED_PASSWORD='a-strong-first-run-password'
   docker compose up -d --build
   ```

4. Open `https://biobank.example.com` and sign in as `admin1` (or `user1`) with
   the seed password. **Change every password** from the "My account" panel, and
   remove or rotate the seed accounts you don't need.

Useful commands:

```bash
docker compose logs -f biobank     # view logs
docker compose down                # stop (data is kept in the volume)
docker compose pull && docker compose up -d --build   # update after a git pull
```

Your data lives in the `biobank-data` Docker volume. Back it up with:

```bash
docker run --rm -v biobank_biobank-data:/data -v "$PWD":/backup alpine \
  cp /data/biobank.db /backup/biobank-backup.db
```

---

## Option B — Plain VPS with systemd + a reverse proxy

Use this if you prefer not to run Docker.

1. Install Python 3.9+ (`sudo apt install python3`), then place the code and a
   service account:

   ```bash
   sudo useradd --system --home /opt/biobank --shell /usr/sbin/nologin biobank
   sudo mkdir -p /opt/biobank /var/lib/biobank
   sudo cp -r biobank /opt/biobank/biobank
   sudo chown -R biobank:biobank /opt/biobank /var/lib/biobank
   ```

2. Install the service unit, set a seed password inside it, and start it:

   ```bash
   sudo cp deploy/biobank.service /etc/systemd/system/
   sudoedit /etc/systemd/system/biobank.service   # set BIOBANK_SEED_PASSWORD
   sudo systemctl daemon-reload
   sudo systemctl enable --now biobank
   sudo systemctl status biobank
   ```

   The app now listens on `127.0.0.1:8000` (not exposed to the internet yet).

3. Put a reverse proxy in front for HTTPS. Easiest is Caddy:

   ```bash
   sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
   # (follow https://caddyserver.com/docs/install for the apt repo, then)
   echo 'biobank.example.com {
       reverse_proxy 127.0.0.1:8000
   }' | sudo tee /etc/caddy/Caddyfile
   sudo systemctl restart caddy
   ```

   Or use nginx + certbot if you already run nginx — proxy `/` to
   `http://127.0.0.1:8000` and obtain a certificate with
   `sudo certbot --nginx -d biobank.example.com`.

4. Open `https://biobank.example.com`, sign in, and change the passwords.

Back up the database file directly:

```bash
sudo cp /var/lib/biobank/biobank.db /root/biobank-backup-$(date +%F).db
```

---

## Option C — PythonAnywhere free tier (free, no credit card, HTTPS included)

Best when you have **no budget**. The free "Beginner" account needs no payment
card, gives you `https://YOURNAME.pythonanywhere.com`, and stores files
persistently (so your SQLite database survives restarts). It runs the app through
the included WSGI adapter (`biobank/wsgi.py`).

1. Create a free account at <https://www.pythonanywhere.com> (choose the free
   "Beginner" plan).

2. Open a **Bash console** (Consoles tab) and fetch the code:

   ```bash
   git clone https://github.com/Amer-omran/biobank.git
   cd biobank && git checkout claude/try-now-5sg4z8      # omit once merged into main
   ```

3. Go to the **Web** tab → **Add a new web app** → **Manual configuration** →
   pick the latest **Python 3.x**. (Free apps live at `YOURNAME.pythonanywhere.com`.)

4. In the Web tab, click the **WSGI configuration file** link, **delete all of its
   contents**, and paste exactly this (only change the password). Keep the
   `import os, sys` line — the app needs it:

   ```python
   import os, sys

   # Project folder inside your home directory (handles username casing for you).
   project = os.path.join(os.path.expanduser("~"), "biobank")
   if project not in sys.path:
       sys.path.insert(0, project)

   os.environ["BIOBANK_DB"] = os.path.join(project, "biobank.db")
   os.environ["BIOBANK_SEED_PASSWORD"] = "a-strong-first-run-password"
   os.environ["BIOBANK_SECURE_COOKIE"] = "1"

   from biobank.wsgi import application
   ```

   > Using `os.path.expanduser("~")` avoids hardcoding your username, so it works
   > regardless of letter case. If you see `NameError: name 'sys' is not defined`,
   > the `import os, sys` line at the top is missing — paste the whole block again.

5. (Optional, faster static files) In the Web tab's **Static files** section add:
   URL `/static/` → Directory `/home/YOURNAME/biobank/biobank/static/`.

6. Click the big green **Reload** button, then open
   `https://YOURNAME.pythonanywhere.com` and sign in as `admin1` with the seed
   password. **Change all passwords** from the "My account" panel.

7. *(Optional)* To enable the auto-filled **Word storage-request form**: upload
   your `.docx` template via the **Files** tab to a folder outside the repo (e.g.
   `/home/YOURNAME/biobank-form/storage_request_form.docx` so `git pull` never
   touches it), then add this line to the WSGI file and **Reload**:

   ```python
   os.environ["BIOBANK_FORM_TEMPLATE"] = "/home/YOURNAME/biobank-form/storage_request_form.docx"
   ```

Notes for the free tier:

- HTTPS is already configured on the `pythonanywhere.com` address — nothing to set up.
- Your data is the file `/home/YOURNAME/biobank/biobank.db`; download it from the
  **Files** tab to back up.
- Free web apps ask you to click a "Run until 3 months from now" button every three
  months to stay active — just log in and click it.
- After pulling code updates (`git pull`), hit **Reload** in the Web tab.

Truly free alternative with more power (but a credit card is required at signup):
**Oracle Cloud "Always Free"** gives a small VM forever — then follow Option A or B
on it.

## Configuration reference

| Variable                | Purpose                                                        |
| ----------------------- | ------------------------------------------------------------- |
| `BIOBANK_HOST`          | Bind address. `0.0.0.0` in containers; `127.0.0.1` behind a proxy. |
| `BIOBANK_PORT`          | Listen port (default `8000`).                                 |
| `BIOBANK_DB`            | SQLite file path (put it on a persistent volume).             |
| `BIOBANK_SEED_PASSWORD` | Password for the six seeded accounts — used only on first run. |
| `BIOBANK_SECURE_COOKIE` | `1` to add the `Secure` flag so cookies require HTTPS. Set behind TLS. |
| `BIOBANK_FORM_TEMPLATE`  | Path to your Word storage-request form (`.docx`). Set it to enable the per-sample "Storage form (Word)" download; leave unset to disable it. The template is not bundled — keep it outside the repo. |

## Post-deployment checklist

- [ ] Change all seeded passwords; remove accounts you don't need.
- [ ] Confirm the site loads over `https://` (not `http://`).
- [ ] `BIOBANK_SECURE_COOKIE=1` is set (both options above do this).
- [ ] Schedule a backup of the SQLite database.
- [ ] Restrict who can reach ports 80/443 if this is internal-only.
