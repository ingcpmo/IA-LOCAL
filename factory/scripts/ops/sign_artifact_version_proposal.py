#!/usr/bin/env python3
"""Panel ARQ 2026-08-04 §6 — fallback GOBERNADO de firma de propuestas
ARTIFACT_VERSION, para usar SOLO si la UI de Mission Control no puede
recuperarse de inmediato.

QUE HACE, Y QUE NO
------------------
Carga la propuesta EXACTA por `proposal_id`, muestra los 8 campos que se
van a firmar, exige re-tipear `proposal_id` y `to_version` como
confirmación explícita, y emite UN evento append-only mediante el MISMO
validador de echo-back que usa el endpoint real
(`factory.services.artifact_version_signing.sign_artifact_version_proposal`)
-- no es una ruta paralela de escritura, es el mismo código.

**NO aplica el bump** (`catalog_version` en `requirements.yaml` sigue
igual). Aplicar es `factory/core/artifact_version_apply.py`, un paso
posterior y separado, bajo su propio procedimiento gobernado. Este script
no tiene ningún flag de fuerza.

USO
---
    python3 factory/scripts/ops/sign_artifact_version_proposal.py \\
        --proposal-id ARTIFACT_VERSION-2026-005

Pide de forma interactiva: motivo, identidad (id real, nunca "human"/
"admin"/genérico -- la misma validación única de la fábrica), y la
re-confirmación exacta.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from factory.core import identity_policy as identity  # noqa: E402
from factory.services import artifact_version_signing as avs  # noqa: E402
from factory.services import governance_service as gov  # noqa: E402


def _print_proposal(p: dict) -> None:
    print("\n" + "=" * 72)
    print("PROPUESTA A FIRMAR — revisa cada campo antes de continuar")
    print("=" * 72)
    for k in ("proposal_id", "artifact_path", "from_version", "to_version",
             "artifact_hash_before", "expected_hash_after", "change_reason",
             "status"):
        print(f"  {k.upper():22s} = {p.get(k)}")
    print(f"  {'STATE_HASH':22s} = {p.get('state_hash')}")
    print("=" * 72 + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proposal-id", required=True)
    args = ap.parse_args()

    # 1. Carga EXACTA por proposal_id -- se busca en TODAS las propuestas
    #    ARTIFACT_VERSION conocidas (no se pide artifact_path aparte: lo
    #    trae la propia propuesta, y re-pedirlo abriria la puerta a un
    #    desajuste entre lo tecleado y lo real).
    todas = gov.list_proposals("ARTIFACT_VERSION")
    encontrada = next((r for r in todas if r["decision_instance_id"] == args.proposal_id), None)
    if encontrada is None:
        print(f"ERROR: {args.proposal_id!r} no existe.", file=sys.stderr)
        return 1

    artifact_path = None
    # `list_proposals` no trae `resolved_target_ids`/`payload` -- se relee el
    # registro completo para obtenerlos (misma fuente unica de verdad).
    from factory.services import decision_store_v2 as store
    registro = next((r for r in store.read_all()
                     if r["decision_instance_id"] == args.proposal_id), None)
    if registro is None or registro.get("decision_family") != "ARTIFACT_VERSION":
        print(f"ERROR: {args.proposal_id!r} no es una propuesta ARTIFACT_VERSION valida.",
              file=sys.stderr)
        return 1
    targets = registro.get("resolved_target_ids") or []
    if len(targets) != 1:
        print(f"ERROR: la propuesta declara {len(targets)} artefactos, se esperaba 1.",
              file=sys.stderr)
        return 1
    artifact_path = targets[0]

    props = avs.list_artifact_version_proposals(artifact_path)
    proposal = next((p for p in props if p["proposal_id"] == args.proposal_id), None)
    if proposal is None:
        print(f"ERROR: {args.proposal_id!r} no aparece bajo {artifact_path!r}.", file=sys.stderr)
        return 1
    if proposal["status"] != avs.STATUS_PROPOSED:
        print(f"ERROR: status={proposal['status']!r} -- solo se firma PROPOSED.", file=sys.stderr)
        return 1
    if not proposal["payload_complete"]:
        print("ERROR: la propuesta no tiene el payload completo (from_version/to_version/"
              "hashes/change_reason) -- no es firmable.", file=sys.stderr)
        return 1

    # 2. Mostrar TODOS los campos que se firmaran.
    _print_proposal(proposal)

    # 4a. Re-confirmacion explicita: proposal_id y to_version re-tipeados.
    tecleado_id = input(f"Re-tipea el PROPOSAL_ID exacto para continuar ({args.proposal_id}): ").strip()
    if tecleado_id != args.proposal_id:
        print("ERROR: proposal_id no coincide. Nada firmado.", file=sys.stderr)
        return 1
    tecleado_to = input(f"Re-tipea el TO_VERSION exacto ({proposal['to_version']}): ").strip()
    if tecleado_to != proposal["to_version"]:
        print("ERROR: to_version no coincide. Nada firmado.", file=sys.stderr)
        return 1

    # 3. Identidad -- misma validacion unica de la fabrica, ANTES de pedir
    #    motivo (fallar rapido si la identidad esta mal, no al final).
    aprobado_por = input("Tu identidad real (id, NUNCA 'human'/'admin'/generico): ").strip()
    try:
        identity.validate_identity(aprobado_por, field="approved_by_id")
    except identity.IdentityValidationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    nombre = input("Tu nombre para mostrar (opcional, Enter para usar el id): ").strip() or aprobado_por

    motivo = input("MOTIVO de esta firma (obligatorio): ").strip()
    if not motivo:
        print("ERROR: el motivo es obligatorio. Nada firmado.", file=sys.stderr)
        return 1

    confirmacion_final = input(
        f"\n¿Confirmas la firma de {args.proposal_id} como {aprobado_por!r}? "
        "Escribe 'FIRMAR' en mayusculas para proceder: ").strip()
    if confirmacion_final != "FIRMAR":
        print("Cancelado. Nada firmado.")
        return 1

    # 5. Emite UN evento, mismo validador de echo-back que el endpoint real
    #    -- nunca una ruta paralela de escritura.
    try:
        resultado = avs.sign_artifact_version_proposal(
            proposal_id=proposal["proposal_id"], artifact_path=proposal["artifact_path"],
            from_version=proposal["from_version"], to_version=proposal["to_version"],
            artifact_hash_before=proposal["artifact_hash_before"],
            expected_hash_after=proposal["expected_hash_after"],
            state_hash=proposal["state_hash"], reason=motivo,
            approved_by_id=aprobado_por, approved_by_display_name=nombre)
    except (avs.ProposalMismatchError, avs.DuplicateSignatureError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 -- cualquier otro rechazo del backend real
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(f"\nFIRMADO: {resultado['decision_instance_id']} "
         f"confirma {resultado['confirms_instance_id']}.")
    print("NO se aplico el bump. Paso siguiente (separado, bajo su propio "
         "procedimiento): factory/core/artifact_version_apply.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
