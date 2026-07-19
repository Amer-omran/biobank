"""End-to-end tests for the biobank system.

Covers the database layer, the importer, and the HTTP API (auth + RBAC)
against a live server bound to an ephemeral port with a temporary database.
"""

import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
import zipfile
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from biobank.db import Database, hash_password
from biobank.exporter import build_xlsx
from biobank.importer import normalize_date, parse_csv, parse_xlsx, rows_to_records
from biobank.pdf import build_receipt_pdf
from biobank.server import make_server, seed_users

SEED_PW = "Test@123"


# ----------------------------------------------------------------------------
# Database layer
# ----------------------------------------------------------------------------
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_password_hashing_roundtrip(self):
        salt, h = hash_password("secret")
        self.assertEqual(hash_password("secret", salt)[1], h)
        self.assertNotEqual(hash_password("other", salt)[1], h)

    def test_user_and_credentials(self):
        self.db.create_user("admin1", "Admin One", "admin", "pw12345")
        self.assertIsNone(self.db.verify_credentials("admin1", "wrong"))
        acc = self.db.verify_credentials("admin1", "pw12345")
        self.assertEqual(acc["role"], "admin")
        self.assertIsNone(self.db.verify_credentials("ghost", "pw12345"))

    def test_sessions(self):
        u = self.db.create_user("user1", "User One", "staff", "pw12345")
        token = self.db.create_session(u["id"])
        self.assertEqual(self.db.get_session_user(token)["username"], "user1")
        self.db.delete_session(token)
        self.assertIsNone(self.db.get_session_user(token))
        self.assertIsNone(self.db.get_session_user(None))

    def test_sample_required_fields(self):
        with self.assertRaises(ValueError):
            self.db.create_sample({"animal_type": "Cattle", "sample_type": "blood",
                                   "department": "virology"})  # missing area
        rec = self.db.create_sample({"area": "Riyadh", "animal_type": "Cattle",
                                     "sample_type": "blood", "department": "virology",
                                     "quantity_ml": "5"}, created_by="admin1")
        self.assertEqual(rec["area"], "Riyadh")
        self.assertEqual(rec["quantity_ml"], 5.0)
        self.assertEqual(rec["created_by"], "admin1")

    def test_list_filter_and_stats(self):
        base = {"animal_type": "Sheep", "sample_type": "blood"}
        self.db.create_sample({**base, "area": "Jeddah", "department": "virology"})
        self.db.create_sample({**base, "area": "Abha", "department": "Bacterial", "disease": "Brucellosis"})
        self.assertEqual(len(self.db.list_samples(department="virology")), 1)
        self.assertEqual(len(self.db.list_samples(search="brucel")), 1)
        stats = self.db.stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["by_department"]["virology"], 1)

    def test_delete_sample(self):
        r = self.db.create_sample({"area": "Hail", "animal_type": "Camel",
                                   "sample_type": "tissue", "department": "Parasitic"})
        self.assertTrue(self.db.delete_sample(r["id"]))
        self.assertFalse(self.db.delete_sample(r["id"]))


