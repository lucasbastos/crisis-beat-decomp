#!/usr/bin/env python3
"""Measure reverse-engineering progress and write the dashboard's data files.

  python tools/progress.py out/progress

Reads disc/DATA.0, notes/*.md, notes/symbols.tsv, out/functions.tsv (export it
first with tools/ghidra_scripts/ExportFunctions.java) and the git history.
Writes entries.json, functions.json, formats.json, milestones.json and
questions.json: plain row lists, no game content.

Byte status:
  decoded     we can convert it to a usable file (images)
  identified  we know what it is (code, sound banks, offset tables, padding)
  unknown     not worked out yet
"""
import hashlib
import json
import re
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import subarc_list  # noqa: E402
import tim2png  # noqa: E402
import unpack  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OVERLAYS = {16: "in-game engine", 17: "post-select cutscene", 19: "not seen yet",
            20: "between-scenes screen", 21: "title, menus, character select", 24: "not seen yet"}
SCENE_FIRST, SCENE_LAST = 25, 2005


def is_code(blob):
    """Scene code: a small u32 id, then a MIPS `addiu sp, sp, -N` prologue or a
    table of pointers into the slot-2 load area (0x8015xxxx)."""
    if len(blob) < 8 or struct.unpack_from("<I", blob, 0)[0] >= 0x100:
        return False
    second = struct.unpack_from("<I", blob, 4)[0]
    return second >> 16 == 0x27BD or second >> 16 == 0x8015


def classify_sections(blob, secs, seen):
    """Split a sub-archive into decoded / identified / unknown bytes."""
    dec = ident = unk = images = new = 0
    ident += secs[0][0]  # the offset table itself
    for a, b in secs:
        s = blob[a:b]
        if s[:4] == b"pBAV" or not any(s[:16]):
            ident += b - a
            continue
        try:
            res = unpack.unpack_any(s)
        except Exception:
            res = []
        tims = [r for r in res if tim2png.parse_tim(r, 0)]
        if tims:
            dec += b - a
            images += len(tims)
            for r in tims:
                h = hashlib.sha1(r).digest()
                new += h not in seen
                seen.add(h)
        else:
            unk += b - a
    return dec, ident, unk, images, new


AREA_DECODED_LISTS = {0}         # list 0: compressed textures (Res_LoadTextures)
AREA_IDENTIFIED_LISTS = {2, 3}   # lists 2/3: VAB bodies / headers (Res_LoadSoundBanks)


def classify_area_block(blob):
    """Bytes of an area resource block (from 0x4000) as decoded / identified / unknown.
    Header and lists are identified; data a list points to takes that list's status and
    runs to the next known start. Data no list points to directly is unknown."""
    lists = unpack.area_lists(blob)
    size = len(blob) - unpack.AREA_CODE_SIZE
    owner = {0: "identified"}  # the 16-slot table
    for k, (head, end, targets) in enumerate(lists):
        owner[head] = "identified"
        owner.setdefault(end, "unknown")  # whatever follows a list until the next start
        status = ("decoded" if k in AREA_DECODED_LISTS else
                  "identified" if k in AREA_IDENTIFIED_LISTS else "unknown")
        for t in targets:
            if owner.get(t) in (None, "unknown"):
                owner[t] = status
    owner.setdefault(0x40, "decoded")
    starts = sorted(o for o in owner if o < size)
    totals = {"decoded": 0, "identified": 0, "unknown": 0}
    for a, b in zip(starts, starts[1:] + [size]):
        totals[owner[a]] += b - a
    return totals["decoded"], totals["identified"], totals["unknown"]


