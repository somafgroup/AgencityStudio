# Systems and scientific context

Plan 6 introduces `System` as the Project-owned identity for the physical or scientific system being studied. A System is not a Dataset and it is not an Analysis run.

## Ownership and identity

The ownership chain is:

```text
Workspace
  -> Project
       -> System
```

`System.id` is a stable UUID. The Project is the durable owner; `created_by` records application provenance and uses safe user-deletion semantics. A System may be reused later with different original DatasetVersions or PreparedDataArtifacts because the mapping between data and scientific context belongs to the future Analysis configuration.

## Immutable scientific revisions

Mutable organisational identity (`name`, short description, active/archive state) lives on `System`. Scientific context lives on `SystemRevision`.

Changing an observable, `A_ref`, `tau`, `w`, `P_c`, scientific mechanism, units, parameter provenance or references creates a new revision. Historical revisions cannot be updated through normal model or Admin workflows. `System.current_revision` is an ergonomic pointer only; future AnalysisRuns must reference an exact revision UUID.

Revision numbers are unique within one System and are allocated while locking the System row. Each revision has a deterministic `configuration_fingerprint` (SHA-256) over scientific content, observables and references. Timestamps and UI state are deliberately excluded. Equal fingerprints mean equal serialized configuration, not scientific correctness.

## AgencityLab 1.1.3 public contract

Plan 6 inspected the public `agencitylab.compute_agencity` signature from the 1.1.3 release before defining Studio validation. The relevant public arguments are `A_ref`, `tau`, `w`, `P_c`, `unit`, `coordinate_unit`, `power_unit`, `observable_kind`, `domain`, `mechanism`, `system_type`, `environment`, `geometry` and `metadata`.

Studio mirrors only the input facts needed for documentation:

- explicit `A_ref` is finite and strictly positive;
- explicit `tau` is finite and strictly positive;
- explicit `w` is finite and strictly positive;
- scalar `P_c` is finite and non-negative, so `P_c = 0` is valid;
- `w` is distinct from `tau`;
- Lab performs no implicit unit conversion.

AgencityLab also exposes contextual `auto` resolution for some parameters. Plan 6 does **not** use that as a substitute for scientific documentation. A technically optional Python argument is not automatically a scientifically justified parameter.

## Physical/contextual parameters

`A_ref`, `tau`, `w` and `P_c` are explicitly labelled **PHYSICAL / CONTEXTUAL** in the UI. Studio does not derive them from a Dataset or PreparedDataArtifact.

In particular, Plan 6 contains no rule equivalent to:

```text
A_ref <- std / MAD / range / max(signal)
tau   <- dt / dominant period / autocorrelation peak
w     <- automatic signal window
P_c   <- measured signal power
```

### A_ref

A revision stores the parsed finite positive value, the value representation entered by the user, unit, origin, source detail and justification. If Pint recognizes both the primary observable unit and `A_ref` unit, they must be dimensionally compatible. Unknown unit labels are preserved and reported as not automatically validated rather than treated as dimensionless.

### tau

`tau` is the characteristic structural time of the System. A known unit must have time dimensionality. The UI explicitly distinguishes acquisition/preparation sampling interval `dt` from structural `tau`.

### w

A revision stores one of two distinct states:

- `UNSPECIFIED`: no numerical `w` is persisted;
- `EXPLICIT`: a finite positive value and its provenance are persisted.

`UNSPECIFIED` is **not** silently rewritten to `w = tau` in Studio. A future Analysis may pass `None` to AgencityLab, whose documented 1.1.3 convention can then resolve `w = tau`; the future run must record that resolved context.

### P_c

Plan 6 supports the fixed scalar case. A known unit must have power dimensionality. Zero is accepted because it is valid under the inspected public Lab contract. Time-varying/component-specific power remains a future workflow rather than a browser-supplied callable.

## Observables

`ObservableDefinition` describes scientific meaning independently of `DatasetColumn`. It records name, optional symbol/description, unit, kind, measurement nature and source description. A revision supports multiple observables and at most one primary observable, keeping the Plan 6 UX scalar-first without making the schema permanently scalar-only.

Plan 6 does not persist Dataset-column-to-observable mappings. The future Analysis configuration will explicitly pair selected data with an exact SystemRevision.

## References and parameter provenance

`ScientificReference` is deliberately lightweight: title, citation, DOI, URL, notes and optional flags indicating which canonical physical/contextual parameter the source supports. User-supplied URLs and citations are rendered as escaped content; no external bibliographic service is required.

For each physical/contextual parameter, origin and justification are distinct from general scientific notes. Origin choices are a small ergonomic vocabulary (measurement, calibration, manufacturer, literature, model, protocol, convention, other), with free-text detail.

## Draft versus Documented

A Draft revision may be incomplete so scientists can build context progressively. `DOCUMENTED` means required context is present; it does **not** mean experimentally validated or theoretically proven.

A documented revision requires a primary observable with unit plus `A_ref`, `tau`, `P_c` values/units/origins/justifications. If `w` is explicit, its value/unit/origin/justification are also required. `w` may intentionally remain unspecified.

## Permissions

System permissions inherit Workspace membership; there is no System ACL.

| Role | View | Create / revise / duplicate | Rename / archive / restore | Hard delete |
| --- | --- | --- | --- | --- |
| Owner | yes | yes | yes | yes |
| Editor | yes | yes | yes | no |
| Analyst | yes | yes | no | no |
| Viewer | yes | no | no | no |
| Non-member | safe not-found | no | no | no |

Analyst can therefore perform scientific configuration work without receiving raw Dataset mutation or Workspace-administration rights.

## Lifecycle and deletion

Archiving a System preserves every revision. Duplicating a System creates a new System UUID and a new Revision 1 copied from the source's current scientific context; history and future analyses are not copied.

A Project that contains Systems cannot be hard-deleted. Plan 7 will add explicit protection from deleting System revisions referenced by historical AnalysisRuns.

## Scientific boundary

Systems do not call `compute_agencity`, `analyze_agencity` or `scientific_workflow`. They store no `u*`, `X*`, `A*`, `M`, `O`, `D`, `S`, `J`, `Theta`, `beta` or `b`. No Theory of Agencity equation is duplicated in the Systems app.

The future Plan 7 will join:

```text
DatasetVersion or PreparedDataArtifact
+
SystemRevision
+
explicit observable mapping
-> Analysis configuration / review / execution
```
