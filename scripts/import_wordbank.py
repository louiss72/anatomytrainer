#!/usr/bin/env python3
"""Build a local anatomy word bank from the PDF and Kenhub atlas images."""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = Path("/Users/louisliu/Downloads/解剖單字表final.pdf")
DATA_DIR = ROOT / "data"
IMAGE_DIR = ROOT / "assets" / "images"

ALGOLIA_URL = "https://TVLY4HZXH3-dsn.algolia.net/1/indexes/production/query"
ALGOLIA_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 personal-anatomy-wordbank",
    "X-Algolia-Application-Id": "TVLY4HZXH3",
    "X-Algolia-API-Key": "ecd1b6edb1faf0f04f85467983a4ab18",
}
KENHUB_ROOT = "https://www.kenhub.com"


MAJOR_SECTIONS = ("頭部", "腹腔", "骨盆會陰", "下肢")
SUBSECTION_LABELS = (
    "咀嚼、表情肌",
    "眼外肌",
    "總頸動脈及分支",
    "靜脈",
    "靜脈竇",
    "眼內",
    "腦神經及分支",
    "神經節、腺體",
    "肌肉",
    "動脈",
    "神經",
    "臟器",
    "臟器、其他",
    "其他",
    "大腿肌肉",
    "小腿肌肉",
    "腳掌肌肉",
    "韌帶、膝蓋",
)

ABBREVIATIONS = {
    "ant.": "anterior",
    "post.": "posterior",
    "sup.": "superior",
    "inf.": "inferior",
    "mid.": "middle",
}

TYPE_SUFFIXES = {
    "m": "muscle",
    "a": "artery",
    "v": "vein",
    "n": "nerve",
    "br": "branch",
    "lig": "ligament",
}

TEXT_FIXES = {
    "spenopalatine": "sphenopalatine",
    "gastrodoudenal": "gastroduodenal",
    "pancreaticodoudenal": "pancreaticoduodenal",
    "pterygopalatal": "pterygopalatine",
    "panceatic": "pancreatic",
    "gluteul": "gluteal",
    "pets anserinus": "pes anserinus",
    "medium": "medius",
}

GENERIC_CONTEXT_TERMS = (
    "anterior branch",
    "posterior branch",
    "ascending branch",
    "transverse branch",
    "descending branch",
    "deep branch",
    "superficial branch",
    "temporal branch",
    "zygomatic branch",
    "buccal branch",
    "marginal mandibular branch",
    "cervical branch",
    "genital branch",
    "femoral branch",
    "long head",
    "short head",
    "lateral head",
    "medial head",
)


@dataclass
class ParsedItem:
    term: str
    raw: str
    region: str
    category: str
    page: int
    parent: str | None


def request_json(url: str, payload: dict, headers: dict[str, str], retries: int = 3) -> dict:
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    return {}


def request_text(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ALGOLIA_HEADERS["User-Agent"]})
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    return ""


def download_file(url: str, path: Path, retries: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ALGOLIA_HEADERS["User-Agent"]})
            with urllib.request.urlopen(req, timeout=45) as response:
                path.write_bytes(response.read())
            return
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))


def normalized(value: str) -> str:
    value = html.unescape(value or "").lower()
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def source_title(hit: dict) -> str:
    return hit.get("title") or hit.get("name") or ""


def hit_score(hit: dict, query: str) -> tuple[int, int]:
    title = normalized(source_title(hit))
    name = normalized(hit.get("name", ""))
    latin = normalized(hit.get("latin_name", ""))
    synonyms = " ".join(normalized(s) for s in hit.get("synonyms", []))
    query_norm = normalized(query)
    query_no_type = re.sub(r"\b(muscle|artery|vein|nerve|branch)\b", "", query_norm)
    query_no_type = re.sub(r"\s+", " ", query_no_type).strip()

    score = 0
    if hit.get("locale") == "en":
        score += 100
    if hit.get("media_type_slug") == "learnable" and hit.get("has_image"):
        score += 70
    if hit.get("media_type_slug") == "articles" and hit.get("thumbnail"):
        score += 25
    haystack = f"{title} {name} {latin} {synonyms}"
    if query_norm and query_norm in haystack:
        score += 45
    if query_no_type and query_no_type in haystack:
        score += 25
    if title == query_norm or name == query_norm:
        score += 80
    return (score, -len(title))


