"""Forms for explicit autonomous RESEARCH field configuration."""

from __future__ import annotations

from django import forms
from django.db.models import F
from django.utils.translation import gettext_lazy as _

from datasets.field_source import FIELD_SOURCE_FORMAT
from datasets.models import DatasetImportStatus, DatasetVersion

from .models import AnalysisKind, AnalysisRun, RunStatus
from .research_contract import (
    BOUNDARY_CHOICES,
    BOUNDARY_PERIODIC,
    INITIAL_CHOICES,
    INITIAL_DOMAIN_WALL,
    INITIAL_NPZ,
    INITIAL_OBSERVABLE_BRIDGE,
    INITIAL_VORTEX_PROFILE,
    MODEL_CHOICES,
    MODEL_DISSIPATIVE_KLEIN_GORDON,
    MODEL_TDGL,
)


def _csv_ints(value: str, *, name: str, minimum: int | None = None) -> list[int]:
    try:
        parsed = [int(item.strip()) for item in str(value).split(",") if item.strip()]
    except ValueError as exc:
        raise forms.ValidationError(_("%(name)s must contain comma-separated integers.") % {"name": name}) from exc
    if minimum is not None and any(item < minimum for item in parsed):
        raise forms.ValidationError(_("%(name)s contains a value below the allowed minimum.") % {"name": name})
    return parsed


def _csv_floats(value: str, *, name: str) -> list[float]:
    try:
        return [float(item.strip()) for item in str(value).split(",") if item.strip()]
    except ValueError as exc:
        raise forms.ValidationError(_("%(name)s must contain comma-separated numbers.") % {"name": name}) from exc


