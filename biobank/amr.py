"""Antimicrobial-resistance (AMR) screening for FASTA sequences.

A dependency-free screener (standard library only) that scans nucleotide or
protein FASTA input for known antimicrobial-resistance gene markers and
reports the resistance genes, drug classes and mechanisms detected.

How it works
------------
The module ships a curated *marker panel* (``AMR_PANEL``): for each gene it
stores a short, conserved reference sub-sequence together with its drug class
and mechanism. Query sequences are screened with a BLAST-style seed-and-extend
approximate matcher:

* nucleotide queries are searched on both strands (plus + reverse-complement);
* protein queries are compared against the translated marker;
* a hit is reported when an aligned marker meets the identity and coverage
  thresholds (defaults: 90 % identity, 80 % coverage for nucleotides).

The bundled panel is a compact demonstration reference, not a substitute for
comprehensive curated databases such as CARD, ResFinder or AMRFinderPlus. It
is deliberately self-contained so the tool runs anywhere Python does, with no
network access or external database downloads.

Command line
------------
    python3 -m biobank.amr sequences.fasta [more.fasta ...]
    python3 -m biobank.amr --json sequences.fasta
    cat sequences.fasta | python3 -m biobank.amr -
"""

from __future__ import annotations

import json
import sys
from typing import Any, Iterable, Optional

# ---------------------------------------------------------------------------
# Sequence helpers
# ---------------------------------------------------------------------------

_COMPLEMENT = str.maketrans("ACGTUNRYSWKMBDHVacgtunryswkmbdhv",
                            "TGCAANYRSWMKVHDBtgcaanyrswmkvhdb")

# Standard genetic code (DNA codons -> single-letter amino acids; * = stop).
_CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

_NUC_CHARS = set("ACGTUN")


def clean_sequence(seq: str) -> str:
    """Uppercase a sequence and drop whitespace/gap characters."""
    return "".join(seq.split()).upper().replace("-", "").replace(".", "")


def reverse_complement(seq: str) -> str:
    """Reverse-complement a nucleotide sequence."""
    return seq.translate(_COMPLEMENT)[::-1]


def translate(seq: str, frame: int = 0) -> str:
    """Translate a nucleotide sequence to protein (single-letter, * = stop)."""
    seq = seq[frame:]
    return "".join(
        _CODON_TABLE.get(seq[i:i + 3], "X") for i in range(0, len(seq) - 2, 3)
    )


def is_nucleotide(seq: str, threshold: float = 0.9) -> bool:
    """Heuristic: True if the sequence looks like DNA/RNA rather than protein."""
    if not seq:
        return True
    hits = sum(1 for c in seq if c in _NUC_CHARS)
    return hits / len(seq) >= threshold


# ---------------------------------------------------------------------------
# FASTA parsing
# ---------------------------------------------------------------------------

