"""Tests for the bioinformatic AMR screening tool."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bioinformatic import amr


class SequenceHelperTests(unittest.TestCase):
    def test_reverse_complement(self):
        self.assertEqual(amr.reverse_complement("ATGC"), "GCAT")
        self.assertEqual(amr.reverse_complement("AATTCCGG"), "CCGGAATT")

    def test_translate(self):
        self.assertEqual(amr.translate("ATGAAATAA"), "MK*")
        self.assertEqual(amr.translate("GGGTTTCCC"), "GFP")

    def test_is_nucleotide(self):
        self.assertTrue(amr.is_nucleotide("ACGTACGTNN"))
        self.assertFalse(amr.is_nucleotide("MKLPQRSTVWY"))

    def test_parse_fasta(self):
        text = ">seq1 desc\nACGT\nACGT\n\n>seq2\nTTTT\n"
        recs = amr.parse_fasta(text)
        self.assertEqual(recs, [("seq1 desc", "ACGTACGT"), ("seq2", "TTTT")])
        self.assertEqual(amr.parse_fasta("ACGTACGT")[0][0], "sequence_1")


class ScreeningTests(unittest.TestCase):
    def _marker(self, gene):
        return next(m for m in amr.AMR_PANEL if m.gene == gene)

    def test_exact_nucleotide_hit(self):
        ndm = self._marker("blaNDM").nt
        contig = "ACGTACGTACGT" + ndm + "TTTTGGGGCCCC"
        report = amr.screen_fasta(f">c1\n{contig}\n")
        self.assertIn("blaNDM", report["summary"]["resistance_genes"])
        hit = next(h for h in report["hits"] if h["gene"] == "blaNDM")
        self.assertEqual(hit["identity"], 100.0)
        self.assertEqual(hit["strand"], "+")
        self.assertEqual(hit["start"], 13)

    def test_mismatch_tolerant_hit(self):
        teta = list(self._marker("tetA").nt)
        teta[5] = "A" if teta[5] != "A" else "C"
        report = amr.screen_fasta(f">m\n{''.join(teta)}\n")
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
        report = amr.screen_fasta(f">p\nMSTVSQ{vim.aa}GGWW\n")
        hit = next(h for h in report["hits"] if h["gene"] == "blaVIM")
        self.assertEqual(hit["via"], "protein")
        self.assertEqual(report["sequences"][0]["type"], "protein")

    def test_no_false_positive_on_random(self):
        random.seed(42)
        rnd = "".join(random.choice("ACGT") for _ in range(4000))
        report = amr.screen_fasta(f">rand\n{rnd}\n")
        self.assertEqual(report["summary"]["total_hits"], 0)

    def test_multiple_genes_in_one_contig(self):
        ndm = self._marker("blaNDM").nt
        mcr = self._marker("mcr-1").nt
        report = amr.screen_fasta(f">iso\nAAAA{ndm}GGGG{mcr}TTTT\n")
        genes = report["summary"]["resistance_genes"]
        self.assertIn("blaNDM", genes)
        self.assertIn("mcr-1", genes)
        self.assertEqual(report["summary"]["sequences_with_hits"], 1)

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            amr.screen_fasta("   \n\n")

    def test_bytes_input(self):
        ndm = self._marker("blaNDM").nt
        report = amr.screen_fasta(f">c\nAAAA{ndm}TTTT\n".encode())
        self.assertIn("blaNDM", report["summary"]["resistance_genes"])

    def test_panel_summary_hides_sequences(self):
        panel = amr.panel_summary()
        self.assertEqual(len(panel), len(amr.AMR_PANEL))
        self.assertNotIn("marker", panel[0])
        self.assertIn("drug_class", panel[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
