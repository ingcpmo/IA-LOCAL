#!/usr/bin/env python3
"""H-6F (2026-08-29) -- política de retención de backups de estado de Factory.

Política: 14 diarios · 8 semanales (lunes) · 6 mensuales (día 1).
Un backup se CONSERVA si cae en cualquiera de las tres ventanas; el resto se
marca para borrado.

SEGURIDAD: por defecto es DRY-RUN. `--apply` borra de verdad. La prueba inicial
de retención de H-6F se ejecuta contra un directorio de FIXTURES temporal, NUNCA
contra `backups/factory/state/` real.

Nombre de fichero esperado:  factory_state_YYYYMMDDT HHMMSSZ.tar.zst
Uso:
  factory_backup_retention.py <dir> [--apply] [--daily 14] [--weekly 8] [--monthly 6] [--json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

_TS_RE = re.compile(r"factory_state_(\d{8}T\d{6}Z)\.tar\.(zst|gz)$")


def _parse_ts(name: str) -> dt.datetime | None:
    m = _TS_RE.search(name)
    if not m:
        return None
    return dt.datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)


def plan(directory: Path, *, daily: int, weekly: int, monthly: int) -> dict:
    items = []
    for p in sorted(directory.glob("factory_state_*.tar.*")):
        ts = _parse_ts(p.name)
        if ts:
            items.append((ts, p))
    items.sort(key=lambda t: t[0], reverse=True)  # más nuevo primero

    keep: set[Path] = set()
    reasons: dict[str, list[str]] = {}

    def _mark(path: Path, why: str):
        keep.add(path)
        reasons.setdefault(path.name, []).append(why)

    seen_days, seen_weeks, seen_months = set(), set(), set()
    for ts, p in items:
        d = ts.date().isoformat()
        if d not in seen_days and len(seen_days) < daily:
            seen_days.add(d); _mark(p, f"daily[{len(seen_days)}/{daily}]")
        iso = ts.isocalendar()
        wk = f"{iso[0]}-W{iso[1]:02d}"
        if wk not in seen_weeks and len(seen_weeks) < weekly:
            seen_weeks.add(wk); _mark(p, f"weekly[{len(seen_weeks)}/{weekly}]")
        mo = f"{ts.year}-{ts.month:02d}"
        if mo not in seen_months and len(seen_months) < monthly:
            seen_months.add(mo); _mark(p, f"monthly[{len(seen_months)}/{monthly}]")

    delete = [p for _ts, p in items if p not in keep]
    return {
        "directory": str(directory),
        "policy": {"daily": daily, "weekly": weekly, "monthly": monthly},
        "total": len(items),
        "keep": sorted(p.name for p in keep),
        "keep_reasons": reasons,
        "delete": sorted(p.name for p in delete),
        "delete_paths": [str(p) for p in delete],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--apply", action="store_true", help="borra de verdad (por defecto: dry-run)")
    ap.add_argument("--daily", type=int, default=14)
    ap.add_argument("--weekly", type=int, default=8)
    ap.add_argument("--monthly", type=int, default=6)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    d = Path(args.directory).resolve()
    if not d.is_dir():
        print(f"no es un directorio: {d}"); return 2

    pl = plan(d, daily=args.daily, weekly=args.weekly, monthly=args.monthly)
    pl["applied"] = False

    if args.apply:
        # guarda: no borrar el ÚNICO backup, ni si todos caen en 'delete'
        if pl["delete"] and pl["keep"]:
            for sp in pl["delete_paths"]:
                p = Path(sp)
                p.unlink(missing_ok=True)
                for aux in (p.with_suffix(p.suffix + ".sha256"),):
                    aux.unlink(missing_ok=True)
            # metadatos sueltos con el mismo timestamp
            for sp in pl["delete_paths"]:
                stem = Path(sp).name.split(".tar.")[0]
                for aux in Path(sp).parent.glob(stem + ".*"):
                    if aux.name not in pl["keep"]:
                        aux.unlink(missing_ok=True)
            pl["applied"] = True
        else:
            pl["applied"] = False
            pl["apply_skipped_reason"] = "nada que borrar o quedaría 0 backups"

    print(json.dumps(pl, indent=1, ensure_ascii=False) if args.json
          else (f"dir={d}\npolicy={pl['policy']}\ntotal={pl['total']} "
                f"keep={len(pl['keep'])} delete={len(pl['delete'])} applied={pl['applied']}\n"
                + "\n".join("  KEEP   " + n for n in pl["keep"])
                + ("\n" if pl["keep"] else "")
                + "\n".join("  DELETE " + n for n in pl["delete"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
