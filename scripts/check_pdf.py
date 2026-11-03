"""Build main.pdf and run layout evals on it. Run after every LaTeX change.

usage: python scripts/check_pdf.py [--no-build] [--pdf main.pdf]

Evals (exit code 1 if any fails):
  1. build      tectonic compiles without errors
  2. refs       no unresolved references or citations ("??" in the text)
  3. overlap    no two words on a page overlap each other (catches labels drawn over boxes in TikZ figures)
  4. bounds     no text runs into the page margin or off the page (catches figures wider than the text block)
  5. overfull   no overfull hbox wider than 10pt in the build log

Screenshots of every page that holds a figure or table are written to build/screens/page-NN.png
so the layout can be checked by eye as well.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "build" / "screens"
MARGIN_PT = 36  # 0.5 in: text closer than this to the page edge counts as out of bounds (layout uses 1 in)
OVERFULL_PT = 10.0


def build():
    r = subprocess.run(["tectonic", "--keep-logs", "main.tex"], cwd=ROOT, capture_output=True, text=True)
    log = (ROOT / "main.log").read_text(errors="ignore") if (ROOT / "main.log").exists() else r.stdout + r.stderr
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
    return r.returncode == 0, log


def overlaps(words, min_frac=0.3):
    """Pairs of words whose boxes overlap by more than min_frac of the smaller box."""
    hits = []
    boxes = [(pymupdf.Rect(w[:4]), w[4]) for w in words if w[4].strip()]
    boxes.sort(key=lambda b: b[0].y0)
    for i, (a, ta) in enumerate(boxes):
        for b, tb in boxes[i + 1:]:
            if b.y0 > a.y1:
                break
            inter = a & b
            if inter.is_empty:
                continue
            small = min(a.get_area(), b.get_area()) or 1
            if inter.get_area() / small > min_frac:
                hits.append((ta, tb))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--pdf", default=str(ROOT / "main.pdf"))
    args = ap.parse_args()

    results, log = {}, ""
    if not args.no_build:
        ok, log = build()
        results["build"] = (ok, "" if ok else "tectonic failed; see output above")

    doc = pymupdf.open(args.pdf)
    SCREENS.mkdir(parents=True, exist_ok=True)
    for old in SCREENS.glob("page-*.png"):
        old.unlink()

    unresolved, overlap_hits, bound_hits, shots = [], [], [], []
    for pno, page in enumerate(doc, 1):
        text = page.get_text()
        if "??" in text:
            unresolved.append(pno)
        words = page.get_text("words")
        for ta, tb in overlaps(words):
            overlap_hits.append(f"p{pno}: '{ta}' overlaps '{tb}'")
        W, H = page.rect.width, page.rect.height
        for w in words:
            if w[2] > W - MARGIN_PT or w[0] < MARGIN_PT:
                bound_hits.append(f"p{pno}: '{w[4]}' at x={w[0]:.0f}-{w[2]:.0f} (page width {W:.0f})")
        has_figure = page.get_images() or len(page.get_drawings()) > 20 or re.search(r"^(Figure|Table) \d+:", text, re.M)
        if has_figure:
            out = SCREENS / f"page-{pno:02d}.png"
            page.get_pixmap(dpi=110).save(out)
            shots.append(out.name)

    results["refs"] = (not unresolved, f"'??' on pages {unresolved}" if unresolved else "")
    results["overlap"] = (not overlap_hits, "; ".join(overlap_hits[:15]))
    results["bounds"] = (not bound_hits, "; ".join(bound_hits[:15]))
    if log:
        over = [float(m) for m in re.findall(r"Overfull \\hbox \((\d+(?:\.\d+)?)pt too wide\)", log)]
        lines = re.findall(r"Overfull \\hbox \((\d+(?:\.\d+)?)pt too wide\) (?:in paragraph |detected )?at lines? (\d+(?:--\d+)?)", log)
        big = [f"{float(o):.1f}pt at lines {ln}" for o, ln in lines if float(o) > OVERFULL_PT]
        results["overfull"] = (not big, "; ".join(big))

    print(f"PDF: {args.pdf} ({len(doc)} pages)")
    for name, (ok, msg) in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f": {msg}" if msg else ""))
    print(f"  screenshots ({len(shots)}): {SCREENS}/ -> {', '.join(shots)}")
    for f in ("main.log",):
        (ROOT / f).unlink(missing_ok=True)
    sys.exit(0 if all(ok for ok, _ in results.values()) else 1)


if __name__ == "__main__":
    main()
