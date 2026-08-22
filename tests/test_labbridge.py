from labbridge.contracts import compatibility
from labbridge.service import SUPPORTED_AGENCITYLAB_VERSION, public_api


def test_pinned_agencitylab_public_api_is_available():
    lab = public_api()

    assert lab.__version__ == SUPPORTED_AGENCITYLAB_VERSION
    assert callable(lab.compute_agencity)


def test_runtime_compatibility_matches_pinned_lab():
    contract = compatibility()

    assert contract.lab_version == SUPPORTED_AGENCITYLAB_VERSION
    assert contract.supported_lab_version == SUPPORTED_AGENCITYLAB_VERSION
    assert contract.compatible is True