# ----------------------------------------------------------------------------
# Importer
# ----------------------------------------------------------------------------
class ImporterTests(unittest.TestCase):
    def test_normalize_date_serial_and_string(self):
        self.assertEqual(normalize_date("45707"), "2025-02-19")
        self.assertEqual(normalize_date("2025-03-01"), "2025-03-01")
        self.assertEqual(normalize_date(""), "")

    def test_parse_csv_and_map(self):
        text = ("Lab number,area,animal type,Sample type,department,barcode number\n"
                "264,Riyadh,Cattle,blood,virology,BC-1\n"
                ",,,,,\n")
        rows = parse_csv(text)
        records, hdr = rows_to_records(rows)
        self.assertEqual(hdr, 0)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["area"], "Riyadh")
        self.assertEqual(records[0]["barcode"], "BC-1")

    def test_header_detection_with_title_rows(self):
        rows = [
            ["Biobank Data Form", "", ""],
            ["", "", ""],
            ["area", "animal type", "department"],
            ["Riyadh", "Cattle", "virology"],
        ]
        records, hdr = rows_to_records(rows)
        self.assertEqual(hdr, 2)
        self.assertEqual(records[0]["animal_type"], "Cattle")

    def test_xlsx_export_roundtrips(self):
        headers = ["NO", "Area", "Quantity (ml)"]
        rows = [[1, "Riyadh", 5.0], [2, "Jeddah, north", 2.5]]  # comma + number
        data = build_xlsx(headers, rows)
        parsed = parse_xlsx(data)
        self.assertEqual(parsed[0][:3], ["NO", "Area", "Quantity (ml)"])
        self.assertEqual(parsed[2][1], "Jeddah, north")        # comma preserved
        self.assertEqual(parsed[1][2], "5.0")                  # number cell

    def test_parse_xlsx(self):
        # Build a minimal .xlsx in memory (inline strings, no sharedStrings).
        sheet = ('<?xml version="1.0"?>'
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 '<sheetData>'
                 '<row r="1"><c r="A1" t="inlineStr"><is><t>area</t></is></c>'
                 '<c r="B1" t="inlineStr"><is><t>animal type</t></is></c>'
                 '<c r="C1" t="inlineStr"><is><t>department</t></is></c></row>'
                 '<row r="2"><c r="A2" t="inlineStr"><is><t>Makkah</t></is></c>'
                 '<c r="B2" t="inlineStr"><is><t>Horse</t></is></c>'
                 '<c r="C2" t="inlineStr"><is><t>Bacterial</t></is></c></row>'
                 '</sheetData></worksheet>')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("xl/worksheets/sheet1.xml", sheet)
        rows = parse_xlsx(buf.getvalue())
        records, _ = rows_to_records(rows)
        self.assertEqual(records[0]["area"], "Makkah")
        self.assertEqual(records[0]["department"], "Bacterial")


