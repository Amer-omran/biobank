"""bioinformatic – dependency-free sequence-analysis tools.

Currently provides antimicrobial-resistance (AMR) screening of FASTA
sequences (see :mod:`bioinformatic.amr`). Standard library only — runs on any
stock Python 3.9+ install with no third-party packages, BLAST or external
database downloads.
"""

from .amr import (  # noqa: F401
    AMR_PANEL,
    panel_summary,
    parse_fasta,
    reverse_complement,
    screen_fasta,
    screen_sequence,
    translate,
)

__version__ = "0.1.0"

__all__ = [
    "AMR_PANEL",
    "panel_summary",
    "parse_fasta",
    "reverse_complement",
    "screen_fasta",
    "screen_sequence",
    "translate",
]
