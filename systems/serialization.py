"""Deterministic serialization for scientific-context fingerprints."""

from __future__ import annotations

import hashlib
import json


def revision_payload(revision) -> dict:
    """Return scientific content only, excluding timestamps and UI state."""
    observables = [
        {
            "position": observable.position,
            "name": observable.name,
            "symbol": observable.symbol,
            "description": observable.description,
            "unit": observable.unit,
            "observable_kind": observable.observable_kind,
            "nature": observable.nature,
            "source_description": observable.source_description,
            "is_primary": observable.is_primary,
        }
        for observable in revision.observables.order_by("position")
    ]
    references = [
        {
            "title": reference.title,
            "citation": reference.citation,
            "doi": reference.doi,
            "url": reference.url,
            "notes": reference.notes,
            "supports_a_ref": reference.supports_a_ref,
            "supports_tau": reference.supports_tau,
            "supports_w": reference.supports_w,
            "supports_p_c": reference.supports_p_c,
        }
        for reference in revision.references.order_by("citation", "title", "id")
    ]
    return {
        "description": revision.description,
        "domain": revision.domain,
        "system_type": revision.system_type,
        "mechanism": revision.mechanism,
        "environment": revision.environment,
        "measurement_context": revision.measurement_context,
        "scientific_notes": revision.scientific_notes,
        "documentation_status": revision.documentation_status,
        "A_ref": {
            "value": revision.a_ref_value,
            "value_text": revision.a_ref_value_text,
            "unit": revision.a_ref_unit,
            "origin": revision.a_ref_origin,
            "origin_detail": revision.a_ref_origin_detail,
            "justification": revision.a_ref_justification,
        },
        "tau": {
            "value": revision.tau_value,
            "value_text": revision.tau_value_text,
            "unit": revision.tau_unit,
            "origin": revision.tau_origin,
            "origin_detail": revision.tau_origin_detail,
            "justification": revision.tau_justification,
        },
        "w": {
            "mode": revision.w_mode,
            "value": revision.w_value,
            "value_text": revision.w_value_text,
            "unit": revision.w_unit,
            "origin": revision.w_origin,
            "origin_detail": revision.w_origin_detail,
            "justification": revision.w_justification,
        },
        "P_c": {
            "mode": revision.p_c_mode,
            "value": revision.p_c_value,
            "value_text": revision.p_c_value_text,
            "unit": revision.p_c_unit,
            "origin": revision.p_c_origin,
            "origin_detail": revision.p_c_origin_detail,
            "justification": revision.p_c_justification,
        },
        "observables": observables,
        "references": references,
    }


def configuration_fingerprint(revision) -> str:
    """Return SHA-256 of canonical scientific configuration content."""
    payload = json.dumps(
        revision_payload(revision),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