# ----------------------------------------------------------------------------
# HTTP API + access control
# ----------------------------------------------------------------------------
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.tmp.close()
        cls.server = make_server(host="127.0.0.1", port=0, db_path=cls.tmp.name, seed_password=SEED_PW)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server.biobank_db.close()
        os.unlink(cls.tmp.name)

    def _req(self, method, path, body=None, token=None, raw=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        if raw is not None:
            data = raw
        elif body is not None:
            data = json.dumps(body).encode()
        else:
            data = None
        req = urllib.request.Request(url, data=data, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Cookie", f"bb_session={token}")
        try:
            with urllib.request.urlopen(req) as resp:
                cookie = resp.headers.get("Set-Cookie", "")
                return resp.status, json.loads(resp.read()), cookie
        except HTTPError as e:
            return e.code, json.loads(e.read()), e.headers.get("Set-Cookie", "")

    def _login(self, username, password=SEED_PW):
        status, body, cookie = self._req("POST", "/api/login",
                                         {"username": username, "password": password})
        self.assertEqual(status, 200, body)
        token = cookie.split("bb_session=")[1].split(";")[0]
        return token

    def test_health_is_public(self):
        status, body, _ = self._req("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_requires_auth(self):
        status, body, _ = self._req("GET", "/api/samples")
        self.assertEqual(status, 401)

    def test_bad_login(self):
        status, body, _ = self._req("POST", "/api/login",
                                    {"username": "admin1", "password": "nope"})
        self.assertEqual(status, 401)

    def test_admin_full_flow(self):
        token = self._login("admin1")
        status, me, _ = self._req("GET", "/api/me", token=token)
        self.assertEqual(me["user"]["role"], "admin")

        status, rec, _ = self._req("POST", "/api/samples", {
            "area": "Riyadh", "animal_type": "Cattle", "sample_type": "blood",
            "department": "virology", "barcode": "BC-9", "freezer_no": "F-1",
        }, token=token)
        self.assertEqual(status, 201, rec)
        self.assertEqual(rec["barcode"], "BC-9")           # admin CAN set restricted
        self.assertEqual(rec["freezer_no"], "F-1")

        status, out, _ = self._req("DELETE", f"/api/samples/{rec['id']}", token=token)
        self.assertEqual(status, 200)
        self.assertTrue(out["deleted"])

    def test_staff_cannot_set_restricted_fields(self):
        token = self._login("user1")
        status, rec, _ = self._req("POST", "/api/samples", {
            "area": "Jeddah", "animal_type": "Sheep", "sample_type": "Serum",
            "department": "Bacterial", "barcode": "SHOULD-NOT-STICK", "freezer_no": "F-9",
            "shelf_no": "R-9", "plate_no": "P-9",
        }, token=token)
        self.assertEqual(status, 201, rec)
        self.assertIsNone(rec["barcode"])                  # stripped server-side
        self.assertIsNone(rec["freezer_no"])
        self.assertIsNone(rec["shelf_no"])
        self.assertIsNone(rec["plate_no"])
        self.assertEqual(rec["area"], "Jeddah")            # allowed field kept

    def test_staff_cannot_delete_or_import_or_list_users(self):
        admin = self._login("admin1")
        _, rec, _ = self._req("POST", "/api/samples", {
            "area": "Abha", "animal_type": "Camel", "sample_type": "tissue",
            "department": "Parasitic"}, token=admin)
        staff = self._login("user2")
        status, _, _ = self._req("DELETE", f"/api/samples/{rec['id']}", token=staff)
        self.assertEqual(status, 403)
        status, _, _ = self._req("POST", "/api/import?filename=x.csv",
                                 raw=b"area\nRiyadh", token=staff)
        self.assertEqual(status, 403)
        status, _, _ = self._req("GET", "/api/users", token=staff)
        self.assertEqual(status, 403)

    def test_admin_import_csv(self):
        token = self._login("admin2")
        csv_bytes = ("area,animal type,Sample type,department,barcode number\n"
                     "Tabuk,Falcon,swabs,virology,BC-777\n").encode()
        status, res, _ = self._req("POST", "/api/import?filename=data.csv",
                                   raw=csv_bytes, token=token)
        self.assertEqual(status, 200, res)
        self.assertEqual(res["added"], 1)
        status, listing, _ = self._req("GET", "/api/samples?search=BC-777", token=token)
        self.assertEqual(len(listing["samples"]), 1)

    def test_logout_invalidates_session(self):
        token = self._login("user3")
        self._req("POST", "/api/logout", token=token)
        status, _, _ = self._req("GET", "/api/me", token=token)
        self.assertEqual(status, 401)

    def test_edit_sample_admin_and_staff(self):
        admin = self._login("admin1")
        _, rec, _ = self._req("POST", "/api/samples", {
            "area": "Riyadh", "animal_type": "Cattle", "sample_type": "blood",
            "department": "virology", "barcode": "BC-ORIG"}, token=admin)
        sid = rec["id"]
        # admin can edit any field, including restricted
        status, updated, _ = self._req("PATCH", f"/api/samples/{sid}", {
            "area": "Jeddah", "barcode": "BC-NEW"}, token=admin)
        self.assertEqual(status, 200)
        self.assertEqual(updated["area"], "Jeddah")
        self.assertEqual(updated["barcode"], "BC-NEW")
        # staff edit: allowed field changes, restricted field left intact
        staff = self._login("user1")
        status, u2, _ = self._req("PATCH", f"/api/samples/{sid}", {
            "sample_type": "Serum", "barcode": "HACK"}, token=staff)
        self.assertEqual(status, 200)
        self.assertEqual(u2["sample_type"], "Serum")
        self.assertEqual(u2["barcode"], "BC-NEW")          # unchanged by staff
        # editing a required field to empty is rejected
        status, _, _ = self._req("PATCH", f"/api/samples/{sid}", {"area": ""}, token=admin)
        self.assertEqual(status, 400)

    def test_audit_log_admin_only_and_records_events(self):
        admin = self._login("admin1")
        staff = self._login("user1")
        # staff cannot read the audit log
        status, _, _ = self._req("GET", "/api/audit", token=staff)
        self.assertEqual(status, 403)
        # a create + an update produce audit entries
        _, rec, _ = self._req("POST", "/api/samples", {
            "area": "Hail", "animal_type": "Camel", "sample_type": "tissue",
            "department": "Parasitic"}, token=staff)
        self._req("PATCH", f"/api/samples/{rec['id']}", {"sample_type": "blood"}, token=admin)
        status, body, _ = self._req("GET", "/api/audit", token=admin)
        self.assertEqual(status, 200)
        actions = [(e["action"], e["sample_id"]) for e in body["audit"]]
        self.assertIn(("create", rec["id"]), actions)
        self.assertIn(("update", rec["id"]), actions)
        update_entry = next(e for e in body["audit"] if e["action"] == "update" and e["sample_id"] == rec["id"])
        self.assertIn("sample_type", update_entry["summary"])

    def test_receipt_pdf(self):
        token = self._login("user1")  # staff can print a reception form
        _, rec, _ = self._req("POST", "/api/samples", {
            "area": "Riyadh", "animal_type": "Cattle", "sample_type": "blood",
            "department": "virology"}, token=token)
        # unauthenticated is rejected
        self.assertEqual(self._req("GET", f"/api/samples/{rec['id']}/receipt.pdf")[0], 401)
        # authenticated download is a real PDF
        url = f"http://127.0.0.1:{self.port}/api/samples/{rec['id']}/receipt.pdf"
        req = urllib.request.Request(url, headers={"Cookie": f"bb_session={token}"})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.headers.get("Content-Type"), "application/pdf")
            body = resp.read()
        self.assertTrue(body.startswith(b"%PDF"))
        self.assertTrue(body.rstrip().endswith(b"%%EOF"))

    def test_xlsx_export_endpoint_admin_only(self):
        admin = self._login("admin1")
        self._req("POST", "/api/samples", {
            "area": "Tabuk", "animal_type": "Falcon", "sample_type": "swabs",
            "department": "virology"}, token=admin)
        # staff is blocked
        staff = self._login("user2")
        status, _, _ = self._req("GET", "/api/export.xlsx", token=staff)
        self.assertEqual(status, 403)
        # admin gets a valid xlsx (verified by parsing it back)
        url = f"http://127.0.0.1:{self.port}/api/export.xlsx"
        req = urllib.request.Request(url, headers={"Cookie": f"bb_session={admin}"})
        with urllib.request.urlopen(req) as resp:
            self.assertIn("spreadsheetml", resp.headers.get("Content-Type", ""))
            payload = resp.read()
        parsed = parse_xlsx(payload)
        self.assertEqual(parsed[0][0], "NO")
        self.assertTrue(any("Tabuk" in row for row in parsed))

    def test_change_password(self):
        token = self._login("user4")
        # wrong current password
        status, _, _ = self._req("POST", "/api/change-password", {
            "current_password": "nope", "new_password": "newpass1"}, token=token)
        self.assertEqual(status, 400)
        # too short
        status, _, _ = self._req("POST", "/api/change-password", {
            "current_password": SEED_PW, "new_password": "123"}, token=token)
        self.assertEqual(status, 400)
        # success, then the new password works and the old one does not
        status, _, _ = self._req("POST", "/api/change-password", {
            "current_password": SEED_PW, "new_password": "brandnew1"}, token=token)
        self.assertEqual(status, 200)
        status, _, _ = self._req("POST", "/api/login",
                                 {"username": "user4", "password": SEED_PW})
        self.assertEqual(status, 401)
        self.assertTrue(self._login("user4", "brandnew1"))

    def test_admin_user_management(self):
        token = self._login("admin1")
        # create a new staff user
        status, u, _ = self._req("POST", "/api/users", {
            "username": "user5", "name": "Lab User 5", "role": "staff", "password": "pw12345",
        }, token=token)
        self.assertEqual(status, 201, u)
        self.assertEqual(u["role"], "staff")
        # duplicate username rejected
        status, err, _ = self._req("POST", "/api/users", {
            "username": "user5", "name": "Dup", "role": "staff", "password": "pw12345",
        }, token=token)
        self.assertEqual(status, 400)
        # the new user can sign in
        self.assertTrue(self._login("user5", "pw12345"))
        # short password rejected
        status, _, _ = self._req("POST", "/api/users", {
            "username": "u6", "name": "N", "role": "staff", "password": "123"}, token=token)
        self.assertEqual(status, 400)
        # delete the new user
        status, out, _ = self._req("DELETE", f"/api/users/{u['id']}", token=token)
        self.assertEqual(status, 200)
        self.assertTrue(out["deleted"])

    def test_cannot_delete_self_or_last_admin(self):
        token = self._login("admin1")
        _, me, _ = self._req("GET", "/api/me", token=token)
        users = self._req("GET", "/api/users", token=token)[1]["users"]
        admin1_id = next(u["id"] for u in users if u["username"] == "admin1")
        status, err, _ = self._req("DELETE", f"/api/users/{admin1_id}", token=token)
        self.assertEqual(status, 400)
        self.assertIn("own account", err["error"])

    def test_index_and_options(self):
        url = f"http://127.0.0.1:{self.port}/"
        with urllib.request.urlopen(url) as resp:
            html = resp.read().decode()
        self.assertIn("Biobank", html)
        token = self._login("admin1")
        status, opts, _ = self._req("GET", "/api/options", token=token)
        self.assertIn("area", opts["options"])
        self.assertIn("barcode", opts["restricted"])


class WsgiTests(unittest.TestCase):
    """Exercise the WSGI adapter over a live wsgiref server."""

    @classmethod
    def setUpClass(cls):
        from wsgiref.simple_server import make_server as make_wsgi_server
        from biobank.wsgi import make_app

        cls.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.tmp.close()
        app = make_app(db_path=cls.tmp.name, seed_password=SEED_PW, secure_cookies=True)
        cls.httpd = make_wsgi_server("127.0.0.1", 0, app)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        os.unlink(cls.tmp.name)

    def _req(self, method, path, body=None, token=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Cookie", f"bb_session={token}")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read()), resp.headers.get("Set-Cookie", "")
        except HTTPError as e:
            return e.code, json.loads(e.read()), e.headers.get("Set-Cookie", "")

    def _login(self, username, password=SEED_PW):
        status, _, cookie = self._req("POST", "/api/login", {"username": username, "password": password})
        self.assertEqual(status, 200)
        self.assertIn("Secure", cookie)  # secure_cookies=True honored
        return cookie.split("bb_session=")[1].split(";")[0]

    def test_wsgi_auth_and_rbac(self):
        # unauthenticated
        self.assertEqual(self._req("GET", "/api/samples")[0], 401)
        # staff create strips restricted fields
        staff = self._login("user1")
        status, rec, _ = self._req("POST", "/api/samples", {
            "area": "Riyadh", "animal_type": "Cattle", "sample_type": "blood",
            "department": "virology", "barcode": "NO"}, token=staff)
        self.assertEqual(status, 201)
        self.assertIsNone(rec["barcode"])
        # staff blocked from admin routes
        self.assertEqual(self._req("GET", "/api/audit", token=staff)[0], 403)
        self.assertEqual(self._req("DELETE", f"/api/samples/{rec['id']}", token=staff)[0], 403)
        # admin can edit + audit records the change
        admin = self._login("admin1")
        status, upd, _ = self._req("PATCH", f"/api/samples/{rec['id']}",
                                   {"barcode": "BC-1"}, token=admin)
        self.assertEqual(status, 200)
        self.assertEqual(upd["barcode"], "BC-1")
        status, audit, _ = self._req("GET", "/api/audit", token=admin)
        self.assertTrue(any(e["action"] == "update" for e in audit["audit"]))

    def test_wsgi_receipt_pdf(self):
        token = self._login("admin1")
        status, rec, _ = self._req("POST", "/api/samples", {
            "area": "Tabuk", "animal_type": "Falcon", "sample_type": "swabs",
            "department": "virology"}, token=token)
        url = f"http://127.0.0.1:{self.port}/api/samples/{rec['id']}/receipt.pdf"
        req = urllib.request.Request(url, headers={"Cookie": f"bb_session={token}"})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.headers.get("Content-Type"), "application/pdf")
            self.assertTrue(resp.read().startswith(b"%PDF"))

    def test_wsgi_serves_ui(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as resp:
            self.assertIn("Biobank", resp.read().decode())


class PdfTests(unittest.TestCase):
    def test_build_receipt_is_valid_pdf(self):
        pdf = build_receipt_pdf({
            "id": 42, "area": "Riyadh", "animal_type": "Cattle", "sample_type": "blood",
            "department": "virology", "storage_method": "-80 °C", "created_by": "user1"})
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"Receipt #42", pdf)


class SeedTests(unittest.TestCase):
    def test_seed_only_once(self):
        db = Database(":memory:")
        self.assertTrue(seed_users(db, "pw"))
        self.assertEqual(db.count_users(), 6)
        self.assertFalse(seed_users(db, "pw"))   # idempotent
        self.assertEqual(db.count_users(), 6)
        db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