def parse_fasta(text: str) -> list[tuple[str, str]]:
    """Parse FASTA text into a list of ``(header, sequence)`` tuples.

    Bare (headerless) sequence blocks are accepted and labelled ``sequence_N``.
    Sequences are uppercased with whitespace and gap characters removed.
    """
    records: list[tuple[str, list[str]]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            records.append((line[1:].strip(), []))
        elif line.startswith(";"):  # legacy FASTA comment line
            continue
        else:
            if not records:
                records.append(("", []))
            records[-1][1].append(line)

    out: list[tuple[str, str]] = []
    for i, (header, chunks) in enumerate(records, start=1):
        seq = clean_sequence("".join(chunks))
        if not seq:
            continue
        out.append((header or f"sequence_{i}", seq))
    return out


# ---------------------------------------------------------------------------
# AMR marker panel
# ---------------------------------------------------------------------------
# Each entry pairs a resistance gene with a conserved nucleotide marker plus
# its drug class and resistance mechanism. Markers are representative fragments
# used for demonstration screening (see the module docstring).

_PANEL_RAW: list[dict[str, str]] = [
    {"gene": "blaTEM", "drug_class": "Beta-lactams", "mechanism": "Broad-spectrum beta-lactamase",
     "marker": "ATGAGTATTCAACATTTCCGTGTCGCCCTTATTCCCTTTTTTGCGGCATTTTGCCTTCCTG"},
    {"gene": "blaSHV", "drug_class": "Beta-lactams", "mechanism": "Broad-spectrum beta-lactamase",
     "marker": "ATGCGTTATATTCGCCTGTGTATTATCTCCCTGTTAGCCACCCTGCCGCTGGCGGTACAC"},
    {"gene": "blaCTX-M", "drug_class": "Cephalosporins", "mechanism": "Extended-spectrum beta-lactamase (ESBL)",
     "marker": "ATGGTGACAAAGAGAGTGCAACGGATGATGTTCGCGGCGGCGGTGCTGCTGCTGCTGGCC"},
    {"gene": "blaKPC", "drug_class": "Carbapenems", "mechanism": "Class A carbapenemase",
     "marker": "ATGTCACTGTATCGCCGTCTAGTTCTGCTGTCTTGTCTCTCATGGCCGCTGGCTGGCTTT"},
    {"gene": "blaNDM", "drug_class": "Carbapenems", "mechanism": "Metallo-beta-lactamase (NDM)",
     "marker": "ATGGAATTGCCCAATATTATGCACCCGGTCGCGAAGCTGAGCACCGCATTAGCCGCTGCA"},
    {"gene": "blaOXA-48", "drug_class": "Carbapenems", "mechanism": "Class D oxacillinase carbapenemase",
     "marker": "ATGCGTGTATTAGCCTTATCGGCTGTGTTTTTGGTGGCATCGATTATCGGAATGCCTGTG"},
    {"gene": "blaVIM", "drug_class": "Carbapenems", "mechanism": "Metallo-beta-lactamase (VIM)",
     "marker": "ATGTTAAAAGTTATTAGTAGTTTATTGGTCTATATGACCGCGTCTGTCATGGCTGTTGCC"},
    {"gene": "blaIMP", "drug_class": "Carbapenems", "mechanism": "Metallo-beta-lactamase (IMP)",
     "marker": "ATGAGCAAGTTATCTGTATTCTTTATATTTTTGTTTTGTAGCATTGCTACCGCAGCAGAG"},
    {"gene": "blaCMY", "drug_class": "Cephalosporins", "mechanism": "AmpC-type beta-lactamase",
     "marker": "ATGATGAAAAAATCGTTATGCTGCGCTCTGCTGCTGACAGCCTCTTTCTCCACATTTGCT"},
    {"gene": "mecA", "drug_class": "Beta-lactams (methicillin)", "mechanism": "Altered PBP2a (MRSA)",
     "marker": "ATGAAAAAGATAAAAATTGTTCCACTTATTTTAATAGTTGTAGTTGTCGGGTTTGGTATA"},
    {"gene": "vanA", "drug_class": "Glycopeptides", "mechanism": "D-Ala-D-Lac ligase (vancomycin)",
     "marker": "ATGAATAGAATAAAAGTTGCAATACTGTTTGGGGGTTGCTCAGAGGAGCATGACGTATCG"},
    {"gene": "vanB", "drug_class": "Glycopeptides", "mechanism": "D-Ala-D-Lac ligase (vancomycin)",
     "marker": "ATGGGAAAAAGGATTGCGATTATTTTTGGCGGCTGCTCTCCGGAACATGAAGTGTCCGTG"},
    {"gene": "mcr-1", "drug_class": "Polymyxins (colistin)", "mechanism": "Phosphoethanolamine transferase",
     "marker": "ATGATGCAGCATACTTCTGTGTGGTACCGACGCTCGGTCAGTCCGTTTGTTCTTGTGGCG"},
    {"gene": "tetA", "drug_class": "Tetracyclines", "mechanism": "Efflux pump (major facilitator)",
     "marker": "ATGAAATCTAACAATGCGCTCATCGTCATCCTCGGCACCGTCACCCTGGATGCTGTAGGC"},
    {"gene": "tetM", "drug_class": "Tetracyclines", "mechanism": "Ribosomal protection protein",
     "marker": "ATGAAAATTATTAATCTTGGGATTTTAGCTCATGTTGATGCAGGAAAAACTACGTTAACA"},
    {"gene": "sul1", "drug_class": "Sulfonamides", "mechanism": "Insensitive dihydropteroate synthase",
     "marker": "ATGGTGACGGTGTTCGGCATTCTGAATCTCACCGAGGACTCCTTCTTCGATGAGAGCCGG"},
    {"gene": "sul2", "drug_class": "Sulfonamides", "mechanism": "Insensitive dihydropteroate synthase",
     "marker": "ATGAATAAATCGCTCATCATTTTCGGCATCGTCAACATAACCTCGGACAGTTTCTCCGAT"},
    {"gene": "aac(6')-Ib", "drug_class": "Aminoglycosides", "mechanism": "Acetyltransferase",
     "marker": "ATGACCGAGCAAGAGATCAAAGATCTGTTTGCCGGCTGGGTGATGCTGCACTGGGCGTGG"},
    {"gene": "aph(3')-III", "drug_class": "Aminoglycosides", "mechanism": "Phosphotransferase",
     "marker": "ATGGCTAAAATGAGAATATCACCGGAATTGAAAAAACTGATCGAAAAATACCGCTGCGTA"},
    {"gene": "aadA1", "drug_class": "Aminoglycosides", "mechanism": "Adenylyltransferase (streptomycin)",
     "marker": "ATGAGGGAAGCGGTGATCGCCGAAGTATCGACTCAACTATCAGAGGTAGTTGGCGTCATC"},
    {"gene": "ermB", "drug_class": "Macrolides (MLSb)", "mechanism": "23S rRNA methyltransferase",
     "marker": "ATGAACAAAAATATAAAATATTCTCAAAACTTTTTAACGAGTGAAAAAGTACTCAACCAA"},
    {"gene": "mefA", "drug_class": "Macrolides", "mechanism": "Efflux pump",
     "marker": "ATGGAAAATTATAGTAAATATTCTAATAAAAATGAGTCTAATAGTTCTGCTGATAAAAAT"},
    {"gene": "qnrS", "drug_class": "Fluoroquinolones", "mechanism": "Target protection (Qnr)",
     "marker": "ATGGAAACCTACAATCATACATATCGGCACCACAATTTTTCACATAAAGACTTAAGTGAT"},
    {"gene": "qnrB", "drug_class": "Fluoroquinolones", "mechanism": "Target protection (Qnr)",
     "marker": "ATGACGCTATTTGCATTATTTTTTAGTGCAGTTTGACAGGATTAGCAGAGCTGCAGGCTG"},
    {"gene": "catA1", "drug_class": "Phenicols", "mechanism": "Chloramphenicol acetyltransferase",
     "marker": "ATGGAGAAAAAAATCACTGGATATACCACCGTTGATATATCCCAATGGCATCGTAAAGAA"},
    {"gene": "floR", "drug_class": "Phenicols", "mechanism": "Efflux pump (florfenicol)",
     "marker": "ATGACCACCACACGCCCCGCGACATCGACTGCCGCCACGCTGGCCGCTGCCGGCGCCCTC"},
    {"gene": "dfrA1", "drug_class": "Trimethoprim", "mechanism": "Insensitive dihydrofolate reductase",
     "marker": "ATGAGCACAGACTTCGCTCATTCAGGTATTGTTGCTGCTAGCTGCTATGGCGCAGTTGCT"},
    {"gene": "catB3", "drug_class": "Phenicols", "mechanism": "Chloramphenicol acetyltransferase",
     "marker": "ATGACTCGCCTGGTGACCGGCGTGCTGGCCTGCTGGCTGGTCGCCTGCACCGCCGGCCTG"},
]


class Marker:
    """A single reference marker with its precomputed protein translation."""

    __slots__ = ("gene", "drug_class", "mechanism", "nt", "aa")

    def __init__(self, gene: str, drug_class: str, mechanism: str, nt: str) -> None:
        self.gene = gene
        self.drug_class = drug_class
        self.mechanism = mechanism
        self.nt = clean_sequence(nt)
        self.aa = translate(self.nt).rstrip("*")

    def as_dict(self) -> dict[str, Any]:
        return {
            "gene": self.gene,
            "drug_class": self.drug_class,
            "mechanism": self.mechanism,
            "marker_length": len(self.nt),
        }


AMR_PANEL: list[Marker] = [
    Marker(m["gene"], m["drug_class"], m["mechanism"], m["marker"]) for m in _PANEL_RAW
]


def panel_summary() -> list[dict[str, Any]]:
    """Public description of the bundled marker panel (no raw sequences)."""
    return [m.as_dict() for m in AMR_PANEL]


# ---------------------------------------------------------------------------
# Approximate matcher (seed and extend)
# ---------------------------------------------------------------------------

def _seed_positions(seq: str, seed: str, start_hint: int) -> Iterable[int]:
    """Yield every index where ``seed`` occurs in ``seq``."""
    idx = seq.find(seed)
    while idx != -1:
        yield idx
        idx = seq.find(seed, idx + 1)


def _best_alignment(
    query: str, motif: str, seed_len: int, min_identity: float, min_coverage: float
) -> Optional[tuple[int, int, float, float]]:
    """Find the best gap-free placement of ``motif`` within ``query``.

    Uses exact short seeds taken from the motif to anchor candidate
    placements, then scores identity over the overlapping region (a
    Hamming/ungapped alignment). Returns ``(start, end, identity, coverage)``
    on the query (0-based, half-open) or ``None`` if nothing clears the
    thresholds.
    """
    mlen = len(motif)
    if mlen == 0 or len(query) == 0:
        return None
    k = min(seed_len, mlen)

    # A few non-overlapping seeds spread across the motif improve sensitivity
    # to mismatches while keeping the search anchored on exact words.
    seed_offsets = sorted({0, max(0, (mlen - k) // 2), max(0, mlen - k)})

    best: Optional[tuple[int, int, float, float]] = None
    seen_starts: set[int] = set()
    for off in seed_offsets:
        seed = motif[off:off + k]
        for pos in _seed_positions(query, seed, off):
            q0 = pos - off  # where motif index 0 lands on the query
            lo = max(0, q0)
            hi = min(len(query), q0 + mlen)
            if lo in seen_starts and hi - lo == mlen:
                continue
            seen_starts.add(lo)
            overlap = hi - lo
            if overlap <= 0:
                continue
            matches = 0
            for qi in range(lo, hi):
                if query[qi] == motif[qi - q0]:
                    matches += 1
            identity = matches / overlap
            coverage = overlap / mlen
            if identity < min_identity or coverage < min_coverage:
                continue
            cand = (lo, hi, identity, coverage)
            if best is None or (identity, coverage) > (best[2], best[3]):
                best = cand
    return best


# ---------------------------------------------------------------------------
# Screening
# ---------------------------------------------------------------------------

def screen_sequence(
    header: str,
    seq: str,
    min_identity: float = 0.90,
    min_coverage: float = 0.80,
) -> list[dict[str, Any]]:
    """Screen one sequence against the panel; return a list of hit dicts."""
    seq = clean_sequence(seq)
    hits: list[dict[str, Any]] = []
    nucleotide = is_nucleotide(seq)

    if nucleotide:
        rc = reverse_complement(seq)
        for m in AMR_PANEL:
            for strand, target in (("+", seq), ("-", rc)):
                aln = _best_alignment(target, m.nt, 12, min_identity, min_coverage)
                if aln is None:
                    continue
                lo, hi, identity, coverage = aln
                if strand == "-":  # map coordinates back to the forward strand
                    lo, hi = len(seq) - hi, len(seq) - lo
                hits.append({
                    "query": header,
                    "gene": m.gene,
                    "drug_class": m.drug_class,
                    "mechanism": m.mechanism,
                    "identity": round(identity * 100, 1),
                    "coverage": round(coverage * 100, 1),
                    "strand": strand,
                    "start": lo + 1,  # 1-based, inclusive
                    "end": hi,
                    "via": "nucleotide",
                })
                break  # one strand is enough per gene
    else:
        for m in AMR_PANEL:
            if not m.aa:
                continue
            aln = _best_alignment(seq, m.aa, 6, max(min_identity, 0.85), min_coverage)
            if aln is None:
                continue
            lo, hi, identity, coverage = aln
            hits.append({
                "query": header,
                "gene": m.gene,
                "drug_class": m.drug_class,
                "mechanism": m.mechanism,
                "identity": round(identity * 100, 1),
                "coverage": round(coverage * 100, 1),
                "strand": ".",
                "start": lo + 1,
                "end": hi,
                "via": "protein",
            })

    hits.sort(key=lambda h: (-h["identity"], h["gene"]))
    return hits


def screen_fasta(
    data: Any,
    min_identity: float = 0.90,
    min_coverage: float = 0.80,
) -> dict[str, Any]:
    """Screen every record in FASTA ``data`` (str or bytes).

    Returns a report dict with per-sequence results, all hits, and a summary
    of the resistance genes / drug classes detected.
    """
    if isinstance(data, (bytes, bytearray)):
        text = bytes(data).decode("utf-8", errors="replace")
    else:
        text = str(data)

    records = parse_fasta(text)
    if not records:
        raise ValueError("no FASTA sequences found in the input")

    sequences: list[dict[str, Any]] = []
    all_hits: list[dict[str, Any]] = []
    for header, seq in records:
        hits = screen_sequence(header, seq, min_identity, min_coverage)
        sequences.append({
            "query": header,
            "length": len(seq),
            "type": "nucleotide" if is_nucleotide(seq) else "protein",
            "hits": hits,
        })
        all_hits.extend(hits)

    genes = sorted({h["gene"] for h in all_hits})
    classes = sorted({h["drug_class"] for h in all_hits})
    return {
        "sequences": sequences,
        "hits": all_hits,
        "summary": {
            "sequences_screened": len(records),
            "sequences_with_hits": sum(1 for s in sequences if s["hits"]),
            "total_hits": len(all_hits),
            "resistance_genes": genes,
            "drug_classes": classes,
            "panel_size": len(AMR_PANEL),
        },
    }


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _format_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    s = report["summary"]
    lines.append("Antimicrobial-resistance screening report")
    lines.append("=" * 42)
    lines.append(f"Sequences screened : {s['sequences_screened']}")
    lines.append(f"With AMR hits      : {s['sequences_with_hits']}")
    lines.append(f"Total hits         : {s['total_hits']}")
    lines.append(f"Panel markers      : {s['panel_size']}")
    lines.append("")
    if s["resistance_genes"]:
        lines.append("Resistance genes   : " + ", ".join(s["resistance_genes"]))
        lines.append("Drug classes       : " + ", ".join(s["drug_classes"]))
    else:
        lines.append("No known resistance markers detected.")
    lines.append("")

    for seq in report["sequences"]:
        lines.append(f"> {seq['query']}  ({seq['length']} bp/aa, {seq['type']})")
        if not seq["hits"]:
            lines.append("    (no hits)")
            continue
        lines.append("    {:<12} {:<7} {:<7} {:<6} {:<10} {}".format(
            "GENE", "IDENT%", "COV%", "STRAND", "POS", "DRUG CLASS / MECHANISM"))
        for h in seq["hits"]:
            lines.append("    {:<12} {:<7} {:<7} {:<6} {:<10} {} — {}".format(
                h["gene"], h["identity"], h["coverage"], h["strand"],
                f"{h['start']}-{h['end']}", h["drug_class"], h["mechanism"]))
        lines.append("")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = False
    paths: list[str] = []
    for arg in argv:
        if arg in ("--json", "-j"):
            as_json = True
        elif arg in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            paths.append(arg)

    if not paths:
        print("usage: python3 -m biobank.amr [--json] <file.fasta> [...]  ('-' for stdin)",
              file=sys.stderr)
        return 2

    chunks: list[str] = []
    for path in paths:
        if path == "-":
            chunks.append(sys.stdin.read())
        else:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    chunks.append(fh.read())
            except OSError as exc:
                print(f"error: cannot read {path}: {exc}", file=sys.stderr)
                return 1

    try:
        report = screen_fasta("\n".join(chunks))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(_format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