def entry_rows(data):
    entries = subarc_list.pack_entries(data)
    seen, rows = set(), []
    for e, (start, end) in enumerate(entries):
        blob = data[start:end]
        size = len(blob)
        dec = ident = unk = images = new = 0
        if size == 0x800 and not any(blob):
            kind, ident = "Empty slot", size
        elif e in OVERLAYS:
            kind = "Code overlay"
            tims = list(tim2png.scan(blob))
            dec = sum(t["end"] - off for off, t in tims)
            ident, images = size - dec, len(tims)
            for off, t in tims:
                h = hashlib.sha1(blob[off:t["end"]]).digest()
                new += h not in seen
                seen.add(h)
        elif blob[:4] == b"pBAV":
            kind, ident = "Sound bank", size
        elif tim2png.parse_tim(blob, 0):
            kind = "Image set"
            tims = list(tim2png.scan(blob))
            dec, images = sum(t["end"] - off for off, t in tims), len(tims)
            ident = size - dec
            for off, t in tims:
                h = hashlib.sha1(blob[off:t["end"]]).digest()
                new += h not in seen
                seen.add(h)
        elif SCENE_FIRST <= e <= SCENE_LAST and (unpack.area_sections(blob) or is_code(blob)):
            # Area code can start with a pointer table instead of a prologue, so the
            # resource block is the stronger test; story scenes have code but no block.
            area = unpack.area_sections(blob)
            if area:
                kind = "Area code + resources"
                s0a, s0b = area[0]
                try:
                    res = unpack.unpack_packed(blob[s0a:s0b])
                except Exception:
                    res = []
                tims = [r for r in res if tim2png.parse_tim(r, 0)]
                images = len(tims)
                for r in tims:
                    h = hashlib.sha1(r).digest()
                    new += h not in seen
                    seen.add(h)
                dec, ident, unk = classify_area_block(blob)
                ident += unpack.AREA_CODE_SIZE  # the scene code itself
            else:
                kind, ident = "Story scene code", size
        else:
            secs = subarc_list.sections(blob)
            if secs:
                if e < SCENE_FIRST:
                    kind = "Team data"
                elif e <= SCENE_LAST:
                    kind = "Area data (sound)"
                else:
                    kind = "Scene bank"
                dec, ident, unk, images, new = classify_sections(blob, secs, seen)
                tail = size - secs[-1][1]
                unk += tail
            elif SCENE_FIRST <= e <= SCENE_LAST and struct.unpack_from("<I", blob, 0)[0] < 0x100:
                # Story-scene slots (e.g. 372, Kenneth's intro) that start with an id and
                # a table of small numbers instead of code: loaded as scene code, layout unknown.
                kind, unk = "Story scene (layout unknown)", size
            else:
                kind = "Team data" if e < SCENE_FIRST else "Unknown"
                unk = size
        status = ("unknown" if unk == size else "decoded" if dec and not unk
                  else "partial" if unk else "identified" if not dec else "decoded")
        rows.append({"entry": e, "kind": kind, "status": status, "bytes": size,
                     "decoded": dec, "identified": ident, "unknown": unk,
                     "images": images, "unique_images": new})
    return rows


def function_rows():
    ours = set()
    for line in (ROOT / "notes/symbols.tsv").read_text().splitlines():
        if line and not line.startswith("#"):
            ours.add(line.split("\t")[1])
    regions = {}
    for line in (ROOT / "out/functions.tsv").read_text().splitlines():
        addr, _, name, _ = line.split("\t")
        if addr.startswith("2000"):
            continue  # GTE macro placeholders, not code
        region = "Overlay 16 (in-game engine)" if addr.startswith("ovl16::") else "Main executable"
        r = regions.setdefault(region, {"region": region, "total": 0, "named_by_us": 0,
                                        "named_by_signature": 0, "unnamed": 0})
        r["total"] += 1
        if name in ours:
            r["named_by_us"] += 1
        elif name.startswith("FUN_"):
            r["unnamed"] += 1
        else:
            r["named_by_signature"] += 1
    return list(regions.values())


FORMATS = [
    ("DATA.0 pack table", "Containers", "understood", "u32 offset table, 2037 entries"),
    ("Sub-archives", "Containers", "understood", "same table layout inside entries"),
    ("Area resource block", "Containers", "understood", "16 offset lists at 0x4000, each ending in 0xE5E5E5E5"),
    ("Area list 0: textures", "Graphics", "understood", "compressed TIMs, uploaded by Res_LoadTextures"),
    ("Area lists 2/3: sound banks", "Sound", "understood", "VAB bodies / headers, opened by Sound_OpenVab"),
    ("Area list 1: placement records", "Game logic", "partial", "10-byte records (5 x s16), 0xE5E5 ends"),
    ("Area lists 4/6: per-object resources", "Game logic", "partial", "indexed by object type, relocated on demand"),
    ("Area lists 5/7-15", "Game logic", "unknown", "consumers named Res_SetupList*, formats not read yet"),
    ("Sprite frame tables", "Graphics", "unknown", "4-byte records reached through list 4 descriptors"),
    ("Scene numbering", "Game logic", "understood", "base + scene*2, one base per scenario"),
    ("Scenarios (teams)", "Game logic", "understood", "0 = Eiji + Julia, 1 = Kenneth + Yan"),
    ("Scenario groups 2-9", "Game logic", "unknown", "55 scenes each, no story scenes"),
    ("Code overlays", "Code", "understood", "6 overlays at 0x80064668, entry points known"),
    ("Area code overlays", "Code", "understood", "slot 2 at 0x80158000"),
    ("Compression: LZ 0x73 / 0x74", "Compression", "understood", "verified on 79,581 streams"),
    ("Compression: 0x70 / 0x71 / 0x72", "Compression", "understood", "mask fill, RLE, interleave"),
    ("Compression: 0x20 / 0x30 / 0x31 / 0x40 / 0xFF", "Compression", "understood", "LZ, RLE, fill, stored"),
    ("Compression: 0x14", "Compression", "partial", "4-bit table; not used in DATA.0, unverified"),
    ("TIM images", "Graphics", "understood", "converted to PNG"),
    ("Texture animation table", "Graphics", "partial", "LoadImage / MoveImage per frame in overlay 16"),
    ("Sprite tables (04 00 02 00)", "Graphics", "unknown", "next to the images in team data"),
    ("0xE5E5E5E5 marker", "Containers", "understood", "end of an offset list (0xE5E5 ends s16 record lists)"),
    ("VAB sound banks", "Sound", "understood", "standard PsyQ format, not converted yet"),
    ("XA music / STR movies", "Sound", "understood", "standard formats, use jPSXdec"),
]