def kenhub_search(query: str) -> dict | None:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "hitsPerPage": 10,
            "attributesToRetrieve": json.dumps(
                [
                    "locale",
                    "slug",
                    "title",
                    "name",
                    "type",
                    "latin_name",
                    "synonyms",
                    "media_type",
                    "media_type_slug",
                    "url",
                    "thumbnail",
                    "has_image",
                    "breadcrumbs",
                ]
            ),
        }
    )
    payload = {"params": params}
    result = request_json(ALGOLIA_URL, payload, ALGOLIA_HEADERS)
    hits = [hit for hit in result.get("hits", []) if hit.get("locale") == "en"]
    hits = [hit for hit in hits if hit.get("media_type_slug") in {"learnable", "articles"}]
    if not hits:
        return None
    hits.sort(key=lambda hit: hit_score(hit, query), reverse=True)
    return hits[0]


def absolutize(url: str) -> str:
    if url.startswith("http"):
        return url
    return f"{KENHUB_ROOT}{url}"


def extract_image_url(page_html: str) -> str | None:
    og = re.search(r"<meta\s+content=['\"]([^'\"]+)['\"]\s+property=['\"]og:image['\"]", page_html)
    if og:
        return html.unescape(og.group(1))
    og = re.search(r"<meta\s+property=['\"]og:image['\"]\s+content=['\"]([^'\"]+)['\"]", page_html)
    if og:
        return html.unescape(og.group(1))
    gallery = re.search(r"data-images='([^']+)'", page_html)
    if gallery:
        try:
            images = json.loads(html.unescape(gallery.group(1)))
            for item in images:
                if item.get("image_type") == "illustration" and item.get("image_url"):
                    return item["image_url"]
            for item in images:
                if item.get("image_url"):
                    return item["image_url"]
        except Exception:
            return None
    return None


def slugify(value: str) -> str:
    value = normalized(value)
    value = re.sub(r"\b(of|the)\b", "", value)
    value = re.sub(r"\s+", "-", value).strip("-")
    return value[:90] or "term"


def strip_comments(line: str) -> str:
    line = re.sub(r"\(\s*\d+[^)]*\)", "", line)
    line = re.sub(r"（[^）]*）", "", line)
    line = re.sub(r"（[^)]*\)", "", line)
    line = re.sub(r"（.*$", "", line)
    return re.sub(r"\s+", " ", line).strip()


def apply_text_fixes(value: str) -> str:
    fixed = value
    for wrong, right in TEXT_FIXES.items():
        fixed = re.sub(rf"\b{re.escape(wrong)}\b", right, fixed, flags=re.IGNORECASE)
    return fixed