class ResearchFieldStartForm(forms.Form):
    name = forms.CharField(max_length=180, label=_("Analysis name"))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class ResearchFieldConfigurationForm(forms.Form):
    model = forms.ChoiceField(choices=MODEL_CHOICES, label=_("Autonomous field model"))
    initial_mode = forms.ChoiceField(choices=INITIAL_CHOICES, label=_("Initial condition source"))
    initial_velocity_mode = forms.ChoiceField(
        choices=(("ZERO", _("Explicit zero phi_dot")), ("NPZ_ARRAY", _("Pinned NPZ phi_dot array"))),
        initial="ZERO",
        label=_("Initial velocity for second-order models"),
        help_text=_("TDGL does not use phi_dot. For Klein-Gordon models choose the initial velocity explicitly."),
    )

    source = forms.ModelChoiceField(
        queryset=DatasetVersion.objects.none(), required=False, label=_("Pinned NPZ source")
    )
    phi_key = forms.CharField(required=False, label=_("Initial phi array"))
    phi_dot_key = forms.CharField(required=False, label=_("Initial phi_dot array"))
    spatial_axis_keys = forms.CharField(
        required=False,
        label=_("Spatial coordinate array keys"),
        help_text=_("Comma-separated exact axis order, for example x,y."),
    )

    observable_run = forms.ModelChoiceField(
        queryset=AnalysisRun.objects.none(),
        required=False,
        label=_("Completed Observable Field Run"),
    )
    observable_time_index = forms.IntegerField(
        required=False, min_value=0, label=_("Observable bridge time index")
    )

    generated_shape = forms.CharField(
        required=False,
        label=_("Generated grid shape"),
        help_text=_("Comma-separated point counts. Domain wall is 1D."),
    )
    generated_spacings = forms.CharField(required=False, label=_("Generated grid spacings"))
    generated_origins = forms.CharField(required=False, label=_("Generated grid origins"))
    domain_wall_center = forms.FloatField(required=False, initial=0.0, label=_("Domain-wall center"))
    domain_wall_orientation = forms.ChoiceField(
        required=False,
        choices=(("1", "+1"), ("-1", "-1")),
        initial="1",
        label=_("Domain-wall orientation"),
    )
    vortex_winding = forms.IntegerField(required=False, label=_("Vortex winding"))
    radial_profile_key = forms.CharField(required=False, label=_("Supplied radial-profile array"))
    vortex_x_key = forms.CharField(required=False, label=_("Vortex x coordinate array"))
    vortex_y_key = forms.CharField(required=False, label=_("Vortex y coordinate array"))

    lambda_ = forms.FloatField(label=_("lambda model parameter"))
    lambda_origin = forms.CharField(label=_("lambda provenance"))
    mu = forms.FloatField(label=_("mu model parameter"))
    mu_origin = forms.CharField(label=_("mu provenance"))
    gamma = forms.FloatField(required=False, label=_("Gamma model parameter"))
    gamma_origin = forms.CharField(required=False, label=_("Gamma provenance"))
    units_convention = forms.ChoiceField(
        choices=(("dimensionless", _("Dimensionless")), ("natural_units", _("Natural units"))),
        label=_("Units convention"),
    )

    boundary_kind = forms.ChoiceField(choices=BOUNDARY_CHOICES, label=_("Boundary condition"))
    boundary_value_real = forms.FloatField(required=False, initial=0.0, label=_("Boundary value / gradient (real)"))
    boundary_value_imag = forms.FloatField(required=False, initial=0.0, label=_("Boundary value / gradient (imaginary)"))
    dt_solver = forms.FloatField(label=_("Numerical dt_solver"))
    n_steps = forms.IntegerField(min_value=1, label=_("Numerical integration steps"))

    topology_contour_indices = forms.CharField(
        required=False,
        label=_("Ordered topology contour flat indices"),
        help_text=_("Optional comma-separated indices. AgencityLab evaluates phase_winding; Studio does not detect a contour."),
    )
    thermo_t_eff = forms.FloatField(required=False, label=_("Thermodynamic T_eff"))
    thermo_entropy_a = forms.FloatField(required=False, label=_("Field entropy coefficient a"))

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.fields["source"].queryset = (
            DatasetVersion.objects.select_related("dataset")
            .filter(
                dataset__project=project,
                dataset__current_version_id=F("pk"),
                import_status=DatasetImportStatus.READY,
                source_format=FIELD_SOURCE_FORMAT,
            )
            .order_by("dataset__name", "-version_number")
        )
        self.fields["source"].label_from_instance = (
            lambda version: f"{version.dataset.name} · v{version.version_number} · {version.original_filename}"
        )
        self.fields["observable_run"].queryset = (
            AnalysisRun.objects.select_related("analysis")
            .filter(
                analysis__project=project,
                analysis__analysis_kind=AnalysisKind.OBSERVABLE_SPATIAL_FIELD,
                status=RunStatus.COMPLETED,
                result_artifact__isnull=False,
            )
            .order_by("-created_at")
        )
        self.fields["observable_run"].label_from_instance = (
            lambda run: f"{run.analysis.name} · Run {run.run_number} · {run.result_sha256[:12]}"
        )

    def clean(self):
        data = super().clean()
        mode = data.get("initial_mode")
        model = data.get("model")
        velocity_mode = data.get("initial_velocity_mode")
        if data.get("mu") is not None and data["mu"] <= 0.0:
            self.add_error("mu", _("mu must be strictly positive."))
        if data.get("dt_solver") is not None and data["dt_solver"] <= 0.0:
            self.add_error("dt_solver", _("dt_solver must be strictly positive."))
        if model in {MODEL_DISSIPATIVE_KLEIN_GORDON, MODEL_TDGL}:
            if data.get("gamma") is None or data["gamma"] < 0.0:
                self.add_error("gamma", _("This public Lab model requires finite Gamma >= 0."))
            if not str(data.get("gamma_origin") or "").strip():
                self.add_error("gamma_origin", _("Gamma provenance is required."))

        if mode == INITIAL_NPZ:
            for name in ("source", "phi_key", "spatial_axis_keys"):
                if not data.get(name):
                    self.add_error(name, _("This field is required for a pinned NPZ initial condition."))
        elif mode == INITIAL_OBSERVABLE_BRIDGE:
            if not data.get("observable_run"):
                self.add_error("observable_run", _("Select a completed Observable Field Run."))
            if data.get("observable_time_index") is None:
                self.add_error("observable_time_index", _("Select the exact source time index."))
        elif mode == INITIAL_DOMAIN_WALL:
            for name in ("generated_shape", "generated_spacings", "generated_origins"):
                if not str(data.get(name) or "").strip():
                    self.add_error(name, _("The generated Lab grid must be explicit."))
        elif mode == INITIAL_VORTEX_PROFILE:
            for name in ("source", "radial_profile_key", "vortex_x_key", "vortex_y_key"):
                if not data.get(name):
                    self.add_error(name, _("This field is required for the Lab vortex constructor."))
            if data.get("vortex_winding") is None:
                self.add_error("vortex_winding", _("Vortex winding is required."))

        if model != MODEL_TDGL:
            if velocity_mode == "NPZ_ARRAY":
                if mode not in {INITIAL_NPZ, INITIAL_VORTEX_PROFILE}:
                    self.add_error(
                        "initial_velocity_mode",
                        _("Pinned NPZ phi_dot is available only when the initial source is an NPZ artifact."),
                    )
                if not str(data.get("phi_dot_key") or "").strip():
                    self.add_error("phi_dot_key", _("Select the exact phi_dot array for NPZ velocity mode."))
            elif velocity_mode != "ZERO":
                self.add_error("initial_velocity_mode", _("Choose an explicit initial velocity mode."))
        elif data.get("phi_dot_key"):
            self.add_error("phi_dot_key", _("TDGL does not consume phi_dot."))

        try:
            if str(data.get("spatial_axis_keys") or "").strip():
                data["spatial_axis_keys_parsed"] = [
                    item.strip() for item in data["spatial_axis_keys"].split(",") if item.strip()
                ]
            if str(data.get("generated_shape") or "").strip():
                data["generated_shape_parsed"] = _csv_ints(
                    data["generated_shape"], name="Generated grid shape", minimum=2
                )
                data["generated_spacings_parsed"] = _csv_floats(
                    data.get("generated_spacings", ""), name="Generated grid spacings"
                )
                data["generated_origins_parsed"] = _csv_floats(
                    data.get("generated_origins", ""), name="Generated grid origins"
                )
                lengths = {
                    len(data["generated_shape_parsed"]),
                    len(data["generated_spacings_parsed"]),
                    len(data["generated_origins_parsed"]),
                }
                if len(lengths) != 1:
                    raise forms.ValidationError(
                        _("Generated shape, spacings and origins must have the same rank.")
                    )
                if any(value <= 0.0 for value in data["generated_spacings_parsed"]):
                    raise forms.ValidationError(_("Generated grid spacings must be strictly positive."))
            if str(data.get("topology_contour_indices") or "").strip():
                parsed = _csv_ints(
                    data["topology_contour_indices"], name="Topology contour", minimum=0
                )
                if len(parsed) < 3:
                    raise forms.ValidationError(_("Topology contour requires at least three ordered indices."))
                data["topology_contour_indices_parsed"] = parsed
        except forms.ValidationError as exc:
            self.add_error(None, exc)

        if mode == INITIAL_DOMAIN_WALL and data.get("generated_shape_parsed"):
            if len(data["generated_shape_parsed"]) != 1:
                self.add_error("generated_shape", _("The public domain-wall reference is one-dimensional."))
        if data.get("thermo_t_eff") is not None and data["thermo_t_eff"] <= 0.0:
            self.add_error("thermo_t_eff", _("T_eff must be strictly positive."))
        if data.get("boundary_kind") == BOUNDARY_PERIODIC:
            data["boundary_value_real"] = 0.0
            data["boundary_value_imag"] = 0.0
        return data
