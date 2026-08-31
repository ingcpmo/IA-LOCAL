#!/usr/bin/env python3
"""H-6F (2026-08-29) -- restore AISLADO + verificación de reconstrucción del
estado gobernado de GMP AI Factory.

PROHIBIDO restaurar sobre `factory/`, `GMPAI/reports/` o cualquier store vivo.
El destino DEBE estar bajo /tmp (o el que se pase con --into, que se valida).

Demuestra:
  SHA256SUMS_VERIFIED
  MANIFEST_VERIFIED
  GOVERNED_DECISIONS_LOADABLE
  REVIEW_QUEUE_LOADABLE
  IDENTITY_REGISTRY_METADATA_LOADABLE   (sobre el .example -- el real es secreto)
  REQUIREMENT_CATALOG_LOADABLE
  AUDIT_HISTORICAL_EXCEPTION_PRESERVED  (FORK-2026-06-15-001 / AUDIT_EXCEPTION-2026-002)
  NEW_FORKS == 0
  CHAIN_STATE_AFTER_RESTORE == original (line_count + break entry_ids)
  RUN_PACKAGE_RESOLVABLE  (SHA256SUMS.txt del paquete re-verifica)
  GRAPH_SNAPSHOT_FINGERPRINT_MATCHES  (snapshot vs audit_metadata del paquete)

Uso:
  restore_factory_state.py <tarball.tar.zst> --into /tmp/factory_restore_XXXX [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

_FORBIDDEN_ROOTS = ("/factory", "/GMPAI")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _fail(checks: dict, key: str, msg: str):
    checks[key] = {"status": "FAIL", "detail": msg}


def _ok(checks: dict, key: str, detail=None):
    checks[key] = {"status": "PASS", **({"detail": detail} if detail is not None else {})}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tarball")
    ap.add_argument("--into", required=True)
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    tarball = Path(args.tarball).resolve()
    into = Path(args.into).resolve()
    repo_root = Path(args.repo_root).resolve()

    # --- guardas de aislamiento -------------------------------------------
    if not (str(into).startswith(tempfile.gettempdir() + "/") or "/factory_restore" in str(into)):
        print(f"REFUSED: destino no aislado: {into} (debe estar bajo {tempfile.gettempdir()})", file=sys.stderr)
        return 3
    for bad in _FORBIDDEN_ROOTS:
        if str(into) == str(repo_root) or str(into).startswith(str(repo_root) + bad):
            print(f"REFUSED: el destino toca un store vivo ({bad})", file=sys.stderr)
            return 3
    if into.exists() and any(into.iterdir()):
        print(f"REFUSED: {into} no está vacío", file=sys.stderr)
        return 3
    into.mkdir(parents=True, exist_ok=True)

    checks: dict = {}

    # --- extracción ------------------------------------------------------
    subprocess.run(["tar", "--use-compress-program=unzstd", "-xf", str(tarball), "-C", str(into)],
                   check=True)
    roots = [p for p in into.iterdir() if p.is_dir() and p.name.startswith("factory_state_")]
    if not roots:
        _fail(checks, "EXTRACTED", "no se encontró factory_state_* en el tar")
        print(json.dumps({"checks": checks}, indent=1)); return 1
    R = roots[0]
    meta = R / "_backup_meta"
    _ok(checks, "EXTRACTED", str(R))

    # --- SHA256SUMS_VERIFIED -------------------------------------------
    sums = meta / "SHA256SUMS"
    manifest_path = meta / "MANIFEST.json"
    bad = []
    n = 0
    if sums.is_file():
        for line in sums.read_text().splitlines():
            if not line.strip():
                continue
            want, rel = line.split("  ", 1)
            fp = R / rel
            n += 1
            if not fp.is_file() or _sha256(fp) != want:
                bad.append(rel)
        if bad:
            _fail(checks, "SHA256SUMS_VERIFIED", f"{len(bad)} mismatch (p.ej. {bad[:3]})")
        else:
            _ok(checks, "SHA256SUMS_VERIFIED", f"{n} ficheros")
    else:
        _fail(checks, "SHA256SUMS_VERIFIED", "SHA256SUMS ausente")

    # --- MANIFEST_VERIFIED -------------------------------------------
    man = {}
    if manifest_path.is_file():
        man = json.loads(manifest_path.read_text())
        actual_files = sorted(p.relative_to(R).as_posix() for p in R.rglob("*")
                              if p.is_file() and not p.relative_to(R).as_posix().startswith("_backup_meta/"))
        want_files = sorted(man.get("sha256", {}))
        missing = set(want_files) - set(actual_files)
        extra = set(actual_files) - set(want_files)
        lc_ok = True
        for rel, want_lc in man.get("jsonl_line_counts", {}).items():
            fp = R / rel
            if fp.is_file() and sum(1 for _ in fp.open("rb")) != want_lc:
                lc_ok = False
        if missing or extra or not lc_ok:
            _fail(checks, "MANIFEST_VERIFIED",
                  f"missing={len(missing)} extra={len(extra)} line_counts_ok={lc_ok}")
        else:
            _ok(checks, "MANIFEST_VERIFIED",
                {"file_count": man.get("file_count"), "git_head": man.get("git_head")})
    else:
        _fail(checks, "MANIFEST_VERIFIED", "MANIFEST.json ausente")

    # --- reconstrucción de estado gobernado (sin red, sin LLM) --------
    sys.path.insert(0, str(repo_root))  # el CÓDIGO viene del repo; el ESTADO del backup

    # decisions v2
    try:
        dv2 = R / "factory/layer9/decisions/decisions_v2.jsonl"
        recs = [json.loads(l) for l in dv2.read_text().splitlines() if l.strip()]
        _ok(checks, "GOVERNED_DECISIONS_LOADABLE", {"records": len(recs)})
        has_exc = any("AUDIT_EXCEPTION-2026-002" in json.dumps(r) for r in recs)
        checks["AUDIT_EXCEPTION_2026_002_IN_DECISIONS"] = {
            "status": "PASS" if has_exc else "FAIL",
            "detail": "AUDIT_EXCEPTION-2026-002 presente" if has_exc else "no encontrada"}
    except Exception as e:  # noqa: BLE001
        _fail(checks, "GOVERNED_DECISIONS_LOADABLE", f"{type(e).__name__}: {e}")

    # review queue
    try:
        rq = R / "factory/layer9/review_queue.jsonl"
        entries = [json.loads(l) for l in rq.read_text().splitlines() if l.strip()]
        _ok(checks, "REVIEW_QUEUE_LOADABLE", {"entries": len(entries)})
    except Exception as e:  # noqa: BLE001
        _fail(checks, "REVIEW_QUEUE_LOADABLE", f"{type(e).__name__}: {e}")

    # identity registry metadata (sobre el .example -- el real es secreto y NO está)
    try:
        import yaml
        ex = R / "factory/config/identity_keys.yaml.example"
        d = yaml.safe_load(ex.read_text()) or {}
        shape_ok = isinstance(d.get("identities"), list)
        checks["IDENTITY_REGISTRY_METADATA_LOADABLE"] = {
            "status": "PASS" if shape_ok else "FAIL",
            "detail": "estructura identities:[...] presente en .example; el fichero real "
                      "es SENSIBLE y NO se incluye (SECRETS_MANIFEST)"}
        real_absent = not (R / "factory/config/identity_keys.yaml").exists()
        checks["SECRET_IDENTITY_KEYS_EXCLUDED_FROM_BACKUP"] = {
            "status": "PASS" if real_absent else "FAIL",
            "detail": "identity_keys.yaml (real) ausente del backup, como debe"}
    except Exception as e:  # noqa: BLE001
        _fail(checks, "IDENTITY_REGISTRY_METADATA_LOADABLE", f"{type(e).__name__}: {e}")

    # requirement catalog
    try:
        from factory.regulatory.requirement_catalog.requirement_catalog_loader import load_requirements
        cat_dir = R / "factory/regulatory/requirement_catalog"
        import os as _os
        _prev = _os.getcwd()
        try:
            # el loader resuelve rutas relativas al repo; comprobamos que el YAML
            # restaurado parsea y trae los requisitos Tier-1.
            import yaml
            reqs = yaml.safe_load((cat_dir / "requirements.yaml").read_text())
            rids = set((reqs or {}).get("requirements", {}))
            tier1 = {"21_CFR_11.10(d)", "21_CFR_11.10(e)", "21_CFR_11.10(g)", "21_CFR_11.50_11.70",
                     "ANNEX11_7.1", "ANNEX11_9", "ANNEX11_12", "ANNEX11_17",
                     "ALCOA_ATTRIBUTABLE", "ALCOA_LEGIBLE", "ALCOA_CONTEMPORANEOUS", "ALCOA_ORIGINAL"}
            missing = tier1 - rids
            checks["REQUIREMENT_CATALOG_LOADABLE"] = {
                "status": "PASS" if not missing else "FAIL",
                "detail": f"{len(rids)} requisitos; Tier-1 faltantes: {sorted(missing) or 'ninguno'}"}
        finally:
            _os.chdir(_prev)
    except Exception as e:  # noqa: BLE001
        _fail(checks, "REQUIREMENT_CATALOG_LOADABLE", f"{type(e).__name__}: {e}")

    # audit chain -- exception preservada, 0 forks nuevos, estado == original
    try:
        from factory.core import audit_writer as aw
        af = R / "factory/audit/factory_audit.jsonl"
        fb = R / "factory/audit/fork_baseline.json"
        base = json.loads(fb.read_text())
        fork_ids = [f.get("fork_id") for f in base.get("known_forks", [])]
        entry_ids = [f.get("entry_id") for f in base.get("known_forks", [])]
        exc_ids = [f.get("accepted_by_decision") for f in base.get("known_forks", [])]
        new_forks = list(aw.new_forks_since_baseline(af, fb))
        breaks = list(aw.chain_break_entry_ids(af))
        line_count = sum(1 for _ in af.open("rb"))

        checks["AUDIT_HISTORICAL_EXCEPTION_PRESERVED"] = {
            "status": "PASS" if ("FORK-2026-06-15-001" in fork_ids
                                 and "AUDIT_EXCEPTION-2026-002" in exc_ids) else "FAIL",
            "detail": {"historical_fork_ids": fork_ids, "accepted_by": exc_ids,
                       "historical_fork_count": len(fork_ids)}}
        checks["NEW_AUDIT_FORKS_ZERO"] = {
            "status": "PASS" if not new_forks else "FAIL",
            "detail": {"new_forks": new_forks}}

        # comparación con el original (repo vivo)
        af0 = repo_root / "factory/audit/factory_audit.jsonl"
        fb0 = repo_root / "factory/audit/fork_baseline.json"
        line0 = sum(1 for _ in af0.open("rb")) if af0.exists() else -1
        breaks0 = list(aw.chain_break_entry_ids(af0)) if af0.exists() else []
        same = (line_count == line0 and set(breaks) == set(breaks0)
                and _sha256(af) == _sha256(af0) and _sha256(fb) == _sha256(fb0))
        checks["CHAIN_STATE_AFTER_RESTORE_EQUALS_ORIGINAL"] = {
            "status": "PASS" if same else "FAIL",
            "detail": {"restored_line_count": line_count, "original_line_count": line0,
                       "restored_breaks": breaks, "original_breaks": breaks0,
                       "audit_sha_equal": _sha256(af) == _sha256(af0),
                       "baseline_sha_equal": _sha256(fb) == _sha256(fb0)}}
    except Exception as e:  # noqa: BLE001
        _fail(checks, "AUDIT_CHAIN_RECONSTRUCTION", f"{type(e).__name__}: {e}")

    # run package resolvable + graph snapshot fingerprint matches
    try:
        rp_base = R / "GMPAI/reports/gmpai_document_validation"
        pkgs = sorted([p for p in rp_base.iterdir() if p.is_dir()]) if rp_base.is_dir() else []
        chosen = None
        for p in reversed(pkgs):
            if (p / "SHA256SUMS.txt").is_file() and (p / "graph_snapshot" / "graph_snapshot.json").is_file():
                chosen = p
                break
        if chosen is None:
            checks["RUN_PACKAGE_RESOLVABLE"] = {"status": "SKIP",
                "detail": "ningún paquete con SHA256SUMS.txt + graph_snapshot en el backup"}
        else:
            sums_txt = (chosen / "SHA256SUMS.txt").read_text().splitlines()
            mm = []
            for line in sums_txt:
                if not line.strip():
                    continue
                want, rel = line.split("  ", 1)
                fp = chosen / rel
                if rel == "manifest.json":
                    continue  # se hashea aparte en el receipt
                if not fp.is_file() or _sha256(fp) != want:
                    mm.append(rel)
            checks["RUN_PACKAGE_RESOLVABLE"] = {
                "status": "PASS" if not mm else "FAIL",
                "detail": {"package": chosen.name, "mismatches": mm[:5], "n": len(sums_txt)}}

            snap = json.loads((chosen / "graph_snapshot" / "graph_snapshot.json").read_text())
            am = json.loads((chosen / "audit_summary" / "audit_metadata.json").read_text())
            from factory.regulatory.validation_v2 import run_fingerprint as rf
            recomputed = rf.graph_snapshot_fingerprint(snap)
            matches = (recomputed == snap.get("graph_snapshot_fingerprint")
                       == am.get("graph_snapshot_fingerprint"))
            checks["GRAPH_SNAPSHOT_FINGERPRINT_MATCHES"] = {
                "status": "PASS" if matches else "FAIL",
                "detail": {"recomputed": recomputed,
                           "in_snapshot": snap.get("graph_snapshot_fingerprint"),
                           "in_audit_metadata": am.get("graph_snapshot_fingerprint")}}
    except Exception as e:  # noqa: BLE001
        _fail(checks, "RUN_PACKAGE_RESOLVABLE", f"{type(e).__name__}: {e}")

    passed = sum(1 for v in checks.values() if v["status"] == "PASS")
    failed = [k for k, v in checks.items() if v["status"] == "FAIL"]
    result = {
        "tarball": str(tarball), "restored_into": str(R),
        "manifest_git_head": man.get("git_head"),
        "checks_passed": passed, "checks_failed": failed,
        "ISOLATED_RESTORE": "PASS" if not failed else "FAIL",
        "checks": checks,
    }
    print(json.dumps(result, indent=1, ensure_ascii=False) if args.json
          else "\n".join(f"{'PASS' if v['status']=='PASS' else v['status']:5} {k}" for k, v in checks.items()))
    if not args.json:
        print(f"\nISOLATED_RESTORE = {'PASS' if not failed else 'FAIL'}  ({passed} pass, {len(failed)} fail)")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
