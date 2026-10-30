# Report builder

Generates `docs/Graduation_Report_DRAFT.docx` (US Letter, Times New Roman, Gulf Colleges template layout).

```bash
npm install docx          # once
node build.js report.docx # from this folder
```

- `content/*.js` hold the chapter text; `[[...]]` marks text the student must fill in (shown highlighted in yellow).
- `img/` holds the figures; `make_figs.py` and `aqte_aspects.py` regenerate the diagrams and charts
  (`python make_figs.py img`), and the `ui_*.png` screenshots come from the running platform with the synthetic demo data.
- Paragraphs containing Arabic are left-aligned (justified Arabic lines make LibreOffice's layout hang), and quoted
  Arabic inside English text uses straight quotes with left-to-right marks so it is not mirrored or reordered.
- Open the .docx in Word and update fields (Ctrl+A, then F9) to fill the table of contents and the lists of figures and tables.