def normalize_term_syntax(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s*/\s*", "/", value)
    value = re.sub(r"\s+", " ", value)
    value = apply_text_fixes(value)
    for short, long in ABBREVIATIONS.items():
        value = re.sub(rf"\b{re.escape(short)}", long, value, flags=re.IGNORECASE)
    value = re.sub(r"\bR/L\b", "right/left", value, flags=re.IGNORECASE)
    value = re.sub(r"\bR\b(?=/)", "right", value)
    value = re.sub(r"(?<=/)\s*L\b", "left", value)
    value = re.sub(r"\bL\b(?=\s+(renal|testicular|gastric))", "left", value)
    value = re.sub(r"\bR\b(?=\s+(renal|testicular|gastric))", "right", value)
    value = re.sub(r"\bAI/AS/PI/PS\s+pancreaticoduodenal\s+a\.?", "anterior inferior/anterior superior/posterior inferior/posterior superior pancreaticoduodenal a.", value, flags=re.IGNORECASE)
    value = re.sub(r"\bseminal vesical\b", "seminal vesicle", value, flags=re.IGNORECASE)
    value = re.sub(r"\bn\.\s+to\s+", "nerve to ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bn\.\s+of\b", "nerve of", value, flags=re.IGNORECASE)
    value = re.sub(r"\bbr\.\s+of\b", "branch of", value, flags=re.IGNORECASE)
    return value


def type_suffix(value: str) -> tuple[str, str | None]:
    match = re.search(r"\b(m|a|v|n|br|lig)\.?\s*$", value, re.IGNORECASE)
    if not match:
        return value.strip(), None
    suffix = TYPE_SUFFIXES[match.group(1).lower()]
    return value[: match.start()].strip(), suffix


def expand_slash_tokens(value: str) -> list[str]:
    words = value.split()
    results = [words]
    for idx, word in enumerate(words):
        if "/" not in word:
            continue
        alternatives = [part.strip() for part in word.split("/") if part.strip()]
        if not alternatives:
            continue
        expanded: list[list[str]] = []
        for current in results:
            for alternative in alternatives:
                copy = list(current)
                copy[idx] = alternative
                expanded.append(copy)
        results = expanded
    return [" ".join(parts) for parts in results]


def parent_context(parent: str | None) -> str | None:
    if not parent:
        return None
    parent = re.sub(r"\s+", " ", parent).strip()
    if parent in {"posterior branch", "anterior branch"}:
        return None
    return parent


def qualify_term(term: str, parent: str | None) -> str:
    term = re.sub(r"\s+", " ", term).strip()
    context = parent_context(parent)
    if context and normalized(term) in GENERIC_CONTEXT_TERMS:
        return f"{term} of {context}"
    if term == "superficial dorsal vein":
        return "superficial dorsal vein of penis"
    if term == "deep dorsal vein":
        return "deep dorsal vein of penis"
    if term == "round ligament" and context == "uterus":
        return "round ligament of uterus"
    return term


def expand_term(raw_value: str, parent: str | None) -> list[str]:
    raw_value = strip_comments(raw_value)
    raw_value = raw_value.strip(" .;:")
    if not raw_value:
        return []
    if re.search(r"\bAI\s*/\s*AS\s*/\s*PI\s*/\s*PS\s+pancreaticodou?denal\s+a\.?", raw_value, flags=re.IGNORECASE):
        return [
            "anterior inferior pancreaticoduodenal artery",
            "anterior superior pancreaticoduodenal artery",
            "posterior inferior pancreaticoduodenal artery",
            "posterior superior pancreaticoduodenal artery",
        ]
    if raw_value in {"S1", "S2", "S3"}:
        return [f"{raw_value} spinal nerve"]

    parenthetical_terms: list[str] = []
    if "(duct)" in raw_value:
        raw_value = raw_value.replace("(duct)", "")
        parenthetical_terms.append(raw_value.replace("gland", "duct").strip())
    branch_match = re.search(r"\((anterior|posterior|ant\.|post\.)\s+(anterior|posterior|ant\.|post\.)?\s*br\.\)", raw_value, flags=re.IGNORECASE)
    if branch_match:
        raw_value = re.sub(r"\([^)]*br\.\)", "", raw_value, flags=re.IGNORECASE).strip()

    value = normalize_term_syntax(raw_value)
    if value.startswith("sub(") and value.endswith("gland"):
        return ["submandibular gland", "sublingual gland"]
    if re.search(r"\bvagina\s+anterior/posterior\s+fornix\b", value):
        return ["anterior fornix of vagina", "posterior fornix of vagina"]

    base, suffix = type_suffix(value)
    expanded = expand_slash_tokens(base)
    terms: list[str] = []
    for item in expanded + parenthetical_terms:
        item = normalize_term_syntax(item)
        item = item.strip(" .;:")
        if not item:
            continue
        if suffix:
            item = f"{item} {suffix}"
        item = re.sub(r"\bbranch branch\b", "branch", item)
        item = re.sub(r"\bartery artery\b", "artery", item)
        item = re.sub(r"\bvein vein\b", "vein", item)
        item = re.sub(r"\bnerve nerve\b", "nerve", item)
        item = qualify_term(item, parent)
        terms.append(item)

    if branch_match:
        for branch in ("anterior branch", "posterior branch"):
            terms.append(qualify_term(branch, terms[0] if terms else parent))

    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = normalized(term)
        if key and key not in seen:
            seen.add(key)
            deduped.append(term)
    return deduped


def update_labels(line: str, current_region: str, current_category: str, in_notes: bool) -> tuple[str, str, bool, str]:
    clean = line.strip()
    for section in MAJOR_SECTIONS:
        if clean == section or clean.startswith(f"{section} "):
            current_region = section
            in_notes = False
            clean = clean[len(section) :].strip()
            break
    if clean.startswith("藍字"):
        in_notes = True
        clean = clean[2:].strip()
    for label in SUBSECTION_LABELS:
        if clean == label or clean.startswith(f"{label} "):
            current_category = label
            clean = clean[len(label) :].strip()
            break
    return current_region, current_category, in_notes, clean


def extract_pdf_text(pdf_path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(pdf_path))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        pages.append((index, page.extract_text() or ""))
    return pages


def parse_terms(pdf_path: Path) -> tuple[list[ParsedItem], str]:
    pages = extract_pdf_text(pdf_path)
    text = "\n\n".join(f"---PAGE {page}---\n{body}" for page, body in pages)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "pdf_text.txt").write_text(text, encoding="utf-8")

    current_region = "General"
    current_category = "Terms"
    in_notes = False
    stack: list[tuple[int, str]] = []
    items: list[ParsedItem] = []
    seen: set[tuple[str, str]] = set()

    for page_number, page_text in pages:
        for original_line in page_text.splitlines():
            if not original_line.strip():
                continue
            if original_line.strip().startswith("最後更新"):
                continue
            if re.fullmatch(r"\d+", original_line.strip()):
                continue

            indent = len(original_line) - len(original_line.lstrip(" "))
            current_region, current_category, in_notes, line = update_labels(
                original_line, current_region, current_category, in_notes
            )
            if in_notes or not line:
                continue
            if not re.search(r"\d+\.", line):
                continue

            match = re.search(r"\d+\.\s*(.*)$", line)
            if not match:
                continue
            raw_item = match.group(1).strip()
            if not raw_item:
                continue

            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1] if stack else None
            expanded_terms = expand_term(raw_item, parent)
            if expanded_terms:
                stack.append((indent, expanded_terms[0]))
            for term in expanded_terms:
                key = (normalized(term), current_region)
                if key in seen:
                    continue
                seen.add(key)
                items.append(
                    ParsedItem(
                        term=term,
                        raw=raw_item,
                        region=current_region,
                        category=current_category,
                        page=page_number,
                        parent=parent,
                    )
                )

    return items, text


