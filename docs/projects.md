# Projects

Plan 3 introduces the durable scientific Project container. A Project organises work; it does not perform AgencityLab computation.

## Ownership and identity

Every `projects.Project` belongs to exactly one `workspaces.Workspace`. Users reach Projects through their existing workspace membership. `created_by` records application provenance only and uses `SET_NULL`, so deleting or deactivating a creator never deletes the scientific container.

Projects use a UUID primary key for stable cross-instance/export references. A readable slug is generated at creation, unique within the owning workspace and intentionally remains stable when the Project is renamed. Project URLs include the workspace slug, UUID and stable Project slug. None of these identifiers are security controls; membership is always checked server-side first.

## Permissions

Plan 3 inherits workspace roles instead of introducing a second ACL system:

| Role | View | Create | Edit | Archive/restore | Duplicate | Delete |
| --- | --- | --- | --- | --- | --- | --- |
| Owner | yes | yes | yes | yes | yes | yes |
| Editor | yes | yes | yes | yes | yes | no |
| Analyst | yes | no | no | no | no | no |
| Viewer | yes | no | no | no | no | no |

Instance `is_staff`/`is_superuser` flags do not bypass workspace membership. A non-member receives 404 for private Project lookup; a member attempting an action outside their role receives 403.

Fine-grained per-Project sharing/public links are deliberately deferred. They require an explicit collaboration/sharing design rather than a second permission matrix hidden inside Plan 3.

## Lifecycle

Projects have only two business states: `ACTIVE` and `ARCHIVED`. Archiving preserves identity and metadata and removes the Project from the normal active list. Restoring reactivates the same record.

Permanent deletion is Owner-only and requires exact-name confirmation in the UI. It deletes the Project and its lightweight application activity. Because Projects will later contain scientific children, `Project.workspace` uses `PROTECT`, and organisation workspace deletion is explicitly refused while Projects remain.

Duplication creates a new UUID, timestamps and slug, makes the current user the creator, starts active, and copies only Plan 3 metadata. It does not copy activity history or pretend to duplicate future Datasets, Systems or Analyses.

## Metadata boundary

Plan 3 metadata is organisational/contextual: name, description, free-text domain, tags and Project-level notes. Workspace identity represents the organisation. Scientific parameters such as `A_ref`, `tau`, `w`, `P_c`, observable and units do not belong on Project and are reserved for future System/Analysis layers.

## Activity

`ProjectActivity` records lightweight application events: create, metadata update, archive, restore and duplicate. It is explicitly **not scientific provenance**. Scientific provenance will later include Dataset versions, System/Analysis configuration, AgencityLab version, preprocessing and run metadata.

A permanent Project deletion is logged operationally by identifiers but has no durable ProjectActivity row because the Project itself is removed. A durable audit subsystem remains a separate future concern.

## URLs and lists

`/projects/` shows Projects for the active workspace only, with active/archived filters, simple name/description/domain search, sorting and Django pagination. Workspace overview and Dashboard show real recent Project data; they never fabricate future Dataset or Analysis counts.

Project workspace pages are nested under the workspace and expose Overview, Activity and Settings now. Datasets, Systems, Analyses, Comparisons, Reports and Files are honest empty-state shells until their own Plans are implemented.
