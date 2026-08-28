# Observable Spatial Agencity Fields

**Scientific status: EXPERIMENTAL**

AgencityStudio 0.12 exposes the public AgencityLab 1.1.3 observable-field API without reproducing Agencity equations in Studio.

## Public AgencityLab contract

Studio calls only:

```python
from agencitylab.fields import compute_agencity_field
```

The inspected AgencityLab 1.1.3 signature is:

```python
compute_agencity_field(
    u,
    t,
    *,
    spatial_axes=None,
    A_ref,
    tau,
    w=None,
    P_c,
    time_axis=0,
    metadata=None,
) -> ObservableAgencityFieldResult
```

The installed 1.1.3 implementation requires `u` to have at least two non-empty dimensions and finite real values. `t` is a finite one-dimensional array with at least three samples, exactly matches the selected time dimension, and is strictly increasing. `time_axis` accepts NumPy-style negative indices; Studio records the normalized axis in the immutable Run snapshot.

`spatial_axes=None` is preserved as such when the user selects spatial indices. AgencityLab then represents each spatial dimension by sample indices. With explicit spatial coordinates, exactly one finite strictly monotone one-dimensional coordinate array must be supplied for every spatial dimension, in exact dimension order and with exact lengths.

AgencityLab 1.1.3 supports:

- `A_ref`: scalar or exact spatial shape;
- `tau`: scalar or exact spatial shape;
- `w`: `None`, scalar, or exact spatial shape;
- `P_c`: scalar, exact spatial shape, or exact original `u` shape for a space-time field.

`A_ref`, `tau` and explicit `w` values must be strictly positive. `P_c` must be finite and non-negative; local `P_c = 0` is valid.

When Studio submits `w=None`, it submits literal `None`. The inspected AgencityLab 1.1.3 implementation then resolves its effective field internally and records `w_mode = fallback_w_equals_tau`. This is an AgencityLab implementation convention. Studio does not materialize `w=tau` itself.

The public result contains `t`, `spatial_axes`, `u`, `u_star`, `X_star`, `A_star`, `M`, `O`, `D`, `S`, `J`, `U`, `beta`, `b`, resolved `A_ref`, `tau`, `w`, `P_c`, `time_axis`, `spatial_shape`, metadata, status, model and backend. Public aliases `beta_obs` and `b_obs` identify the observable field explicitly. AgencityLab 1.1.3 does **not** return a field `theta`; Studio therefore never reconstructs one as `arg(beta_obs)`.

## Scientific boundary

The construction is exclusively:

```text
u(x1, x2, ..., xd, t)
    ↓ independently at each spatial location
canonical temporal scalar pipeline
    ↓
beta_obs(x1, ..., xd, t)
b_obs(x1, ..., xd, t)
```

CRM is evaluated along the temporal axis independently at each spatial location. No spatial CRM is introduced.

`beta_obs(x,t)` is an observable spatial Agencity field. It is not the autonomous dynamical field `phi(x,t)`.

Plan 12 introduces:

```text
No spatial CRM.
No spatial derivative.
No PDE.
No autonomous field dynamics.
No domain walls.
No vortices.
No thermodynamics.
No gravity.
```

It also introduces no automatic bridge from `beta_obs` to `phi`. Autonomous-field models and other research extensions belong to a separate future RESEARCH workflow.

A non-zero local `beta_obs` or a large `b_obs` is not by itself evidence of coherent or "real" agencity.

## Immutable N-dimensional source

The existing tabular Dataset importer cannot faithfully encode arbitrary `(time, x, y, ...)` arrays without flattening. Plan 12 therefore adds the smallest source extension: an **NPZ-backed `DatasetVersion`**. It is not a second Data Workspace or a parallel ownership model.

```text
Workspace
  ↓
Project
  ↓
Dataset
  ↓
DatasetVersion (exact immutable NPZ bytes + SHA-256)
```

The NPZ source stores named NumPy arrays. During inspection, Studio records each array's key, shape, dtype, element count and NPY-member SHA-256. Scientific roles are not inferred during import.

