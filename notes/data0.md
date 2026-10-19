# DATA.0 / GALLERY.0 pack format

Status: **table layout confirmed**; entry contents mostly unknown.

## Container

```
u32 offsets[N]   // little-endian byte offsets, each a multiple of 0x800
                 // offsets[0] == table size (DATA.0: 0x2000, GALLERY.0: 0x800)
                 // unused slots are 0
<entries>        // entry i = [offsets[i], offsets[i+1]); last runs to EOF
```

- DATA.0: 2037 entries, 0x1181D800 bytes. GALLERY.0: 14 entries.
- No names. The game must refer to entries by index (still to confirm in the exe).
- Offsets are byte offsets but always sector aligned, so the loader probably
  turns them into a CD sector number with `offset / 0x800`.

List or extract with `python tools/pack_list.py disc/DATA.0 [--extract out/DATA]`.

## Entry types seen (first bytes)

| Head | Count | Guess |
|---|---|---|
| `00 00 00 00 ...` (0x800 long) | ~1001 | empty / reserved slot |
| `10 00 00 00 09 00 00 00` | ~373 | **TIM image**, 8bpp with CLUT. All of GALLERY.0 |
| `00 04 00 00 20 1c ...` / `00 02 00 00 20 12 ...` | many | header of 0x400 or 0x200 bytes holding ascending u32 offsets, so probably a sub-archive |
| `70 aa 05 00 18 68 06 00` (entries 0,2,4,...,10) | few | ascending u32s. Unknown, possibly an offset table |
| `NN 00 00 00` + `0x8006xxxx` pointers / MIPS code | entries 16-21, 24 | **code overlays**: u32 id (6..12) then code/data that loads near 0x8006xxxx |
| `70 42 41 56` (`pBAV`) | entry 22 | **VAB** sound bank (PsyQ libsnd) |
| `NN 00 00 00 0a 0a 44 45...` | entry 18 | maybe text, or an overlay holding strings |

## Open questions

- [ ] Find the loader in SLES_027.93: look for the code that calls `CdControl`/`CdRead`
      with DATA.0's start LBA (23) plus `offset/0x800`.
- [ ] Find the load address of each overlay. Entry 17 calls `0x8002DCB0` in the main exe.
- [ ] Find the meaning of the `0x400`/`0x200` sub-archive headers.
- [ ] Check whether any entries are compressed.
