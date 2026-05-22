# Anatomy Trainer

A personal anatomy word-bank and quiz app for studying structures by image.

## What is included

- Static website files: `index.html`, `styles.css`, and `app.js`
- The anatomy term bank at `data/wordbank.json`
- Authorized anatomy image assets in `assets/images/`
- A local importer at `scripts/import_wordbank.py`

The image assets are included for authorized personal study use.

## Run locally

```bash
python3 -m http.server 5173
```

Then open `http://127.0.0.1:5173/`.

## Rebuild the image word bank

The importer expects the PDF at:

```text
/Users/louisliu/Downloads/解剖單字表final.pdf
```

Install the parser dependency if needed, then run:

```bash
python3 -m pip install pypdf
python3 scripts/import_wordbank.py
```

This refreshes `data/wordbank.json` and downloads local images into `assets/images/`.

## Notes

This app is set up for personal study. If you publish or share a live version, use images you have permission to distribute.
