"""End-to-end tests for the biobank system.

Covers the database layer directly and the HTTP API against a live server
bound to an ephemeral port with a temporary database.
"""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from biobank.db import Database
from biobank.server import make_server


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_create_and_get_donor(self):
        d = self.db.create_donor("D-001", "Alice Zahra", 1990, "F")
        self.assertEqual(d["code"], "D-001")
        self.assertEqual(self.db.get_donor(d["id"])["full_name"], "Alice Zahra")

    def test_duplicate_code_rejected(self):
        self.db.create_donor("D-001", "Alice")
        with self.assertRaises(Exception):
            self.db.create_donor("D-001", "Someone Else")

    def test_donor_validation(self):
        with self.assertRaises(ValueError):
            self.db.create_donor("", "No Code")
        with self.assertRaises(ValueError):
            self.db.create_donor("D-9", "Bad Sex", sex="X")

    def test_sample_lifecycle(self):
        d = self.db.create_donor("D-002", "Bob")
        s = self.db.create_sample(d["id"], "blood", volume_ml=5.0, storage_temp=-80,
                                  location="Freezer-A")
        self.assertEqual(s["status"], "stored")
        updated = self.db.update_sample_status(s["id"], "in_use")
        self.assertEqual(updated["status"], "in_use")
        with self.assertRaises(ValueError):
            self.db.update_sample_status(s["id"], "bogus")

    def test_sample_requires_existing_donor(self):
        with self.assertRaises(ValueError):
            self.db.create_sample(999, "blood")

    def test_cascade_delete(self):
        d = self.db.create_donor("D-003", "Carol")
        self.db.create_sample(d["id"], "DNA")
        self.db.delete_donor(d["id"])
        self.assertEqual(self.db.list_samples(donor_id=d["id"]), [])

    def test_filter_and_stats(self):
        d = self.db.create_donor("D-004", "Dana")
        self.db.create_sample(d["id"], "blood")
        s2 = self.db.create_sample(d["id"], "plasma")
        self.db.update_sample_status(s2["id"], "depleted")
        self.assertEqual(len(self.db.list_samples(status="stored")), 1)
        stats = self.db.stats()
        self.assertEqual(stats["donors"], 1)
        self.assertEqual(stats["samples"], 2)
        self.assertEqual(stats["samples_by_status"]["depleted"], 1)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.tmp.close()
        cls.server = make_server(host="127.0.0.1", port=0, db_path=cls.tmp.name)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server.biobank_db.close()
        os.unlink(cls.tmp.name)

    def _req(self, method, path, body=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except HTTPError as e:
            return e.code, json.loads(e.read())

    def test_health(self):
        status, body = self._req("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_full_flow(self):
        status, donor = self._req("POST", "/api/donors",
                                  {"code": "API-1", "full_name": "Eve", "sex": "F"})
        self.assertEqual(status, 201)
        did = donor["id"]

        status, sample = self._req("POST", "/api/samples",
                                   {"donor_id": did, "sample_type": "serum", "volume_ml": 2.5})
        self.assertEqual(status, 201)
        sid = sample["id"]

        status, body = self._req("PATCH", f"/api/samples/{sid}", {"status": "in_use"})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "in_use")

        status, body = self._req("GET", f"/api/samples?donor_id={did}")
        self.assertEqual(len(body["samples"]), 1)

        status, _ = self._req("DELETE", f"/api/donors/{did}")
        self.assertEqual(status, 200)

    def test_bad_request(self):
        status, body = self._req("POST", "/api/donors", {"full_name": "No Code"})
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_not_found(self):
        status, body = self._req("GET", "/api/donors/99999")
        self.assertEqual(status, 404)

    def test_index_served(self):
        url = f"http://127.0.0.1:{self.port}/"
        with urllib.request.urlopen(url) as resp:
            html = resp.read().decode()
        self.assertIn("Biobank", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
