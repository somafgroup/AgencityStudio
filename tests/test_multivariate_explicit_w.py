import numpy as np

from labbridge.multivariate import execute_multivariate_analysis
from labbridge.service import public_extended_api


def test_multivariate_bridge_preserves_explicit_w_vector_exactly():
    xi = np.arange(80, dtype=float) * 0.1
    component_a = np.sin(2.0 * np.pi * xi)
    component_b = 0.4 * np.cos(0.8 * np.pi * xi)
    matrix = np.column_stack((component_a, component_b))
    kwargs = {
        "A_ref": [1.0, 0.9],
        "tau": [0.2, 0.3],
        "w": [0.4, 0.5],
        "P_c": [2.0, 3.0],
        "sample_axis": 0,
    }

    direct = public_extended_api().compute_multivariate_agencity(matrix, xi, **kwargs)
    bridged = execute_multivariate_analysis(u=matrix, xi=xi, **kwargs).result

    np.testing.assert_array_equal(np.asarray(bridged["w"]), np.asarray(direct["w"]))
    assert bridged["components"][0]["w"] == direct["components"][0]["w"] == 0.4
    assert bridged["components"][1]["w"] == direct["components"][1]["w"] == 0.5
    np.testing.assert_array_equal(bridged["beta_multi"], direct["beta_multi"])
    np.testing.assert_array_equal(bridged["b_total"], direct["b_total"])
