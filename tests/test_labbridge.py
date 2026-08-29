from labbridge.contracts import compatibility
from labbridge.service import SUPPORTED_AGENCITYLAB_VERSION, public_api


RUNTIME_VERSION_GUARD_MODULES = (
    "analyses.services",
    "analyses.multivariate_services",
    "analyses.diagnostic_services",
    "sensitivity.services",
)


def _is_semver_literal(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 3 and all(part.isdigit() for part in parts)


def _string_constants(code):
    for value in code.co_consts:
        if isinstance(value, str):
            yield value
        elif hasattr(value, "co_consts"):
            yield from _string_constants(value)


def test_pinned_agencitylab_public_api_is_available():
    lab = public_api()

    assert lab.__version__ == SUPPORTED_AGENCITYLAB_VERSION
    assert callable(lab.compute_agencity)


def test_runtime_compatibility_matches_pinned_lab():
    contract = compatibility()

    assert contract.lab_version == SUPPORTED_AGENCITYLAB_VERSION
    assert contract.supported_lab_version == SUPPORTED_AGENCITYLAB_VERSION
    assert contract.compatible is True


def test_runtime_lab_version_guards_use_central_supported_version():
    offenders = []

    for module_name in RUNTIME_VERSION_GUARD_MODULES:
        module = __import__(module_name, fromlist=["*"])
        with open(module.__file__, encoding="utf-8") as source_file:
            source = source_file.read()
        code = compile(source, module.__file__, "exec")
        literals = [value for value in _string_constants(code) if _is_semver_literal(value)]
        if literals:
            offenders.append(f"{module_name}: {literals!r}")

    assert not offenders, (
        "Runtime AgencityLab version literals must be centralized in "
        "labbridge.service.SUPPORTED_AGENCITYLAB_VERSION:\n" + "\n".join(offenders)
    )
