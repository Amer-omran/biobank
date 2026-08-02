# bioinformatic

Dependency-free **bioinformatics tools** for sequence analysis. Written in pure
Python — **no third-party dependencies** (standard library only) — so it runs on
any stock Python 3.9+ install, with no BLAST and no external database downloads.

The first tool is an **antimicrobial-resistance (AMR) screener** for FASTA
sequences.

## AMR screening

Scan a nucleotide or protein **FASTA** file for known antimicrobial-resistance
genes and report the resistance genes, drug classes and mechanisms detected.

The screener ships a curated **marker panel** (28 genes): for each gene it stores
a short conserved reference sub-sequence together with its drug class and
mechanism. Query sequences are screened with a BLAST-style seed-and-extend
approximate matcher:

- nucleotide queries are searched on **both strands** (plus + reverse-complement);
- protein queries are matched against the **translated** marker;
- a hit is reported when an aligned marker clears the identity and coverage
  thresholds (defaults: 90 % identity, 80 % coverage for nucleotides).

**Covered classes:** β-lactams, ESBLs and carbapenemases (`blaTEM`, `blaSHV`,
`blaCTX-M`, `blaKPC`, `blaNDM`, `blaOXA-48`, `blaVIM`, `blaIMP`, `blaCMY`),
methicillin (`mecA`), glycopeptides (`vanA`, `vanB`), polymyxins/colistin
(`mcr-1`), tetracyclines (`tetA`, `tetM`), sulfonamides (`sul1`, `sul2`),
aminoglycosides (`aac(6')-Ib`, `aph(3')-III`, `aadA1`), macrolides (`ermB`,
`mefA`), fluoroquinolones (`qnrS`, `qnrB`), phenicols (`catA1`, `catB3`, `floR`)
and trimethoprim (`dfrA1`).

> The bundled panel is a compact **demonstration** reference, not a substitute
> for comprehensive curated databases such as CARD, ResFinder or AMRFinderPlus.

## Usage

```bash
# from inside the project directory
python3 -m bioinformatic.amr isolate.fasta          # human-readable report
python3 -m bioinformatic.amr --json isolate.fasta   # machine-readable JSON
cat isolate.fasta | python3 -m bioinformatic.amr -  # read from stdin
```

### As a library

```python
from bioinformatic import screen_fasta

report = screen_fasta(">contig1\nATGGAATTGCCCAATATT...\n")
for hit in report["hits"]:
    print(hit["gene"], hit["drug_class"], hit["identity"], "%")
```

`screen_fasta(data, min_identity=0.90, min_coverage=0.80)` accepts a FASTA
`str` or `bytes` and returns a dict with:

- `sequences` — per-record results (`query`, `length`, `type`, `hits`);
- `hits` — every hit (`gene`, `drug_class`, `mechanism`, `identity`, `coverage`,
  `strand`, `start`, `end`, `via`);
- `summary` — counts plus the unique `resistance_genes` and `drug_classes`.

## Project layout

```
bioinformatic/
  __init__.py       package exports + metadata
  amr.py            FASTA parsing + AMR marker screening (stdlib only)
tests/
  test_amr.py       sequence-helper and screening tests
```

## Running the tests

```bash
python3 -m unittest discover -s tests -v
```