def milestone_rows():
    log = subprocess.run(["git", "-C", str(ROOT), "log", "--reverse", "--date=iso-strict",
                          "--format=%ad%x09%h%x09%s"], capture_output=True, text=True, check=True)
    return [dict(zip(("date", "commit", "title"), line.split("\t", 2)))
            for line in log.stdout.splitlines()]


def question_rows():
    rows = []
    for path in sorted((ROOT / "notes").glob("*.md")):
        for m in re.finditer(r"^- \[( |x)\] (.+?)(?=\n(?:- \[|\S|$)|\Z)",
                             path.read_text(), re.M | re.S):
            text = " ".join(m.group(2).split())
            rows.append({"notes": path.name, "question": text, "done": m.group(1) == "x"})
    return rows


DASHBOARD_URL = "https://claude.ai/artifact/HJouFMXmC3fZy2iSKUEBcX"
README_START, README_END = "<!-- progress:start -->", "<!-- progress:end -->"


def readme_block(ds, when):
    """Markdown status block for README.md; same figures as the dashboard."""
    e, f, fm, q = ds["entries"], ds["functions"], ds["formats"], ds["questions"]
    total = sum(r["bytes"] for r in e)
    dec = sum(r["decoded"] for r in e)
    ident = sum(r["identified"] for r in e)
    mib = lambda b: f"{b / 2**20:,.1f} MB"
    unknown_by_kind = {}
    for r in e:
        unknown_by_kind[r["kind"]] = unknown_by_kind.get(r["kind"], 0) + r["unknown"]
    big_kind, big_bytes = max(unknown_by_kind.items(), key=lambda kv: kv[1])
    mapped = sum("unknown" not in r["kind"].lower() for r in e)
    fn_total = sum(r["total"] for r in f)
    fn_us = sum(r["named_by_us"] for r in f)
    fn_named = fn_us + sum(r["named_by_signature"] for r in f)
    count = lambda s: sum(x["status"] == s for x in fm)
    done = sum(x["done"] for x in q)
    last = ds["milestones"][-1] if ds["milestones"] else {"commit": "none", "title": ""}
    return "\n".join([
        README_START,
        f"Status as of {when} (after commit `{last['commit']}`). "
        f"Updated on every commit by `tools/hooks/pre-commit`; full charts on the "
        f"[progress dashboard]({DASHBOARD_URL}) (private until shared).",
        "",
        "| Measure | Now |",
        "|---|---|",
        f"| DATA.0 bytes understood | **{(dec + ident) / total:.1%}** ({mib(dec + ident)} of {mib(total)}) |",
        f"| DATA.0 bytes decoded to files | {dec / total:.1%} ({mib(dec)}) |",
        f"| Entries mapped | {mapped:,} of {len(e):,} |",
        f"| Unique images extracted | {sum(r['unique_images'] for r in e):,} ({sum(r['images'] for r in e):,} with copies) |",
        f"| Functions named | {fn_named:,} of {fn_total:,} ({fn_us} by us) |",
        f"| Formats understood | {count('understood')} of {len(fm)} ({count('partial')} partly) |",
        f"| Questions answered | {done} of {len(q)} |",
        f"| Biggest unknown | {big_kind}: {mib(big_bytes)} |",
        README_END,
    ])


def update_readme(path, block):
    text = path.read_text()
    if README_START in text and README_END in text:
        head, rest = text.split(README_START, 1)
        _, tail = rest.split(README_END, 1)
        new = head + block + tail
    else:
        raise SystemExit(f"{path}: add {README_START} and {README_END} markers first")
    if new != text:
        path.write_text(new)
        return True
    return False


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="?", default="out/progress")
    ap.add_argument("--readme", metavar="README.md", help="also rewrite the status block in this file")
    args = ap.parse_args()

    if not (ROOT / "disc/DATA.0").exists():
        raise SystemExit("disc/DATA.0 not found: extract the disc first (tools/extract_disc.py)")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = (ROOT / "disc/DATA.0").read_bytes()
    datasets = {
        "entries": entry_rows(data),
        "functions": function_rows(),
        "formats": [dict(zip(("format", "area", "status", "note"), f)) for f in FORMATS],
        "milestones": milestone_rows(),
        "questions": question_rows(),
    }
    for name, rows in datasets.items():
        (out / f"{name}.json").write_text(json.dumps(rows, indent=0))
        print(f"{name}: {len(rows)} rows")
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if args.readme:
        changed = update_readme(Path(args.readme), readme_block(datasets, when))
        print(f"{args.readme}: {'updated' if changed else 'unchanged'}")
    print("generated", when)


if __name__ == "__main__":
    main()
