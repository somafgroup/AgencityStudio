import ast
import re
from pathlib import Path

from labbridge.contracts import compatibility
from labbridge.service import SUPPORTED_AGENCITYLAB_VERSION, public_api


RUNTIME_VERSION_GUARD_FILES = (
    "analyses/services.py",
    "analyses/multivariate_services.py",
    "analyses/diagnostic_services.py",
    "sensitivity/services.py",
)
SEMVER_PATTERN = re.compile(r"(?<!\d)\d+\.\d+\.\d+(?!\d)")


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
    root = Path(__file__).resolve().parents[1]
    offenders = []

    for relative_path in RUNTIME_VERSION_GUARD_FILES:
        path = root / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and SEMVER_PATTERN.search(node.value)
            ):
                offenders.append(f"{relative_path}:{node.lineno}: {node.value!r}")

    assert not offenders, (
        "Runtime AgencityLab version literals must be centralized in "
        "labbridge.service.SUPPORTED_AGENCITYLAB_VERSION:\n" + "\n".join(offenders)
    )