Before allocating user arrays, the inspector validates ZIP member paths, compressed-container structure, NPY headers, configured element/uncompressed-byte limits and dtype. Object arrays are rejected and user data are always loaded with `allow_pickle=False`.

The Analysis builder explicitly selects:

- the observable array `u`;
- the time coordinate array `t`;
- `time_axis`;
- spatial coordinate arrays or `spatial_axes=None` sample-index mode;
- spatial axis names and units when physically known;
- the System Revision and observable;
- physical parameter scalar/map modes.

Studio never guesses the longest dimension as time and never invents physical coordinates such as metres when only an index exists.

## Physical parameter provenance

Scalar `A_ref`, `tau`, explicit scalar `w`, and scalar `P_c` are taken from the selected immutable `SystemRevision`. Field maps are exact named arrays from the pinned NPZ source and store shape, dtype, NPY-member SHA-256, unit and explicit physical/contextual provenance in the Run snapshot.

Studio does not estimate maps from standard deviation, MAD, range, FFT, autocorrelation or any other signal statistic. Such estimates would be heuristic/experimental inference and are outside this Analysis contract.

Map shapes are exact:

```text
A_ref spatial map: spatial_shape
tau spatial map:   spatial_shape
w spatial map:     spatial_shape
P_c spatial map:   spatial_shape
P_c space-time:    exact u.shape
```

No broadcasting rule beyond the public AgencityLab scalar/spatial/space-time contract is invented by Studio.

## No hidden field preprocessing

During Analysis, Studio performs no interpolation, resampling, smoothing, filtering, normalization, clipping, NaN filling, row dropping, spatial averaging or inferred reshape. The original `u` array and axis order are passed to AgencityLab as pinned.

A non-zero `time_axis` remains a non-zero `time_axis`; Studio does not silently transpose the scientific source to make it look conventional.

## Field Run and result artifact

Plan 12 reuses `Analysis` and `AnalysisRun`. A queued field Run freezes:

- source DatasetVersion and source SHA-256;
- array inventory;
- exact `u.shape` and dtype;
- normalized `time_axis`;
- spatial shape and axis order;
- spatial coordinate identities and hashes;
- System Revision and fingerprint;
- observable identity;
- parameter modes, scalar values or map identities/hashes/provenance;
- Studio and AgencityLab versions;
- public function and scientific status;
- execution fingerprint.

Celery receives only the Run UUID. The worker reloads immutable source bytes, verifies the source hash, loads only named arrays, calls the public field API, and publishes one immutable result artifact. Duplicate delivery is guarded by the Run state machine.

The field result uses the existing private `ZIP_NPY_JSON` pattern. N-dimensional arrays remain `.npy` arrays with original shape and dtype. Complex `U`, `beta` and `b` values are not downcast or split destructively. The artifact SHA-256 is part of the Run provenance.

## Visualization

Apache ECharts 6.1.0 remains the visualization engine.

For one spatial dimension, Studio provides a display-only sampled time × space heatmap for `u`, `|beta_obs|` and `|b_obs|`, with Re/Im/magnitude/phase representations for complex fields.

For two spatial dimensions, Studio provides a map at one exact selected time. For higher-dimensional fields, one or two displayed spatial dimensions are selected and the remaining dimensions are fixed by explicit indices. Studio never reduces dimensions by an automatic mean, max or PCA.

The exact-point endpoint always returns the full-resolution stored cell. The local trace endpoint returns the temporal trajectory at one exact spatial location. Display reduction changes only what is sent to the browser; it never changes the scientific artifact or exact inspector.

## Reproducibility and equivalence

Tests compare:

1. direct `compute_agencity_field(...)` with `Studio -> labbridge -> compute_agencity_field(...)` using the same arrays and parameters;
2. selected field locations with direct public scalar `compute_agencity(...)` on the corresponding temporal trajectory;
3. serialized complex arrays with the public Lab result after storage and reader round-trip.

The expected scientific values come from AgencityLab's public APIs, not from duplicated Studio formulas.
