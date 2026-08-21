# AgencityStudio UI foundation

Plan 1 establishes a server-rendered scientific workspace rather than a SPA. Django owns navigation, URLs, permissions and persisted domain state. HTMX is reserved for useful server-side partial refreshes; Alpine.js owns only local interface state such as mobile navigation, command palette, theme selection and lightweight feedback.

## Frontend stack

- Tailwind CSS 4.3.x for utility generation and reusable component classes.
- HTMX 2.0.x for partial server interactions.
- Alpine.js 3.16.x for local UI state.
- Lucide 1.31.x as the single icon family.
- esbuild for the small JavaScript bundle.

Run `npm install` and `npm run build` for a one-off build. Use the CSS/JS watch scripts during local frontend work. Generated files under `static/css` and `static/js` are build artifacts and are not source files. The output directories are retained in Git so a fresh checkout always has valid build targets.

## Visual principles

The interface should be scientific, calm, precise and information-dense without becoming cramped. Prefer neutral surfaces, restrained accents, strong typography hierarchy and functional motion. Avoid decorative gradients, glass effects, gaming aesthetics and oversized marketing layouts.

## Components

Reusable classes live in `frontend/styles/app.css`. The foundation includes buttons, icon buttons, fields, labels, help/error text, inputs, selects, textareas, check/radio rows, toggles, cards, panels, dividers, badges, alerts, navigation, breadcrumbs, empty states, skeletons, spinners, tables, tabs, dropdowns, dialogs, toasts, toolbars and page/section headers.

Django include templates under `templates/components/` are used when server-side composition adds value. Do not create a template component merely to wrap one CSS class.

The development-only `/dev/ui/` page shows representative primitives when `DEBUG=True`.

## Scientific statuses

The official visible status vocabulary is:

`CANONICAL`, `DIAGNOSTIC`, `NUMERICAL`, `EXPERIMENTAL`, `RESEARCH`, `LEGACY`, `DEPRECATED`, `WARNING`.

Every status includes text; colour is supplementary only. Status styling never changes the scientific meaning supplied by AgencityLab or project metadata.

## Themes

`light`, `dark` and `system` are supported. The preference is stored in `localStorage` as `agencity-theme` and applied before the stylesheet loads to reduce incorrect-theme flash. Future plotting code should listen for the `agencity:theme-changed` event instead of reading unrelated DOM styles.

## Accessibility and responsive behaviour

Use semantic controls, associated labels, visible focus, keyboard-accessible navigation and native dialog semantics where possible. The shell becomes an off-canvas navigation on small screens. Motion is reduced under `prefers-reduced-motion`. Do not encode status or errors by colour alone.

## HTMX and Alpine rules

Keep normal page navigation as normal links. Use HTMX only for partial server content that benefits from refresh without a full navigation; the current system-status panel is the reference example. Keep Alpine state local to the shell or component. Domain state belongs in Django, not in a global Alpine store.

## Adding UI

1. Reuse an existing semantic component class.
2. Add a reusable class to `frontend/styles/app.css` when a pattern repeats.
3. Add a Django include only when server composition is useful.
4. Add JavaScript only when HTML/HTMX cannot express the interaction cleanly.
5. Add Playwright coverage only for a meaningful workflow, not visual trivia.
