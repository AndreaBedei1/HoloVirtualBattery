"""Rendered-UI audit: screenshots and measurable checks at several viewport widths.

Usage::

    python tools/ui_audit.py http://127.0.0.1:8765/ --out docs/ui_review/screenshots/final \
        --routes overview robot mission run results compare library evidence

For every route and width it saves a full-page PNG and records, from the rendered DOM:
horizontal page overflow, elements clipped beyond the viewport, text smaller than 12 px,
text whose WCAG contrast ratio is below 4.5:1 (3:1 for large text), interactive elements
smaller than 24 x 24 px, inputs without an accessible name and buttons without one.
The checks are measurements, not a substitute for looking at the screenshots.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

WIDTHS = (320, 360, 390, 768, 1024, 1440, 1920)
HEIGHTS = {320: 700, 360: 760, 390: 844, 768: 1024, 1024: 768, 1440: 900, 1920: 1080}

AUDIT_JS = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const out = {overflow_px: Math.max(0, document.documentElement.scrollWidth - vw),
               clipped: [], small_text: [], low_contrast: [], small_targets: [],
               unnamed_inputs: [], unnamed_buttons: []};
  const lum = (c) => { const m = c.match(/[\d.]+/g); if (!m) return null;
    const [r, g, b] = m.slice(0, 3).map(Number).map(v => { v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const alpha = (c) => { const m = c.match(/[\d.]+/g); return m && m.length > 3 ? Number(m[3]) : 1; };
  const bg = (el) => { for (let e = el; e; e = e.parentElement) {
      const c = getComputedStyle(e).backgroundColor; if (alpha(c) > 0.5) return c; }
    return 'rgb(255,255,255)'; };
  const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const label = (el) => (el.textContent || '').trim().slice(0, 60);
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 && getComputedStyle(el).position !== 'fixed') {
      let scroller = false;
      for (let p = el.parentElement; p; p = p.parentElement) {
        const ox = getComputedStyle(p).overflowX; if (ox === 'auto' || ox === 'scroll') { scroller = true; break; } }
      if (!scroller) out.clipped.push(el.tagName + '.' + el.className + ' ' + label(el));
    }
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (own) {
      const s = getComputedStyle(el); const size = parseFloat(s.fontSize);
      if (size < 12) out.small_text.push(size + 'px ' + label(el));
      const a = lum(s.color), b = lum(bg(el));
      if (a !== null && b !== null) {
        const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        const large = size >= 24 || (size >= 18.66 && Number(s.fontWeight) >= 700);
        if (ratio < (large ? 3 : 4.5)) out.low_contrast.push(ratio.toFixed(2) + ' ' + label(el));
      }
    }
    if (el.matches('a[href],button,input,select,textarea,[role=button],summary') && !el.closest('.sr-only')) {
      if ((r.width < 24 || r.height < 24) && !el.matches('input[type=checkbox],input[type=radio]'))
        out.small_targets.push(Math.round(r.width) + 'x' + Math.round(r.height) + ' ' + el.tagName + ' ' + label(el));
    }
    if (el.matches('input:not([type=hidden]),select,textarea')) {
      const named = el.labels?.length || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.title;
      if (!named) out.unnamed_inputs.push(el.tagName + '#' + el.id + ' ' + el.name);
    }
    if (el.matches('button,[role=button]') && !label(el) && !el.getAttribute('aria-label') && !el.title)
      out.unnamed_buttons.push(el.outerHTML.slice(0, 80));
  }
  for (const k of Object.keys(out)) if (Array.isArray(out[k])) out[k] = [...new Set(out[k])].slice(0, 25);
  return out;
}
"""


def audit(url, out_dir, routes, widths=WIDTHS, wait_ms=1500, prefix=""):
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in widths:
            page = browser.new_page(viewport={"width": width, "height": HEIGHTS.get(width, 900)})
            for route in routes:
                target = url if not route else f"{url.rstrip('/')}/#/{route}"
                page.goto(target)
                page.wait_for_timeout(wait_ms)
                name = f"{prefix}{route or 'home'}_{width}"
                page.screenshot(path=str(out_dir / f"{name}.png"), full_page=True)
                results[name] = page.evaluate(AUDIT_JS)
            page.close()
        browser.close()
    (out_dir / "audit.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    return results


def summarise(results):
    rows = []
    for name, r in results.items():
        rows.append(
            f"{name}: overflow {r['overflow_px']} px, clipped {len(r['clipped'])}, "
            f"small text {len(r['small_text'])}, low contrast {len(r['low_contrast'])}, "
            f"small targets {len(r['small_targets'])}, unnamed inputs {len(r['unnamed_inputs'])}"
        )
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--routes", nargs="*", default=[""])
    parser.add_argument("--widths", nargs="*", type=int, default=list(WIDTHS))
    parser.add_argument("--wait-ms", type=int, default=1500)
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()
    print(summarise(audit(args.url, args.out, args.routes, args.widths, args.wait_ms, args.prefix)))


if __name__ == "__main__":
    main()
