import sys
import yaml
from pathlib import Path
from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

CATALOG_PATH  = Path(__file__).parent.parent.parent / "registry" / "agents_catalog.yaml"
PROFILES_DIR  = Path(__file__).parent.parent.parent / "profiles"


@router.get("")
def get_agents():
    with open(CATALOG_PATH) as f:
        catalog = yaml.safe_load(f)
    return {
        "base_agents": catalog.get("base_agents", {}),
        "custom_agents": catalog.get("custom_agents", {}),
        "derived_profiles": catalog.get("derived_profiles", {}),
    }


@router.get("/profiles")
def get_profiles():
    profiles = {}
    for p in sorted(PROFILES_DIR.glob("*.yaml")):
        with open(p) as f:
            data = yaml.safe_load(f)
        profiles[p.stem] = data
    return profiles
