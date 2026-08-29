"""MlVocabExtractor -- the frozen ML-encoder coupling (ml_label).

Ties tag/material vocabulary values to the CNN/LightGBM encoders in crafting_classifier.py,
their duplicated training mirrors, and the baked model artifacts. This is the coupling a
call-graph is totally blind to: renaming `fire` silently shifts the CNN hue it was trained
on; changing the SET SIZE of a LightGBM category list trips a feature-shape mismatch.

Returns raw site dicts (indexer resolves value->concept, creating ml_material concepts for
material categories like 'metal'/'elemental' that aren't in the combat/WMS authorities).
"""

from __future__ import annotations

from typing import Dict, List

from ..coordinates import (
    ENCODER_SPECS, CNN_ENCODER_COPIES, MODEL_ARTIFACTS, CRAFTING_CLASSIFIER,
    ML_COUNT_MISMATCH_SITE,
)


class MlVocabExtractor:
    def collect(self, repo_root: str) -> List[Dict]:
        sites: List[Dict] = []
        for spec in ENCODER_SPECS:
            artifacts = _artifact_paths(spec)
            for key in spec["keys"]:
                # 1) the runtime encoder site
                sites.append(_site(key, "ml_label", "python", CRAFTING_CLASSIFIER, spec["line"],
                                   f"{spec['name']} ({spec['kind']}): {spec['role']}",
                                   spec["silent_failure"], mirror_group=spec.get("mirror_group")))
                # 2) count-sensitive -> the hard shape-mismatch guard
                if spec["count_sensitive"]:
                    f, ln, note = ML_COUNT_MISMATCH_SITE
                    sites.append(_site(key, "ml_label", "python", f, ln,
                                       f"count-sensitive: {note}",
                                       "changing the SET SIZE of this list trips the feature-shape guard -> validation error"))
                # 3) duplicated training mirrors (CNN encoders only)
                if spec.get("mirror_group") == "cnn_smithing_encoder":
                    for path, cline, mnote in CNN_ENCODER_COPIES:
                        sites.append(_site(key, "ml_label", "python", path, cline,
                                           f"training mirror of {spec['name']}: {mnote}",
                                           "training mirror must match runtime encoder or the model trains on different inputs",
                                           mirror_group="cnn_smithing_encoder"))
                # 4) baked model artifacts (retrain to regenerate)
                for path in artifacts:
                    sites.append(_site(key, "ml_label", "ml_binary", path, 1,
                                       f"baked model artifact ({_disc(path)}) -- learned weights encode the old value",
                                       "artifact is STALE until retrained; rename invalidates it (no error)",
                                       locator_extra={"artifact": True}))
        return sites


def _artifact_paths(spec) -> List[str]:
    out: List[str] = []
    for disc in spec.get("artifacts", []):
        out.extend(MODEL_ARTIFACTS.get(disc, []))
    return out


def _disc(path: str) -> str:
    return "keras/CNN" if path.endswith(".keras") else "LightGBM"


def _site(value, site_kind, language, file, line, role, silent, mirror_group=None, locator_extra=None) -> Dict:
    return {
        "value": value, "kind_hint": "ml_feature_slot",
        "site_kind": site_kind, "coupling_type": "ml_label", "language": language,
        "file": file, "line": int(line), "role": role, "silent_failure": silent,
        "editable": 1, "governance": None, "preferred_taxonomy": None,
        "mirror_group": mirror_group, "locator_extra": locator_extra, "content_hash": None,
    }