def image_extension(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"


def build_wordbank(items: Iterable[ParsedItem]) -> tuple[list[dict], list[dict]]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    existing_entries: dict[str, dict] = {}
    existing_path = DATA_DIR / "wordbank.json"
    if existing_path.exists():
        try:
            for entry in json.loads(existing_path.read_text(encoding="utf-8")):
                existing_entries[normalized(entry.get("term", ""))] = entry
        except Exception:
            existing_entries = {}

    wordbank: list[dict] = []
    failures: list[dict] = []

    for index, item in enumerate(items, start=1):
        entry = {
            "id": slugify(item.term),
            "term": item.term,
            "raw": item.raw,
            "region": item.region,
            "category": item.category,
            "page": item.page,
            "image": None,
            "status": "pending",
        }

        cached = existing_entries.get(normalized(item.term))
        if cached and cached.get("status") == "downloaded" and cached.get("image"):
            cached_image = ROOT / cached["image"]
            if cached_image.exists() and cached_image.stat().st_size > 0:
                entry.update(
                    {
                        "image": cached.get("image"),
                        "status": "downloaded",
                    }
                )
                wordbank.append(entry)
                print(f"[{index:03}] reused: {item.term}", flush=True)
                continue

        try:
            hit = kenhub_search(item.term)
            if not hit:
                entry["status"] = "no-match"
                failures.append({"term": item.term, "reason": "No Kenhub search hit"})
                wordbank.append(entry)
                print(f"[{index:03}] no match: {item.term}", flush=True)
                continue

            source_url = absolutize(hit["url"])
            page_html = request_text(source_url)
            image_url = extract_image_url(page_html)
            if not image_url and hit.get("thumbnail"):
                image_url = absolutize(hit["thumbnail"])
            if not image_url:
                entry["status"] = "no-image"
                failures.append({"term": item.term, "reason": "No image on matched Kenhub page", "source_url": source_url})
                wordbank.append(entry)
                print(f"[{index:03}] no image: {item.term}", flush=True)
                continue

            image_url = absolutize(image_url)
            filename = f"{entry['id']}{image_extension(image_url)}"
            image_path = IMAGE_DIR / filename
            if not image_path.exists() or image_path.stat().st_size == 0:
                download_file(image_url, image_path)

            entry.update(
                {
                    "image": str(Path("assets/images") / filename),
                    "status": "downloaded",
                }
            )
            wordbank.append(entry)
            print(f"[{index:03}] downloaded: {item.term}", flush=True)
            time.sleep(0.08)
        except Exception as exc:
            entry["status"] = "error"
            failures.append({"term": item.term, "reason": str(exc)})
            wordbank.append(entry)
            print(f"[{index:03}] error: {item.term}: {exc}", flush=True)

    return wordbank, failures


def main() -> int:
    if not PDF_PATH.exists():
        print(f"PDF not found: {PDF_PATH}", file=sys.stderr)
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    items, _ = parse_terms(PDF_PATH)
    preview = [item.__dict__ for item in items]
    (DATA_DIR / "parsed_terms.json").write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Parsed {len(items)} terms from {PDF_PATH.name}", flush=True)

    wordbank, failures = build_wordbank(items)
    report = {
        "pdf": str(PDF_PATH),
        "total_terms": len(wordbank),
        "downloaded": sum(1 for item in wordbank if item["status"] == "downloaded"),
        "not_downloaded": sum(1 for item in wordbank if item["status"] != "downloaded"),
        "failures": failures,
    }
    (DATA_DIR / "wordbank.json").write_text(json.dumps(wordbank, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "import_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
