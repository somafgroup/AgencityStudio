# Data Preparation, Transformations and Provenance

AgencityStudio prepares data only through explicit user-requested transformations. Preparation is upstream of AgencityLab and does not calculate agencity or infer canonical physical parameters.

## Raw versus prepared

The immutable source contract remains:

```text
DatasetVersion (ORIGINAL, immutable)
        ↓ pinned source UUID + source SHA-256
DataPreparation (ordered recipe)
        ↓ asynchronous deterministic execution
PreparedDataArtifact (PREPARED, immutable)
```

A preparation always references one exact `DatasetVersion`. It never references `Dataset.current_version` dynamically. A later Dataset version therefore cannot alter the lineage of an existing preparation.

The original source path, exact source bytes, import metadata and `source_sha256` are never changed by a preparation.

A PreparedDataArtifact is still data, not a System. Plan 7 may select the artifact as one exact canonical Analysis source together with an exact SystemRevision and explicit observable mapping. That association exists on AnalysisRun; it is never written back into preparation metadata.

## Recipe contract

Recipes are ordered JSON structures. Order is part of provenance because operations are not generally commutative. The recipe fingerprint is derived from:

```text
source SHA-256
+ canonical recipe serialization
+ preparation engine identifier/version
```

The recipe fingerprint detects an equivalent request configuration. It is not the hash of the output data. The output receives its own `prepared_sha256` computed from the exact materialized artifact bytes.

A Draft recipe may be edited or reordered. Running it freezes that record by moving it through `QUEUED` and `PROCESSING`. A READY result is not edited in place; a changed recipe or re-run creates another preparation record.

## Supported transformations

Plan 5 implements these explicit operations:

- time-range crop with inclusive start/end bounds;
- row-range selection for non-physical row indexing;
- explicit row exclusion by one-based row number;
- missing-value row removal on selected columns;
- linear interpolation on selected numeric columns using an explicitly selected, strictly increasing coordinate column, with no boundary extrapolation;
- uniform resampling with an explicit target `dt` and linear interpolation;
- moving-average smoothing with an explicit odd window size and preserved edge samples;
- explicit compatible unit conversion through Pint;
- explicit column selection;
- explicit stable ascending time sort.

Filtering is deliberately not included in the final Plan 5/7 scope. A frequency-domain filter requires a clearly defined sampling contract, cutoff/order/phase behaviour and, for downsampling, an explicit anti-alias policy. Studio does not introduce SciPy and hidden filter defaults merely to add a checkbox.

## Important numerical behaviour

Linear interpolation requires a strictly increasing coordinate without duplicates. Studio does not silently choose which duplicate timestamp to keep. Missing values at the edges are not extrapolated.

Resampling requires a strictly increasing time axis. `target_dt` is a sampling interval only. It is not `tau` and it is not the CRM memory window `w`. Studio never derives either quantity from sampling. System revisions document `tau` and `w` independently from the prepared-data acquisition grid.

Moving-average smoothing is never automatic and records its target columns, window length and boundary behaviour.

Unit conversion preserves the original unit in source metadata and changes the unit only on the prepared result. The same Pint dependency is reused by Systems and Analysis for dimensional validation of known units, but preparation conversion and scientific-context validation remain separate operations. Neither layer guesses an unknown unit.

This explicit conversion path is also the required remedy when canonical Analysis sees dimensionally compatible but differently scaled units. Analysis itself never converts `km/h` to `m/s`, `ms` to `s`, or any other source values before calling Lab.

## Materialization

Plan 5 materializes prepared tabular results as deterministic UTF-8 CSV with comma delimiter and LF line endings. Numeric precision is not intentionally down-cast. The result is written through the same confined private storage abstraction used by the Data Workspace and uses write-once object creation.

The worker first applies the entire recipe, inspects the resulting table, writes the artifact and calculates its SHA-256. The database record is marked READY only after the immutable artifact is complete. Failed executions keep the source and recipe but do not publish a partial READY artifact.

The current execution engine is intentionally bounded by `DATA_PREPARATION_MAX_ROWS`. This is an operator-configurable memory-safety limit for the current in-memory implementation; it is not a scientific restriction.

## Prepared inspection

The prepared result receives a new inspection snapshot including row/column counts, missing/non-finite values and time-axis quality information when applicable. Raw `DatasetVersion` quality findings remain untouched.

A successful preparation does not imply that data are automatically valid for an Agencity analysis. Analysis still requires an exact SystemRevision, explicit mapping and structural compatibility with the public canonical scalar input contract.

Analysis execution does **not** perform a second preparation pass. It reads the selected prepared bytes and column positions as they exist. There is no hidden sorting, filling, interpolation, resampling, smoothing, filtering, normalization or unit conversion between PreparedDataArtifact and AgencityLab.

## Provenance

A preparation records:

- exact source DatasetVersion UUID and source SHA-256;
- ordered recipe and normalized parameters;
- recipe fingerprint;
- AgencityStudio version;
- Python version;
- transformation engine identifier/version;
- relevant NumPy and Pint versions;
- execution timestamps and duration metadata;
- transformation warnings/notes;
- output row/column counts;
- immutable artifact path, size and prepared SHA-256;
- prepared column metadata and quality inspection.

AgencityLab version remains part of the overall Studio environment, but preparation provenance does not claim that AgencityLab executed these generic Studio transformations.

When a PreparedDataArtifact is used by an AnalysisRun, the Run additionally snapshots its artifact UUID, `prepared_sha256`, column mapping and complete preparation lineage back to the original DatasetVersion. The PreparedDataArtifact foreign key is protected from deletion while referenced.

System scientific provenance is separate. For example, a preparation may record resampling to `dt=0.01 s`, while a SystemRevision separately records `tau=0.8 s`, its physical origin and justification. Neither provenance stream overwrites the other.

## Permissions

Preparation reuses Workspace/Project permissions rather than creating another ACL:

- Owner: create, edit Drafts, run, duplicate, download and delete preparations;
- Editor: create, edit Drafts, run, duplicate and download;
- Analyst: create, edit Drafts, run, duplicate and download derived data while raw Dataset metadata/source remain read-only;
- Viewer: view and download existing prepared results but cannot mutate or run preparations;
- non-member: safe 404-style denial.

This makes the Analyst role useful for scientific experimentation while preserving the immutable original source. Analyst can also select an existing READY prepared result in a canonical Analysis.

Prepared artifacts remain private and are downloaded only through authorized endpoints. No hash, UUID or storage path is an authorization mechanism.

## Scientific boundary

The preparation layer contains no Agencity formula and does not infer:

```text
A_ref
tau
w
P_c
X
A
M
O
D
S
J
Theta
beta
b
```

In particular, statistical normalization is not used to imitate canonical normalization. Systems own explicit documentation of `A_ref`, `tau`, `w` and `P_c`; preparation does not calculate, suggest or override them.

Plan 7 is the first layer that deliberately combines an exact data artifact and SystemRevision for AgencityLab execution, but it still does not transform the selected data. See [Canonical Analyses](analyses.md).
