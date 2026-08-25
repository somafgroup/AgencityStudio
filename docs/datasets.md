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

## Dataset is not System

A Dataset answers: **what measurements/data do I have?** A Plan 6 `System` answers: **what physical/scientific system do those measurements represent, and what contextual parameters are justified for future analysis?**

The two objects share a Project but are intentionally independent. A System may later be used with several DatasetVersions or PreparedDataArtifacts, and a Dataset does not automatically create or select a System.

`DatasetColumn` is therefore not an `ObservableDefinition`. A source column may have a technical header such as `col_07`, while the System observable may be scientifically named “Rotor angular position”. Plan 6 persists no mapping between them; future Analysis configuration will choose the exact data source and map its columns to an exact SystemRevision explicitly.

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

The `OBSERVABLE` Dataset role is an acquisition/data annotation only. It does not bind the column to a System observable and does not define `A_ref`, `tau`, `w` or `P_c`.

## Inspection diagnostics

The Data Workspace may report:

- row and column counts;
- source size;
- missing values;
- non-numeric values in Observable candidates;
- non-finite numeric values;
- duplicate headers;
- numeric minimum and maximum;
- datetime range;
- duplicate time values;
- non-monotonic time;
- observed sampling interval information;
- observed sampling frequency when its unit is unambiguous;
- irregular sampling;
- potential sampling gaps using an explicitly documented inspection heuristic.

These are data-quality diagnostics. They do not define `A_ref`, `tau`, `w` or `P_c`.

In particular, observed sampling interval `dt` remains an acquisition property. It is never copied into a System as `tau` or `w`. Dataset standard deviation, MAD, range, extrema and similar signal statistics never populate `A_ref` or `P_c`.

The raw Data Workspace never sorts, drops, fills, interpolates, resamples, smooths, filters or normalizes a `DatasetVersion` in place. Plan 5 adds a separate preparation layer that materializes explicit derived artifacts while leaving this raw contract unchanged. See [Data Preparation, Transformations and Provenance](data-preparation.md).

## Preview

Preview is server-side paginated. The browser receives only the requested page rather than the full source. Preview values are rendered as escaped user content; they are not interpreted as HTML or executable spreadsheet formulas.

Any future cache or query artifact used to accelerate preview is an implementation artifact only and must never replace the immutable raw source.

## Access control

Datasets inherit existing Project/Workspace permissions; there is no Dataset-specific ACL.

- Owner: read, import, upload versions, edit metadata/annotations, download and delete when no protected descendants exist.
- Editor: read, import, upload versions, edit metadata/annotations and download.
- Analyst: read, preview and download raw data; Plan 5 additionally allows creation of immutable derived preparations without granting raw mutation rights.
- Viewer: read, preview and download.
- Non-members: safe 404-style denial.

Raw files are private by default. Download goes through an authorized Django endpoint and uses attachment disposition. A source hash never grants access to an artifact in another Workspace.

## Deletion and retention

A Project containing Datasets cannot be hard-deleted. The Datasets must first be handled explicitly. Plan 6 extends the same conservative Project boundary to Systems: the presence of either retained Datasets or Systems blocks Project hard deletion.

Dataset deletion is Owner-only and removes related metadata/private raw artifacts through the storage service when deletion is allowed.

A `DatasetVersion` referenced by a `DataPreparation` is protected by a database foreign-key contract. Derived lineage must be handled explicitly before that exact source version can disappear. This prevents a prepared result from losing the source it claims in provenance.

Database transactions and object/file storage are separate atomicity domains, so cleanup is explicit and conservative rather than pretending both systems share one transaction.

## Scientific boundary

The Data Workspace answers questions such as what source was imported, what its exact hash is, which columns exist and whether the observed time axis has quality issues.

It does not answer what `A_ref`, `tau`, `w`, `P_c`, `beta` or `b` are. No canonical Agencity pipeline equation belongs in `datasets/`.

Plan 6 Systems hold the documented physical/contextual side of future analysis, independently from data. See [Systems & Scientific Context](systems.md). The future Analysis layer—not Dataset and not System—will associate one exact DatasetVersion or PreparedDataArtifact with one exact SystemRevision and observable mapping.
