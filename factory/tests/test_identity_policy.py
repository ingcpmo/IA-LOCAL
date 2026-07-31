"""factory/core/identity_policy.py -- G3 (2026-07-30): "claude_probe" pasó el
match exacto de RESERVED_IDENTITIES y quedó como approved_by_id real de
D2-2026-003 (human_confirmed, ACTIVE) -- una firma fabricada por el propio
agente. El match exacto no bastaba: cualquier variante con sufijo de un
prefijo reservado identifica al mismo no-humano.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.core import identity_policy as idp


class TestPrefixVariantsAreReserved:

    @pytest.mark.parametrize("name", [
        "claude_probe", "claude_code_session_g2_1", "Claude Opus 5",
        "CLAUDE_PROBE", "claude", "capa9_bot", "capa8-worker", "layer9x",
        "agente_ficticio",
        # W5V2_FIX_FIRMA_SILENCIOSA §3.1: variantes explicitas del documento
        "human_reviewer", "Human-2", "HUMAN_REVIEWER", "admin_test",
        "Admin-2", "system_bot", "SYSTEM_2",
    ])
    def test_rejected(self, name):
        assert idp.is_reserved(name), f"{name!r} deberia ser reservado"
        with pytest.raises(idp.IdentityValidationError):
            idp.validate_identity(name)

    @pytest.mark.parametrize("name", ["Cesar", "ing_cpmo", "Cesar May", "qa_real"])
    def test_real_names_are_not_swept_up_by_the_prefix_guard(self, name):
        """El endurecimiento no puede volverse tan amplio que rechace un
        nombre real -- 'qa_real' contiene 'qa' pero no EMPIEZA con un prefijo
        reservado completo ('qa' es exacto en RESERVED_IDENTITIES, no prefijo)."""
        assert not idp.is_reserved(name)
        assert idp.validate_identity(name) == name

    def test_the_incident_string_specifically(self):
        """El string exacto que produjo D2-2026-003. Regresion nominal."""
        with pytest.raises(idp.IdentityValidationError):
            idp.validate_identity("claude_probe", field="approved_by_id")
