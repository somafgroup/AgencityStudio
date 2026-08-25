# Data Workspace

AgencityStudio's Data Workspace imports, preserves and inspects scientific source data. It does not perform Agencity calculations and it does not infer canonical physical parameters from signal statistics.

## Ownership and versioning

The ownership chain is:

```text
User
  ↓ membership
Workspace
  ↓
Project
  ↓
Dataset
  ↓
DatasetVersion
```

`Dataset` is the stable logical identity of a data collection. `DatasetVersion` is one exact raw-source snapshot. Dataset and version identifiers are UUIDs. Version numbers are monotonically allocated per Dataset and are protected by a database uniqueness constraint.

A successful inspection does not silently replace the current version. The user confirms a READY version before `Dataset.current_version` is updated. A FAILED new version never makes the previous current version unusable.

## Dataset is not System or Analysis

A Dataset answers: **what measurements/data do I have?** A `System` answers: **what physical/scientific system do those measurements represent, and what contextual parameters are justified?** An `AnalysisRun` answers: **which exact source, SystemRevision, mapping and parameters were executed?**

The objects share a Project but are intentionally independent. A System may be used with several DatasetVersions or PreparedDataArtifacts, and a Dataset does not automatically create or select a System.

`DatasetColumn` is not an `ObservableDefinition`. A source column may have a technical header such as `col_07`, while the System observable may be scientifically named “Rotor angular position”. Plan 7 maps them explicitly and pins both identities in the AnalysisRun.

## Raw-source immutability

Every source artifact is stored under a generated private path derived from Project, Dataset and DatasetVersion UUIDs. The original client filename is metadata only and is never used as a storage path.

Raw artifacts are write-once. New uploads create new DatasetVersions; Studio never overwrites an earlier raw source. A SHA-256 digest is calculated from the exact uploaded or pasted bytes while they are written. The digest is therefore a source fingerprint, not a hash of parsed or normalized values.

Pasted tabular data is encoded and stored as its own original source artifact before inspection.

## Supported formats

The Data Workspace supports:

- CSV;
- TSV;
- structured TXT with an explicit or detected delimiter;
- XLSX;
- pasted delimited text.

Legacy `.xls`, JSON, Parquet, HDF5, NPY and NPZ are not part of the current import scope.

XLSX inspection uses `openpyxl` in read-only mode. Workbook macros are not executed. Formula cells are preserved as source values and reported as an inspection warning rather than evaluated as code.

## Import configuration

A DatasetVersion stores the configuration actually used for parsing, including applicable fields such as encoding, delimiter, header presence, decimal separator and XLSX sheet. Automatically detected values are distinguished from explicit user choices in the import metadata.

The importer identifier and importer schema version are also retained so future parser changes remain traceable.

## Asynchronous inspection

The HTTP request stores the raw source and creates the DatasetVersion transactionally. The Celery inspection task is enqueued with `transaction.on_commit()` so a worker never depends on an uncommitted database row.

The lifecycle is intentionally small:

```text
PENDING → PROCESSING → READY
                    ↘ FAILED
```

Studio reports real states rather than invented percentages. Re-inspection increments an inspection generation. A stale worker result is ignored if a newer configuration has already been submitted.

## Column metadata

`DatasetColumn` preserves column position and the original source header independently. Duplicate source headers therefore remain distinct columns instead of being merged by name.

Inspection infers lightweight types such as numeric, datetime, boolean, text, mixed or empty. Inference is descriptive and may be corrected later by workflow-specific layers.

Users with write permission can annotate columns with one of:

```text
TIME
OBSERVABLE
OTHER
```

At most one column can be the primary Time column for the current tabular workflow. Multiple columns may be marked Observable. Units are stored as user-declared metadata and are not silently converted.

The `OBSERVABLE` Dataset role is an acquisition/data annotation only. It does not bind the column to a System observable and does not define `A_ref`, `tau`, `w` or `P_c`. Plan 7 may use role annotations as visible defaults, but the Run records an explicit mapping by stable position/identity.

