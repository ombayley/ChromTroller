#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: **Add Desc**.
"""
# import zipfile
#
#
# def test_parse_openlabcds():
#     path = r"C:\Users\OllyBayley\Documents\Repos\work\ChromTroller\docs\example_datasets\hplc\simple\example_simple1.dx"
#     with zipfile.ZipFile(path, 'r') as dx_file_unzipped:
#         print(dx_file_unzipped.namelist())
# from __future__ import annotations

import struct
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

# ----------------------------
# Helpers
# ----------------------------

def u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]

def u64(b: bytes, off: int) -> int:
    return struct.unpack_from("<Q", b, off)[0]

def f32(b: bytes, off: int) -> float:
    return struct.unpack_from("<f", b, off)[0]

def f64(b: bytes, off: int) -> float:
    return struct.unpack_from("<d", b, off)[0]

def is_finite(x: float) -> bool:
    return not (math.isnan(x) or math.isinf(x))

def mz_plausible(mz: float) -> bool:
    return is_finite(mz) and 30.0 <= mz <= 5000.0

def inten_plausible(i: float) -> bool:
    # intensity often >= 0; can be float or int
    return is_finite(i) and i >= 0.0 and i <= 1e12

# ----------------------------
# Candidate scan-record models
# ----------------------------

@dataclass
class ScanRecord:
    scan_index: int
    offset: int
    byte_count: int
    point_count: int
    uncompressed_byte_count: Optional[int] = None

@dataclass
class ScanLayoutHypothesis:
    name: str
    record_size: int
    parse_one: Callable[[bytes, int, int], Optional[ScanRecord]]  # (mscan_bytes, base, scan_index)->record

def make_scan_hypotheses(peak_size: int) -> list[ScanLayoutHypothesis]:
    hyps: list[ScanLayoutHypothesis] = []

    # Hypothesis A: <I offset, <I bytecount, <I pointcount, <I uncompressed
    def parse_A(b: bytes, base: int, idx: int) -> Optional[ScanRecord]:
        if base + 16 > len(b): return None
        off = u32(b, base)
        bc  = u32(b, base+4)
        pc  = u32(b, base+8)
        uc  = u32(b, base+12)
        if off >= peak_size or bc == 0 or bc > 50_000_000: return None
        if pc > 5_000_000: return None
        if uc != 0 and uc < bc: return None
        return ScanRecord(idx, off, bc, pc, uc)

    hyps.append(ScanLayoutHypothesis("A:u32,u32,u32,u32", 16, parse_A))

    # Hypothesis B: <Q offset, <I bytecount, <I pointcount, <I uncompressed, +4 pad (total 24)
    def parse_B(b: bytes, base: int, idx: int) -> Optional[ScanRecord]:
        if base + 24 > len(b): return None
        off = u64(b, base)
        bc  = u32(b, base+8)
        pc  = u32(b, base+12)
        uc  = u32(b, base+16)
        if off >= peak_size or bc == 0 or bc > 50_000_000: return None
        if pc > 5_000_000: return None
        if uc != 0 and uc < bc: return None
        return ScanRecord(idx, int(off), bc, pc, uc)

    hyps.append(ScanLayoutHypothesis("B:u64,u32,u32,u32,+pad", 24, parse_B))

    # Hypothesis C: <Q offset, <I bytecount, <I pointcount (no uncompressed) (total 16)
    def parse_C(b: bytes, base: int, idx: int) -> Optional[ScanRecord]:
        if base + 16 > len(b): return None
        off = u64(b, base)
        bc  = u32(b, base+8)
        pc  = u32(b, base+12)
        if off >= peak_size or bc == 0 or bc > 50_000_000: return None
        if pc > 5_000_000: return None
        return ScanRecord(idx, int(off), bc, pc, None)

    hyps.append(ScanLayoutHypothesis("C:u64,u32,u32", 16, parse_C))

    return hyps

# ----------------------------
# MSPeak payload decoding hypotheses
# ----------------------------

@dataclass
class Spectrum:
    mz: list[float]
    intensity: list[float]

@dataclass
class PayloadHypothesis:
    name: str
    decode: Callable[[bytes, ScanRecord], Optional[Spectrum]]

def make_payload_hypotheses() -> list[PayloadHypothesis]:
    hyps: list[PayloadHypothesis] = []

    # Payload 1: centroid list: repeated (float64 mz, float32 intensity) with 4-byte pad => 16 bytes/peak
    def decode_p1(seg: bytes, rec: ScanRecord) -> Optional[Spectrum]:
        n = rec.point_count
        stride = 16
        need = n * stride
        if n == 0 or need > len(seg): return None
        mzs: list[float] = []
        ints: list[float] = []
        off = 0
        for _ in range(n):
            mz = f64(seg, off)
            it = f32(seg, off+8)
            if not mz_plausible(mz) or not inten_plausible(it): return None
            mzs.append(mz); ints.append(float(it))
            off += stride
        return Spectrum(mzs, ints)

    hyps.append(PayloadHypothesis("p1:(f64 mz, f32 I, pad)", decode_p1))

    # Payload 2: centroid list: repeated (float64 mz, float64 intensity) => 16 bytes/peak
    def decode_p2(seg: bytes, rec: ScanRecord) -> Optional[Spectrum]:
        n = rec.point_count
        stride = 16
        need = n * stride
        if n == 0 or need > len(seg): return None
        mzs: list[float] = []
        ints: list[float] = []
        off = 0
        for _ in range(n):
            mz = f64(seg, off)
            it = f64(seg, off+8)
            if not mz_plausible(mz) or not inten_plausible(it): return None
            mzs.append(mz); ints.append(it)
            off += stride
        return Spectrum(mzs, ints)

    hyps.append(PayloadHypothesis("p2:(f64 mz, f64 I)", decode_p2))

    # Payload 3: profile-like: (float64 smallest_mz, float64 mz_delta) then uint32 intensities[point_count]
    # m/z reconstructed as smallest_mz + i*mz_delta
    def decode_p3(seg: bytes, rec: ScanRecord) -> Optional[Spectrum]:
        n = rec.point_count
        if n == 0: return None
        header = 16
        need = header + n*4
        if need > len(seg): return None
        smallest = f64(seg, 0)
        delta = f64(seg, 8)
        if not mz_plausible(smallest) or not is_finite(delta) or not (0.0 < delta < 1.0):
            return None
        mzs = [smallest + i*delta for i in range(n)]
        ints = [float(u32(seg, header + 4*i)) for i in range(n)]
        # intensities should not be all zeros
        if sum(1 for x in ints if x > 0) < max(3, n//200):
            return None
        return Spectrum(mzs, ints)

    hyps.append(PayloadHypothesis("p3:(f64 smallest, f64 delta, u32 intensities)", decode_p3))

    return hyps

# ----------------------------
# Scoring & discovery
# ----------------------------

def score_spectrum(spec: Spectrum) -> float:
    # Reward plausible m/z range and some variability
    n = len(spec.mz)
    if n == 0: return 0.0
    mz_ok = sum(1 for x in spec.mz if mz_plausible(x)) / n
    i_ok  = sum(1 for x in spec.intensity if inten_plausible(x)) / n
    # variability: not all equal
    uniq_i = len(set(round(x, 6) for x in spec.intensity[:min(n, 500)]))
    var_bonus = min(1.0, uniq_i / 50.0)
    # monotonic mz is common (not guaranteed), mild reward
    mono = sum(1 for i in range(1, n) if spec.mz[i] >= spec.mz[i-1]) / max(1, n-1)
    return 100.0*mz_ok + 60.0*i_ok + 20.0*var_bonus + 10.0*mono

def discover(
    mscan_path: Path,
    mspeak_path: Path,
    scan_data_offset_guess: int = 0x58,
    max_scans_to_test: int = 2000,
) -> None:
    mscan = mscan_path.read_bytes()
    mspeak = mspeak_path.read_bytes()
    peak_size = len(mspeak)

    print(f"MSScan.bin size: {len(mscan)} bytes")
    print(f"MSPeak.bin size: {peak_size} bytes")
    print(f"MSScan magic u32 @0: {u32(mscan, 0)}")
    print(f"MSPeak magic u32 @0: {u32(mspeak, 0)}")

    scan_hyps = make_scan_hypotheses(peak_size)
    payload_hyps = make_payload_hypotheses()

    best = None  # (total_score, scan_hyp_name, payload_name, records_preview)
    for sh in scan_hyps:
        # Try multiple possible alignments around the "0x58" guess
        for base0 in range(scan_data_offset_guess - 32, scan_data_offset_guess + 33, 4):
            records: list[ScanRecord] = []
            ok = 0
            for i in range(max_scans_to_test):
                base = base0 + i*sh.record_size
                rec = sh.parse_one(mscan, base, i)
                if rec is None:
                    break
                # also require the segment to fit
                if rec.offset + rec.byte_count > peak_size:
                    break
                records.append(rec)
                ok += 1

            if ok < 50:
                continue

            # Evaluate a few spectra using payload hypotheses
            for ph in payload_hyps:
                tot = 0.0
                tested = 0
                for rec in records[:min(200, len(records))]:
                    seg = mspeak[rec.offset : rec.offset + rec.byte_count]
                    spec = ph.decode(seg, rec)
                    if spec is None:
                        continue
                    tot += score_spectrum(spec)
                    tested += 1
                    if tested >= 30:
                        break

                if tested < 5:
                    continue

                avg = tot / tested
                key = (avg, sh.name, f"base0=0x{base0:x}", ph.name, tested, records[:3])
                if best is None or avg > best[0]:
                    best = key

    if best is None:
        print("\nNo convincing layout found yet.")
        print("Next ideas:")
        print("- MSScan may include per-scan structs BEFORE the spectrum params (RT, MS level, polarity).")
        print("- Offsets/lengths may be stored in a nested structure rather than a flat array.")
        return

    avg, sh_name, base0, ph_name, tested, preview = best
    print("\nBEST MATCH")
    print(f"  avg_score: {avg:.2f} (tested {tested} spectra)")
    print(f"  scan_layout: {sh_name}")
    print(f"  scan_table_base: {base0}")
    print(f"  payload_layout: {ph_name}")
    print("  first_records:")
    for r in preview:
        print(f"    idx={r.scan_index} off={r.offset} bytes={r.byte_count} points={r.point_count} uc={r.uncompressed_byte_count}")

def export_first_spectrum(
    mscan_path: Path,
    mspeak_path: Path,
    record: ScanRecord,
    payload: PayloadHypothesis,
    out_csv: Path,
) -> None:
    mspeak = mspeak_path.read_bytes()
    seg = mspeak[record.offset : record.offset + record.byte_count]
    spec = payload.decode(seg, record)
    if spec is None:
        raise ValueError("Could not decode spectrum with this payload hypothesis.")

    with out_csv.open("w", encoding="utf-8") as f:
        f.write("mz,intensity\n")
        for mz, it in zip(spec.mz, spec.intensity):
            f.write(f"{mz},{it}\n")

# ----------------------------
# CLI-ish entry point
# ----------------------------

if __name__ == "__main__":
    # Update these paths to your local copies
    base_dir = Path(r"C:\Users\OllyBayley\Desktop")
    MSPEAK = base_dir / "Sample_2025-12-03 12-39-12+01-00-r003.MSPeak.bin"
    MSSCAN = base_dir / "Sample_2025-12-03 12-39-12+01-00-r003.MSScan.bin"

    discover(MSSCAN, MSPEAK, scan_data_offset_guess=0x58, max_scans_to_test=5000)
