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

from biobank import amr
from biobank.db import Database, hash_password
from biobank.importer import normalize_date, parse_csv, parse_xlsx, rows_to_records
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

    def test_amr_requires_auth(self):
        status, _, _ = self._req("POST", "/api/amr", raw=b">x\nACGT")
        self.assertEqual(status, 401)
        status, _, _ = self._req("GET", "/api/amr/panel")
        self.assertEqual(status, 401)

    def test_amr_panel_and_screen(self):
        token = self._login("user1")  # staff may screen (read-only, no DB write)
        status, panel, _ = self._req("GET", "/api/amr/panel", token=token)
        self.assertEqual(status, 200)
        self.assertGreater(len(panel["panel"]), 0)

        ndm = next(m for m in amr.AMR_PANEL if m.gene == "blaNDM").nt
        fasta = f">contig\nACGTACGT{ndm}TTTT\n".encode()
        status, report, _ = self._req("POST", "/api/amr", raw=fasta, token=token)
        self.assertEqual(status, 200, report)
        self.assertIn("blaNDM", report["summary"]["resistance_genes"])

    def test_amr_empty_body_rejected(self):
        token = self._login("user1")
        status, err, _ = self._req("POST", "/api/amr", raw=b"", token=token)
        self.assertEqual(status, 400)

    def test_index_and_options(self):
        url = f"http://127.0.0.1:{self.port}/"
        with urllib.request.urlopen(url) as resp:
            html = resp.read().decode()
        self.assertIn("Biobank", html)
        token = self._login("admin1")
        status, opts, _ = self._req("GET", "/api/options", token=token)
        self.assertIn("area", opts["options"])
        self.assertIn("barcode", opts["restricted"])


# ----------------------------------------------------------------------------
# AMR screening engine
# ----------------------------------------------------------------------------
class AmrTests(unittest.TestCase):
    def _marker(self, gene):
        return next(m for m in amr.AMR_PANEL if m.gene == gene)

    def test_reverse_complement_and_translate(self):
        self.assertEqual(amr.reverse_complement("ATGC"), "GCAT")
        self.assertEqual(amr.reverse_complement("AATTCCGG"), "CCGGAATT")
        self.assertEqual(amr.translate("ATGAAATAA"), "MK*")
        self.assertTrue(amr.is_nucleotide("ACGTACGTNN"))
        self.assertFalse(amr.is_nucleotide("MKLPQRSTVWY"))

    def test_parse_fasta(self):
        text = ">seq1 desc\nACGT\nACGT\n\n>seq2\nTTTT\n"
        recs = amr.parse_fasta(text)
        self.assertEqual(recs, [("seq1 desc", "ACGTACGT"), ("seq2", "TTTT")])
        # headerless block is accepted and labelled
        self.assertEqual(amr.parse_fasta("ACGTACGT")[0][0], "sequence_1")

    def test_exact_nucleotide_hit(self):
        ndm = self._marker("blaNDM").nt
        contig = "ACGTACGTACGT" + ndm + "TTTTGGGGCCCC"
        report = amr.screen_fasta(f">c1\n{contig}\n")
        genes = report["summary"]["resistance_genes"]
        self.assertIn("blaNDM", genes)
        hit = next(h for h in report["hits"] if h["gene"] == "blaNDM")
        self.assertEqual(hit["identity"], 100.0)
        self.assertEqual(hit["strand"], "+")
        self.assertEqual(hit["start"], 13)  # 1-based, after the 12 bp flank

    def test_mismatch_tolerant_hit(self):
        teta = list(self._marker("tetA").nt)
        teta[5] = "A" if teta[5] != "A" else "C"   # one mismatch
        seq = "".join(teta)
        report = amr.screen_fasta(f">m\n{seq}\n")
        hit = next(h for h in report["hits"] if h["gene"] == "tetA")
        self.assertGreater(hit["identity"], 90.0)
        self.assertLess(hit["identity"], 100.0)

    def test_reverse_strand_hit(self):
        kpc = self._marker("blaKPC").nt
        rc = amr.reverse_complement("AAAA" + kpc + "TTTT")
        report = amr.screen_fasta(f">rev\n{rc}\n")
        hit = next(h for h in report["hits"] if h["gene"] == "blaKPC")
        self.assertEqual(hit["strand"], "-")
        self.assertEqual(hit["identity"], 100.0)

    def test_protein_hit(self):
        vim = self._marker("blaVIM")
        prot = "MSTVSQ" + vim.aa + "GGWW"
        report = amr.screen_fasta(f">p\n{prot}\n")
        hit = next(h for h in report["hits"] if h["gene"] == "blaVIM")
        self.assertEqual(hit["via"], "protein")
        self.assertEqual(report["sequences"][0]["type"], "protein")

    def test_no_false_positive_on_random(self):
        import random
        random.seed(42)
        rnd = "".join(random.choice("ACGT") for _ in range(4000))
        report = amr.screen_fasta(f">rand\n{rnd}\n")
        self.assertEqual(report["summary"]["total_hits"], 0)

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            amr.screen_fasta("   \n\n")

    def test_panel_summary_hides_sequences(self):
        panel = amr.panel_summary()
        self.assertEqual(len(panel), len(amr.AMR_PANEL))
        self.assertNotIn("marker", panel[0])
        self.assertIn("drug_class", panel[0])


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