## Inspection diagnostics

The Data Workspace may report row/column counts, source size, missing/non-numeric/non-finite values, duplicate headers, numeric ranges, datetime ranges, duplicate/non-monotonic time, observed sampling interval/frequency, irregular sampling and explicit quality heuristics.

These are data-quality diagnostics. They do not define `A_ref`, `tau`, `w` or `P_c`.

Observed sampling interval `dt` remains an acquisition property. It is never copied into a System as `tau` or `w`. Dataset standard deviation, MAD, range, extrema and similar signal statistics never populate `A_ref` or `P_c`.

The raw Data Workspace never sorts, drops, fills, interpolates, resamples, smooths, filters or normalizes a `DatasetVersion` in place. Plan 5 provides a separate preparation layer that materializes explicit derived artifacts while leaving this raw contract unchanged. See [Data Preparation, Transformations and Provenance](data-preparation.md).

## Use by canonical Analysis

Plan 7 may select a READY `DatasetVersion` directly as one exact Analysis source. The Run stores the DatasetVersion UUID, exact raw SHA-256, source type, selected coordinate/observable column identities and the relevant source metadata. It never resolves `Dataset.current_version` later to reinterpret history.

The Analysis source adapter rereads the immutable artifact with the recorded importer configuration and materializes only the selected numeric vectors. It does not change row order or values. Non-finite, non-numeric, non-monotonic or irregular sources are blocked/rejected with guidance to create explicit Prepared Data.

Canonical execution uses a strict unit policy because AgencityLab 1.1.3 treats unit strings as descriptive metadata and performs no conversion. Dimensionally compatible but differently scaled values such as `km/h` and `m/s` must be converted upstream in an explicit PreparedDataArtifact, never silently inside Analysis.

A DatasetVersion referenced by an AnalysisRun is protected from deletion. Creating or confirming a later DatasetVersion never changes an existing Run.

## Preview

Preview is server-side paginated. The browser receives only the requested page rather than the full source. Preview values are rendered as escaped user content; they are not interpreted as HTML or executable spreadsheet formulas.

Any future cache or query artifact used to accelerate preview is an implementation artifact only and must never replace the immutable raw source.

## Access control

Datasets inherit existing Project/Workspace permissions; there is no Dataset-specific ACL.

- Owner: read, import, upload versions, edit metadata/annotations, download and delete when no protected descendants exist.
- Editor: read, import, upload versions, edit metadata/annotations and download.
- Analyst: read, preview and download raw data; may create immutable preparations and Analyses without gaining raw mutation rights.
- Viewer: read, preview and download.
- Non-members: safe 404-style denial.

Raw files are private by default. Download goes through an authorized Django endpoint and uses attachment disposition. A source hash never grants access to an artifact in another Workspace.

## Deletion and retention

A Project containing Datasets cannot be hard-deleted. Datasets must first be handled explicitly. The same conservative Project boundary covers Systems and Analyses.

Dataset deletion is Owner-only and removes related metadata/private raw artifacts through the storage service when deletion is allowed.

A `DatasetVersion` referenced by a `DataPreparation` or `AnalysisRun` is protected by database foreign-key contracts. Derived lineage and completed-run reproducibility must be handled explicitly before that exact source can disappear.

Database transactions and object/file storage are separate atomicity domains, so cleanup is explicit and conservative rather than pretending both systems share one transaction.

## Scientific boundary

The Data Workspace answers what source was imported, its exact hash, which columns exist and whether the observed time axis has quality issues.

It does not answer what `A_ref`, `tau`, `w`, `P_c`, `beta` or `b` are. No canonical Agencity pipeline equation belongs in `datasets/`.

Systems hold the documented physical/contextual side independently from data. Analysis makes the explicit association and delegates all canonical quantities to AgencityLab. See [Systems & Scientific Context](systems.md) and [Canonical Analyses](analyses.md).
