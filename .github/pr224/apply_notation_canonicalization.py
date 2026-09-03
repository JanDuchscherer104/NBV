#!/usr/bin/env python3
"""Apply the PR #224 semantic notation migration to a clean current-main tree."""

from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
SYMBOL_DIR = ROOT / "docs/typst/shared/symbols"
SYMBOL_ROOT = ROOT / "docs/typst/shared/symbols.typ"
GLOSSARY = ROOT / "docs/typst/shared/glossary.typ"
EQUATION_ROOT = ROOT / "docs/typst/shared/equations.typ"

TEXT_SUFFIXES = {
    ".typ", ".py", ".yml", ".yaml", ".json", ".jsonl", ".lua", ".qmd",
    ".md", ".toml", ".txt", ".sh", ".ini", ".cfg",
}
SKIP_PARTS = {".git", ".venv", "node_modules", "target", "__pycache__"}
GENERATED_PATHS = {
    "docs/notation.yml",
    "docs/_extensions/aria-glossary/notation.generated.lua",
    "docs/typst/shared/notation.generated.typ",
    "docs/_generated/context/glossary.jsonl",
    "docs/contents/glossary.qmd",
    "docs/glossary/terms.yml",
    "docs/typst/shared/glossary.generated.typ",
}


@dataclass(frozen=True)
class Entry:
    expr: str
    comment: str


@dataclass
class Record:
    key: str
    tex: str
    description: str
    thesis_list: bool
    order: int


MODULE_ORDER = [
    "frame", "trajectory", "ase", "entity", "spatial", "obs", "scene",
    "metric", "rl", "model", "oracle", "vin", "shape",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def iter_text_files() -> list[Path]:
    result: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        result.append(path)
    return result


def parse_module(path: Path) -> dict[str, Entry]:
    entries: dict[str, Entry] = {}
    comments: list[str] = []
    if not path.exists():
        return entries
    for line in read(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            comments.append(stripped[2:].strip())
            continue
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*):\s*(\$.*\$),\s*$", line)
        if match:
            entries[match.group(1)] = Entry(
                expr=match.group(2),
                comment=" ".join(comments[-3:]).strip(),
            )
        comments = []
    return entries


def find_matching_paren(text: str, opening: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    raise RuntimeError("unterminated notation tuple")


RECORD_PATTERN = re.compile(
    r'^\s*\(key:\s*"(?P<key>[^"]+)",\s*'
    r'tex:\s*"(?P<tex>(?:\\.|[^"])*)",\s*'
    r'description:\s*"(?P<description>(?:\\.|[^"])*)",\s*'
    r'thesis_list:\s*(?P<thesis>true|false),\s*'
    r'order:\s*(?P<order>\d+)\),\s*$',
    re.MULTILINE,
)


def parse_registry(text: str, marker: str) -> tuple[list[Record], str, str]:
    start = text.index(marker)
    opening = text.index("(", start)
    closing = find_matching_paren(text, opening)
    records: list[Record] = []
    for match in RECORD_PATTERN.finditer(text[opening + 1 : closing]):
        records.append(
            Record(
                key=match.group("key"),
                tex=json.loads('"' + match.group("tex") + '"'),
                description=json.loads('"' + match.group("description") + '"'),
                thesis_list=match.group("thesis") == "true",
                order=int(match.group("order")),
            )
        )
    return records, text[:start], text[closing + 1 :]


OLD_MODULES = {
    module: parse_module(SYMBOL_DIR / f"{module}.typ")
    for module in ("frame", "ase", "entity", "spatial", "obs", "scene", "rl", "model", "oracle", "vin", "shape")
}
OLD_RECORDS, _, ROOT_SUFFIX = parse_registry(
    read(SYMBOL_ROOT), "#let aria-notation-symbols ="
)
if len(OLD_RECORDS) < 40:
    raise RuntimeError(f"parsed only {len(OLD_RECORDS)} existing symbol records")

# Symbol-key migration. Equation identifiers are deliberately not renamed by
# this table: only `symb.*` references and symbol-ref registries are migrated.
KEY_MAP: dict[str, str] = {
    "ase.mesh_target": "oracle.target_mesh",
    "ase.mesh": "ase.scene_mesh",
    "ase.faces": "ase.scene_faces",
    "ase.traj_final": "spatial.factual_rig_pose_end",
    "ase.traj": "spatial.factual_rig_pose",
    "ase.points_semi": "obs.sem_dense_points",
    "entity.E": "entity.set",
    "entity.B_pred": "entity.obb_pred",
    "entity.B_gt": "entity.obb_gt",
    "entity.w": "metric.entity_weights",
    "entity.lambda_scene": "metric.scene_weight",
    "entity.rri_total": "metric.combined_rri",
    "entity.rri_e": "metric.target_rri_label",
    "entity.target_hyp_pred_t": "entity.hypotheses",
    "entity.target_desc": "entity.descriptor",
    "entity.center": "entity.center_world",
    "entity.target_error_pm": "metric.target_error_point_to_mesh",
    "entity.target_error_mp": "metric.target_error_mesh_to_point",
    "entity.target_error_next": "metric.target_error_next",
    "entity.target_error_0": "metric.target_error_root",
    "entity.target_error_H": "metric.target_error_endpoint",
    "entity.target_error": "metric.target_error",
    "entity.target_rri_marginal": "metric.target_rri",
    "entity.target_rri_cumulative": "metric.cumulative_rri",
    "entity.target_root_gain_cumulative": "metric.cumulative_gain",
    "entity.endpoint_gain": "metric.endpoint_gain",
    "entity.log_gain": "metric.log_gain",
    "entity.lookahead_headroom": "metric.lookahead_headroom",
    "entity.q_recovery": "metric.q_recovery",
    "entity.target_reward": "rl.target_reward",
    "entity.return_h": "rl.return",
    "obs.img_rgb": "obs.rgb",
    "obs.img_gray": "obs.grayscale",
    "obs.pose": "spatial.factual_camera_pose",
    "obs.meta": "obs.metadata",
    "obs.points_semi_t": "obs.sem_dense_points",
    "obs.points_semi": "obs.sem_dense_points",
    "obs.points_t": "obs.accumulated_points",
    "obs.points_next": "obs.accumulated_points_next",
    "obs.points_cand_ti": "oracle.candidate_points",
    "obs.selected_rays_ti": "obs.selected_rays",
    "obs.points_tensor_t": "model.point_tensor",
    "obs.points_tensor_cand_ti": "model.candidate_point_tensor",
    "obs.dino_point_bank_t": "obs.dino_point_bank",
    "obs.point_tokens_t": "model.point_tokens",
    "obs.points_cf": "obs.counterfactual_points",
    "obs.vis": "obs.visibility",
    "obs.lookat": "vin.lookat",
    "obs.face_vis_step": "vin.face_visibility_step",
    "obs.face_vis": "vin.face_visibility",
    "obs.voxel_center": "spatial.voxel_center",
    "obs.face_normal": "obs.normal",
    "oracle.points_t": "obs.accumulated_points",
    "oracle.points_tensor": "model.point_tensor",
    "oracle.points_q": "oracle.candidate_points",
    "oracle.points": "obs.accumulated_points",
    "oracle.candidate_tensor": "model.candidate_rows",
    "oracle.candidates_t": "rl.candidate_table",
    "oracle.candidate_qti": "rl.candidate",
    "oracle.candidates": "rl.candidate_table",
    "oracle.depth_q": "oracle.candidate_depth",
    "oracle.mask_q": "oracle.candidate_projection_mask",
    "oracle.cameras_q": "spatial.candidate_camera_pose",
    "oracle.center": "spatial.camera_center_world",
    "oracle.offset": "spatial.sampling_offset",
    "oracle.dist_pm": "metric.point_to_mesh",
    "oracle.acc": "metric.point_to_mesh",
    "oracle.dist_mp": "metric.mesh_to_point",
    "oracle.comp": "metric.mesh_to_point",
    "oracle.err": "metric.point_mesh_error",
    "oracle.rri": "metric.rri",
    "scene.scene_memory_t": "scene.memory",
    "scene.ray_memory_t": "scene.ray_memory",
    "scene.evl_local": "scene.root_evl_field",
    "scene.evl_support_frac": "scene.evl_support_fraction",
    "scene.evl_support_token": "model.evl_support_token",
    "scene.target_support_pool": "model.target_support_token",
    "scene.frustum_support_pool": "model.candidate_support_token",
    "scene.target_frustum_pool": "model.target_candidate_support_token",
    "scene.ray_query_ti": "model.ray_query_token",
    "spatial.ref_candidate_transform": "spatial.candidate_relative_transform",
    "spatial.ref_pose": "spatial.factual_camera_pose",
    "spatial.pose_6d": "spatial.rotation_6d",
    "spatial.candidate_pose_feat": "model.candidate_pose_token",
    "spatial.candidate_target_rel_feat": "model.target_candidate_token",
    "spatial.relation_rpe": "model.relative_position_embedding",
    "spatial.target_bearing": "spatial.target_alignment",
    "spatial.dir_unit": "spatial.unit_direction",
    "spatial.target_obb_scale": "entity.obb_scale",
    "spatial.dir_memory": "model.directional_token",
    "spatial.dir_moment": "spatial.directional_moment",
    "spatial.sh_basis": "spatial.spherical_harmonics",
    "spatial.candidate_camera_frame": "spatial.candidate_camera_pose",
    "spatial.trajectory_camera_frame": "spatial.factual_camera_pose",
    "rl.rollout_index": "trajectory.rollout_index",
    "rl.s_hist": "rl.factual_state",
    "rl.s_off": "trajectory.replay_record",
    "rl.s_obs": "rl.factual_state",
    "rl.s_cf0_next": "rl.counterfactual_state_next",
    "rl.s_cf0": "rl.counterfactual_state",
    "rl.s_pose": "model.pose_history_state",
    "rl.s_surface": "model.selected_surface_state",
    "rl.s_ray": "model.ray_aware_state",
    "rl.s_cf_geom": "model.selected_observation_state",
    "rl.s_cf_gt_carrier": "model.privileged_selected_depth_state",
    "rl.s_oracle": "oracle.information",
    "rl.state_emb": "model.state_token",
    "rl.reward_target": "rl.target_reward",
    "rl.return_h": "rl.return",
    "rl.qh_target": "rl.q_target",
    "rl.qh_theta": "rl.q",
    "rl.conditional_q": "rl.candidate_value",
    "rl.qh": "rl.q",
    "rl.validity_mask": "rl.admission_mask",
    "rl.action_mask": "rl.admission_mask",
    "rl.candidate_row_mask": "rl.row_mask",
    "rl.q_label_mask": "rl.value_target_mask",
    "rl.feasibility_label_mask": "rl.feasibility_target_mask",
    "rl.feasibility_logits": "model.feasibility_logit",
    "rl.coral_q_edge": "model.coral_q_edge",
    "rl.coral_q_value": "model.coral_q_value",
    "rl.coral_q_label": "model.coral_q_label",
    "rl.candidate_token": "model.candidate_token",
    "rl.candidate_qti": "rl.candidate",
    "rl.candidate_features": "model.candidate_rows",
    "rl.candidate_mask": "rl.admission_mask_vector",
    "rl.invalid_reasons": "rl.invalid_reason_vector",
    "rl.q_weight": "model.q_weight",
    "rl.target": "entity.target",
    "rl.selected_action_theta": "rl.selected_action",
    "rl.exact_q2_target": "rl.q2_diagnostic_target",
    "rl.q2_recursion_error": "rl.q2_diagnostic_error",
    "rl.q_loss": "model.q_loss",
    "rl.H_max": "rl.max_horizon",
    "rl.H": "rl.endpoint_horizon",
    "rl.gamma": "rl.discount",
    "rl.pi": "rl.policy_generic",
    "rl.Q": "rl.q_generic",
    "rl.V": "rl.state_value",
    "rl.A": "rl.advantage",
    "rl.G": "rl.return_generic",
    "rl.r": "rl.reward_generic",
    "rl.a": "rl.action",
    "rl.s": "rl.state",
    "rl.o": "obs.factual",
    "model.history_pose_feature": "model.history_pose_token",
    "model.candidate_validity_token": "model.candidate_admission_token",
    "model.candidate_provenance_token": "model.candidate_source_token",
    "model.candidate_physical_token": "model.candidate_geometry_token",
    "shape.Nq": "shape.candidate_count",
    "shape.B": "shape.batch_count",
    "shape.N": "shape.sample_count",
    "shape.Tlen": "shape.trajectory_length",
    "shape.Pmax": "shape.point_capacity",
    "shape.Pproj": "shape.projected_point_count",
    "shape.Pfr": "shape.frustum_point_count",
    "shape.P": "shape.point_count",
    "shape.Himg": "shape.image_height",
    "shape.Wimg": "shape.image_width",
    "shape.H": "shape.image_height",
    "shape.Wdim": "shape.image_width",
    "shape.Vvox": "shape.voxel_count",
    "shape.M": "shape.mesh_vertex_count",
    "shape.K": "shape.ordinal_bin_count",
    "shape.D": "shape.feature_dim",
    "shape.Csem": "shape.sem_dense_dim",
    "shape.Fin": "shape.input_dim",
    "shape.Ffield": "shape.scene_dim",
    "shape.Fpose": "shape.pose_dim",
    "shape.Fpe": "shape.position_dim",
    "shape.Fq": "shape.candidate_dim",
    "shape.Fg": "shape.global_dim",
    "shape.Ftau": "shape.trajectory_dim",
    "shape.Fproj": "shape.projection_dim",
    "shape.Fcnn": "shape.cnn_dim",
    "shape.Ftok": "shape.token_dim",
    "shape.Ffr": "shape.frustum_dim",
    "shape.Fpt": "shape.point_dim",
    "shape.Faux": "shape.auxiliary_dim",
    "shape.Fhead": "shape.head_dim",
    "shape.Fhid": "shape.hidden_dim",
    "shape.Gpool": "shape.pool_dim",
    "shape.Gproj": "shape.projection_dim",
    "shape.Gsem": "shape.sem_dense_grid_count",
    "vin.pose_emb": "vin.pose_embedding",
    "vin.token": "model.candidate_token",
    "vin.vox_tok": "vin.voxel_token",
    "vin.pos": "vin.position_embedding",
    "vin.global": "vin.global_context",
    "vin.query": "vin.attention_query",
    "vin.key": "vin.attention_key",
    "vin.value": "vin.attention_value",
    "vin.T": "spatial.transform",
    "vin.W": "vin.weight",
    "vin.gamma": "vin.film_scale",
    "vin.beta": "vin.film_shift",
    "vin.rri_hat": "vin.rri_prediction",
    "vin.rri": "vin.rri_target",
    "vin.cand_valid": "rl.admission_mask",
    "vin.scene_memory_t": "scene.memory",
    "vin.evl_local": "scene.root_evl_field",
    "vin.evl_support_frac": "scene.evl_support_fraction",
    "vin.evl_support_token": "model.evl_support_token",
    "vin.target_pool": "model.target_support_token",
    "vin.frustum_pool": "model.candidate_support_token",
    "vin.target_frustum_pool": "model.target_candidate_support_token",
    "vin.ray_query_ti": "model.ray_query_token",
    "vin.render_query": "scene.render_query",
    "vin.pose_6d": "spatial.rotation_6d",
    "vin.dir_unit": "spatial.unit_direction",
    "vin.dir_memory": "model.directional_token",
    "vin.dir_moment": "spatial.directional_moment",
    "vin.sh_basis": "spatial.spherical_harmonics",
    "vin.candidate_pose_feat": "model.candidate_pose_token",
}


def replace_symbol_refs(text: str) -> str:
    for old, new in sorted(KEY_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace("symb." + old, "symb." + new)
    return text


def replace_symbol_ref_blocks(text: str) -> str:
    # Only mutate symbol_refs tuples; equation_refs retain their own stable IDs.
    pattern = re.compile(r"(symbol_refs:\s*\()(.*?)(\n\s*\),)", re.DOTALL)

    def repl(match: re.Match[str]) -> str:
        body = match.group(2)
        for old, new in sorted(KEY_MAP.items(), key=lambda item: len(item[0]), reverse=True):
            body = body.replace('"' + old + '"', '"' + new + '"')
        return match.group(1) + body + match.group(3)

    text = pattern.sub(repl, text)
    return replace_symbol_refs(text)


# Migrate authored symbol references. Generated projections are rebuilt later.
for path in iter_text_files():
    rel = relative(path)
    if path == SYMBOL_ROOT or path.parent == SYMBOL_DIR or rel in GENERATED_PATHS:
        continue
    text = read(path)
    original = text
    if path == GLOSSARY:
        text = replace_symbol_ref_blocks(text)
    elif path.suffix == ".typ":
        text = replace_symbol_refs(text)
    else:
        # Runtime/reporting consumers store canonical symbol IDs as strings.
        for old, new in sorted(KEY_MAP.items(), key=lambda item: len(item[0]), reverse=True):
            text = text.replace(old, new)
    if path.suffix == ".typ" and "docs/typst/thesis" in rel:
        text = text.replace("S0-pose", "pose-history representation")
        text = text.replace("S1-surface", "selected-surface representation")
        text = text.replace("S2-ray", "ray-aware representation")
        text = text.replace("CF-GT-carrier", "privileged selected-depth carrier")
    if text != original:
        write(path, text)

# Canonicalize existing arrow/pair transform syntax. T_(to <- from) becomes
# bold(T)_from^to. The state transition is separately cal(T).
arrow_transform = re.compile(
    r"(?P<head>bold\(T\)|(?<![A-Za-z_])T)_\((?P<to>[^()\n,]+?)\s+arrow\.l\s+(?P<frm>[^()\n,]+?)\)"
)
pair_transform = re.compile(
    r"bold\(T\)_\((?P<to>[^(),\n]+?),\s*(?P<frm>[^(),\n]+?)\)(?![\^_])"
)
for path in iter_text_files():
    if path.suffix != ".typ" or path.parent == SYMBOL_DIR:
        continue
    text = read(path)
    original = text
    text = arrow_transform.sub(
        lambda match: f"bold(T)_({match.group('frm').strip()})^({match.group('to').strip()})",
        text,
    )
    text = pair_transform.sub(
        lambda match: f"bold(T)_({match.group('frm').strip()})^({match.group('to').strip()})",
        text,
    )
    text = text.replace('bold(T)_"root<-cam"', 'bold(T)_c^r')
    text = text.replace('T_"root<-cam"', 'bold(T)_c^r')
    if text != original:
        write(path, text)

# ---------------------------------------------------------------------------
# Canonical module values.
# ---------------------------------------------------------------------------
CURATED: dict[str, OrderedDict[str, Entry]] = {
    module: OrderedDict() for module in MODULE_ORDER
}


def add(module: str, key: str, expr: str, comment: str) -> None:
    CURATED[module][key] = Entry(expr, comment)


for key, expr, comment in (
    ("w", "$w$", "World frame label; use only in geometric indices."),
    ("r", "$r$", "Rig frame label; use only in geometric indices."),
    ("c", "$c$", "Camera frame family; use only in geometric indices."),
    ("o", "$o$", "Object frame family; use only in geometric indices."),
    ("v", "$v$", "Voxel frame label; use only in geometric indices."),
    ("s", "$s$", "Sampling frame label; use only in geometric indices."),
): add("frame", key, expr, comment)

for key, expr, comment in (
    ("factual", "$tau$", "Factual recorded trajectory; factuality is the unmarked default."),
    ("counterfactual", "$tau_n^\"cf\"$", "Counterfactual rollout trajectory n."),
    ("composite", "$bar(tau)_n$", "Factual prefix followed by counterfactual rollout n."),
    ("rollout_index", "$n$", "Counterfactual rollout identity."),
    ("step", "$t$", "Decision-step index shared by factual and counterfactual trajectories."),
    ("history_step", "$j$", "Earlier realised decision step, j<t."),
    ("root_step", "$t_0$", "Factual root from which a counterfactual rollout branches."),
    ("replay_record", "$d_t^\"replay\"$", "Persisted replay record; not a decision state."),
): add("trajectory", key, expr, comment)

add("ase", "scene_mesh", "$cal(M)^\"GT\"$", "Ground-truth ASE scene mesh.")
add("ase", "scene_faces", "$cal(F)^\"GT\"$", "Ground-truth ASE scene-mesh faces.")

for key, expr, comment in (
    ("set", "$cal(E)$", "Universe of target entities."),
    ("targets_at_root", "$cal(E)(s_(t_0))$", "Targets admitted for the task root."),
    ("target", "$e$", "Fixed target entity for one target-conditioned task."),
    ("obb_pred", "$hat(bold(B))_e$", "Actor-visible predicted target OBB."),
    ("obb_gt", "$bold(B)_e^\"GT\"$", "Privileged ground-truth target OBB."),
    ("target_frame", "$o_e$", "Target-local object frame."),
    ("center_world", "$bold(p)_e^w$", "Target centre in world coordinates."),
    ("extent", "$bold(a)_e$", "Metric target extent vector."),
    ("descriptor", "$bold(phi)_e$", "Actor-visible target descriptor."),
    ("hypotheses", "$cal(O)_t^\"pred\"$", "Actor-visible target hypotheses at state t."),
    ("obb_scale", "$r_e$", "Geometric-mean target proxy scale."),
): add("entity", key, expr, comment)

for key, expr, comment in (
    ("transform", "$bold(T)_a^b$", "Rigid transform from source frame a to destination frame b."),
    ("factual_rig_pose", "$bold(T)_r^w(t)$", "Factual world-from-rig pose."),
    ("factual_rig_pose_end", "$bold(T)_r^w(t_\"end\")$", "Factual terminal world-from-rig pose."),
    ("factual_camera_pose", "$bold(T)_c^w(t)$", "Factual world-from-camera pose."),
    ("counterfactual_camera_pose", "$bold(T)_(c_n^\"cf\")^w(t)$", "Realised world-from-camera pose on counterfactual rollout n."),
    ("candidate_camera_pose", "$bold(T)_(tilde(c)_i)^w(t)$", "Prospective endpoint pose carried by candidate i."),
    ("counterfactual_candidate_camera_pose", "$bold(T)_(tilde(c)_(n,i)^\"cf\")^w(t)$", "Prospective candidate endpoint on counterfactual rollout n."),
    ("target_pose", "$bold(T)_(o_e)^w$", "World-from-target-object pose."),
    ("candidate_relative_transform", "$bold(T)_(tilde(c)_i)^c(t)$", "Candidate camera expressed relative to the current camera."),
    ("camera_center_world", "$bold(p)_c^w(t)$", "Camera centre in world coordinates."),
    ("sampling_offset", "$bold(o)$", "Candidate-sampling offset vector."),
    ("voxel_center", "$bold(p)_v$", "Voxel-centre point in the voxel frame."),
    ("rotation_6d", "$bold(R)^\"6D\"$", "Continuous six-dimensional rotation representation."),
    ("unit_direction", "$hat(bold(d))$", "Unit direction vector."),
    ("local_delta_pos", "$bold(delta)_(a|i)^p$", "Candidate-local relative displacement."),
    ("local_delta_rot", "$bold(delta)_(a|i)^R$", "Candidate-local relative rotation descriptor."),
    ("target_alignment", "$cos theta_(t,e,i)^\"opt\"$", "Optical-axis alignment with the target direction."),
    ("target_frame_motion_direction", "$hat(bold(delta))_(n,t)^e$", "Selected-camera displacement direction in target coordinates."),
    ("target_frame_view_direction", "$hat(bold(v))_(n,t)^e$", "Selected-camera optical direction in target coordinates."),
    ("target_frame_frustum", "$cal(F)_(n,t)^e$", "Target-proxy footprint of one selected frustum."),
    ("target_frame_frustum_fraction", "$kappa_(n,t)^e$", "Fraction of target proxy supported by one selected frustum."),
    ("frustum_solid_angle", "$Omega_(n,t)^\"FOV\"$", "Calibrated camera field-of-view solid angle."),
    ("directional_moment", "$bold(M)^\"dir\"$", "Second directional moment."),
    ("spherical_harmonics", "$bold(Y)_L$", "Spherical-harmonic basis through degree L."),
): add("spatial", key, expr, comment)

for key, expr, comment in (
    ("factual", "$o_t$", "Observation acquired on the factual trajectory."),
    ("counterfactual", "$o_(n,t)^\"cf\"$", "Observation realised on counterfactual rollout n."),
    ("rgb", "$bold(I)_t^\"rgb\"$", "RGB observation."),
    ("grayscale", "$bold(I)_t^\"gray\"$", "Grayscale observation."),
    ("depth", "$bold(D)_t$", "Actor-acquired depth observation."),
    ("metadata", "$cal(C)_t^\"meta\"$", "Camera and observation metadata."),
    ("sem_dense_points", "$cal(P)_t^\"semi\"$", "Time-indexed semi-dense observed points."),
    ("accumulated_points", "$cal(P)_t$", "Actor-visible accumulated point set."),
    ("accumulated_points_next", "$cal(P)_(t+1)$", "Accumulated point set after selection."),
    ("counterfactual_points", "$cal(P)_(n,t)^\"cf\"$", "Geometry realised along a counterfactual rollout."),
    ("selected_rays", "$cal(R)_(n,t)^\"sel\"$", "Rays acquired from a selected observation."),
    ("dino_point_bank", "$bold(F)_t^\"DINO@pt\"$", "Logged point-attached DINO descriptors."),
    ("normal", "$bold(n)_u$", "Physical normal for point or sample u."),
    ("visibility", "$bold(V)_t$", "Observed visibility cue."),
): add("obs", key, expr, comment)

for key, expr, comment in (
    ("memory", "$bold(Phi)_t$", "Actor-visible scene memory."),
    ("ray_memory", "$bold(M)_t^\"ray\"$", "Actor-visible ray-aware memory."),
    ("ray_memory_next", "$bold(M)_(t+1)^\"ray\"$", "Ray-aware memory after selection."),
    ("root_evl_field", "$bold(E)_(t_0)^\"EVL\"$", "Root-local EVL evidence field."),
    ("evl_support_fraction", "$omega_(t,i)^\"EVL\"$", "Fraction of a query supported by the EVL field."),
    ("render_query", "$op(\"RenderQuery\")$", "Actor-visible scene-memory query operator."),
): add("scene", key, expr, comment)

for key, expr, comment in (
    ("point_mesh_error", "$D$", "Aggregate point-mesh reconstruction error."),
    ("point_to_mesh", "$D_(P -> M)$", "Point-to-mesh directional error."),
    ("mesh_to_point", "$D_(M -> P)$", "Mesh-to-point directional error."),
    ("target_error", "$Delta_t^e$", "Target reconstruction error at state t."),
    ("target_error_next", "$Delta_(t+1)^e$", "Target error after one selected transition."),
    ("target_error_root", "$Delta_0^e$", "Target error at the rollout root."),
    ("target_error_endpoint", "$Delta_H^e$", "Target error at endpoint horizon H."),
    ("target_error_point_to_mesh", "$D_(P -> M,t)^e$", "Target point-to-mesh error at state t."),
    ("target_error_mesh_to_point", "$D_(M -> P,t)^e$", "Target mesh-to-point error at state t."),
    ("candidate_target_error", "$Delta_(t|i)^e$", "Target error after prospective candidate i."),
    ("rri", "$op(\"RRI\")$", "Relative Reconstruction Improvement functional."),
    ("target_rri_label", "$op(\"RRI\")_e$", "Target-specific RRI label family."),
    ("target_rri", "$op(\"RRI\")_(t,i)^e$", "State-relative target-specific one-step RRI."),
    ("candidate_gain", "$g_(t,i)^e$", "Candidate gain normalized by rollout-root target error."),
    ("cumulative_rri", "$C_t^(\"RRI\",e)$", "Running sum of selected one-step RRIs."),
    ("cumulative_gain", "$J_t^e$", "Running root-normalized selected gain."),
    ("endpoint_gain", "$J_e^((H))$", "Fixed-budget endpoint gain."),
    ("log_gain", "$J_(e,\"log\")^((H))$", "Log-scale endpoint gain."),
    ("lookahead_headroom", "$Delta J_e^\"look\"$", "Endpoint headroom of bounded lookahead."),
    ("q_recovery", "$eta_Q$", "Fraction of the learned-myopic-to-lookahead gap recovered."),
    ("entity_weights", "$bold(w)$", "Target weighting vector."),
    ("scene_weight", "$lambda_\"scene\"$", "Scene-objective mixing weight."),
    ("combined_rri", "$op(\"RRI\")_\"total\"$", "Combined scene/target RRI objective."),
): add("metric", key, expr, comment)

for key, expr, comment in (
    ("state", "$s$", "Generic decision state."),
    ("factual_state", "$s_t$", "State induced by the factual trajectory."),
    ("counterfactual_state", "$s_(n,t)^\"cf\"$", "State on realised counterfactual rollout n."),
    ("counterfactual_state_next", "$s_(n,t+1)^\"cf\"$", "Counterfactual successor state."),
    ("action", "$a$", "Generic action."),
    ("selected_action", "$a_t$", "Selected candidate-row index."),
    ("policy", "$pi_theta$", "Target-conditioned learned policy."),
    ("policy_generic", "$pi$", "Generic policy."),
    ("transition", "$cal(T)$", "Selected-action state-transition operator."),
    ("mdp_nbv", "$cal(M)_\"NBV\"$", "Target-conditioned finite-candidate NBV process."),
    ("candidate_table", "$cal(Q)_t$", "Finite permutation-insensitive candidate-action family."),
    ("candidate", "$q_(t,i)$", "Candidate/action record carrying a prospective endpoint."),
    ("action_set", "$cal(A)(s_t)$", "Admitted candidate-row indices."),
    ("row_mask", "$m_(t,i)^\"row\"$", "Materialised row versus padding."),
    ("admission_mask", "$m_(t,i)^\"adm\"$", "Admission under the frozen action-support protocol."),
    ("admission_mask_vector", "$bold(m)_t^\"adm\"$", "Vector of admission indicators."),
    ("value_target_mask", "$m_(t,i)^(Q,h)$", "Availability of a finite value target."),
    ("feasibility_target_mask", "$m_(t,i)^\"feas\"$", "Availability of trusted feasibility supervision."),
    ("successor_mask", "$m_t^\"succ\"$", "Availability of the factual successor needed for backup."),
    ("source_role", "$zeta_(t,i)^\"src\"$", "Categorical evidence provenance role."),
    ("invalid_reason", "$rho_(t,i)$", "Categorical reason for non-admission."),
    ("invalid_reason_vector", "$bold(rho)_t$", "Vector of non-admission reasons."),
    ("reward_generic", "$r$", "Generic immediate reward."),
    ("target_reward", "$r_t^e$", "Selected target-specific immediate reward."),
    ("return_generic", "$G$", "Generic cumulative return."),
    ("return", "$G_(t,e)^((h))$", "Target-conditioned residual-horizon return."),
    ("q_generic", "$Q$", "Generic state-action value function."),
    ("q", "$Q_theta$", "Shared horizon-conditioned candidate-value function."),
    ("candidate_value", "$Q_theta(s_t,e,i,h)$", "Value emitted for candidate i."),
    ("q_target", "$Q_(bar(theta))$", "Delayed target-network value function."),
    ("state_value", "$V$", "Generic state-value function."),
    ("advantage", "$A$", "Generic advantage function."),
    ("discount", "$gamma$", "Temporal discount factor."),
    ("requested_horizon", "$h$", "Requested residual return horizon."),
    ("endpoint_horizon", "$H$", "Fixed endpoint or evaluation horizon."),
    ("max_horizon", "$H_\"max\"$", "Maximum supported requested horizon."),
    ("budget", "$b_t$", "Remaining acquisition budget."),
    ("acquisition_cost", "$C(tau)$", "Acquisition cost of a trajectory."),
    ("q2_diagnostic_target", "$y_(t,e)^((2,\"diag\"))$", "Two-step Bellman and successor-linkage diagnostic."),
    ("q2_diagnostic_error", "$epsilon_(t,e)^((2,\"diag\"))$", "Recursive-target error against the two-step diagnostic."),
): add("rl", key, expr, comment)

for key, expr, comment in (
    ("target_token", "$bold(z)_e$", "Learned target token; e already identifies its role."),
    ("candidate_row", "$bold(x)_(t,i)$", "Typed pre-encoding candidate row."),
    ("candidate_rows", "$bold(X)_t^\"cand\"$", "Tensor of typed candidate rows."),
    ("candidate_token", "$bold(z)_(t,i)$", "Learned candidate token."),
    ("candidate_geometry_token", "$bold(z)_(t,i)^\"geom\"$", "Candidate geometry/support token."),
    ("candidate_admission_token", "$bold(z)_(t,i)^\"adm\"$", "Candidate admission/reason token."),
    ("candidate_source_token", "$bold(z)_(t,i)^\"src\"$", "Candidate provenance token."),
    ("candidate_pose_token", "$bold(z)_(t,i)^\"pose-rel\"$", "Encoded relative candidate-pose token."),
    ("target_candidate_token", "$bold(z)_(t,e,i)^\"rel\"$", "Encoded target-candidate relation token."),
    ("relative_position_embedding", "$bold(z)_(a|i)^\"rpe\"$", "Relative-position embedding."),
    ("history_pose_token", "$bold(z)_(t,j)^\"hist\"$", "Earlier realised pose encoded relative to current state."),
    ("history_relative_age", "$a_(t,j)^\"hist\"$", "Normalized age of earlier realised step j."),
    ("history_token", "$bold(z)_t^\"hist\"$", "Aggregated causal history token."),
    ("state_token", "$bold(z)_t^\"state\"$", "Learned state token."),
    ("point_tokens", "$bold(Z)_t^\"pt\"$", "Learned point-token set."),
    ("point_tensor", "$bold(P)_t$", "Tensorized accumulated points."),
    ("candidate_point_tensor", "$bold(P)_(t,i)^\"cand\"$", "Tensorized candidate point contribution."),
    ("evl_support_token", "$bold(z)_(t,i)^\"EVL\"$", "Learned EVL support token."),
    ("target_support_token", "$bold(z)_e^\"support\"$", "Learned target-support token."),
    ("candidate_support_token", "$bold(z)_(t,i)^\"support\"$", "Learned candidate-support token."),
    ("target_candidate_support_token", "$bold(z)_(t,e,i)^\"support\"$", "Learned intersection-support token."),
    ("ray_query_token", "$bold(z)_(t,i)^\"ray\"$", "Learned ray-query token."),
    ("directional_token", "$bold(z)^\"dir\"$", "Learned directional-history token."),
    ("feasibility_logit", "$ell_(t,i)^\"feas\"$", "Auxiliary feasibility logit."),
    ("pose_history_representation", "$Psi^\"pose\"$", "Pose-history state-representation map."),
    ("selected_surface_representation", "$Psi^\"surface\"$", "Selected-surface state-representation map."),
    ("ray_aware_representation", "$Psi^\"ray\"$", "Ray-aware state-representation map."),
    ("pose_history_state", "$Psi^\"pose\"(s_(n,t)^\"cf\")$", "Pose-history representation of a counterfactual state."),
    ("selected_surface_state", "$Psi^\"surface\"(s_(n,t)^\"cf\")$", "Selected-surface representation of a counterfactual state."),
    ("ray_aware_state", "$Psi^\"ray\"(s_(n,t)^\"cf\")$", "Ray-aware representation of a counterfactual state."),
    ("selected_observation_state", "$Psi^\"obs\"(s_(n,t)^\"cf\")$", "State augmented only with selected observations."),
    ("privileged_selected_depth_state", "$Psi^\"GT-depth\"(s_(n,t)^\"cf\")$", "Privileged selected-depth control representation."),
    ("q_weight", "$bold(w)_Q$", "Weight vector of a linear Q head."),
    ("q_loss", "$cal(L)_Q(theta)$", "Q-function training loss."),
    ("coral_q_edge", "$e_k^Q$", "Boundary assigning a continuous target to CORAL classes."),
    ("coral_q_value", "$u_k^Q$", "Continuous representative of a CORAL class."),
    ("coral_q_label", "$c_m^Q$", "Ordinal class assigned to a fitted-Q target."),
): add("model", key, expr, comment)

for key, expr, comment in (
    ("target_mesh", "$cal(M)_e^\"GT\"$", "Privileged target-mesh crop."),
    ("candidate_depth", "$tilde(bold(D))_(t,i)^\"GT\"$", "Privileged candidate depth render."),
    ("candidate_points", "$tilde(cal(P))_(t,i)^\"GT\"$", "Privileged candidate point contribution."),
    ("candidate_projection_mask", "$tilde(bold(M))_(t,i)^\"GT\"$", "Valid-pixel mask for a privileged candidate render."),
    ("selected_depth", "$bold(D)_(n,t)^\"GT,sel\"$", "Privileged selected-depth control carrier."),
    ("information", "$cal(I)^\"oracle\"$", "Privileged information available only to labels and evaluation."),
): add("oracle", key, expr, comment)

for key, expr, comment in (
    ("loss", "$cal(L)^\"VIN\"$", "Historical VIN training loss."),
    ("pose_embedding", "$bold(z)_q^\"VIN,pose\"$", "Historical VIN pose embedding."),
    ("voxel_token", "$bold(z)^\"VIN,vox\"$", "Historical VIN voxel token."),
    ("position_embedding", "$bold(z)^\"VIN,pos\"$", "Historical VIN positional encoding."),
    ("global_context", "$bold(z)^\"VIN,global\"$", "Historical VIN global context."),
    ("attention_query", "$bold(q)^\"VIN\"$", "Historical VIN attention query."),
    ("attention_key", "$bold(k)^\"VIN\"$", "Historical VIN attention key."),
    ("attention_value", "$bold(v)^\"VIN\"$", "Historical VIN attention value."),
    ("weight", "$bold(W)^\"VIN\"$", "Historical VIN weight matrix."),
    ("film_scale", "$bold(gamma)^\"VIN\"$", "Historical VIN FiLM scale."),
    ("film_shift", "$bold(beta)^\"VIN\"$", "Historical VIN FiLM shift."),
    ("rri_target", "$op(\"RRI\")_i^\"VIN\"$", "Historical VIN one-step RRI target."),
    ("rri_prediction", "$hat(op(\"RRI\"))_i^\"VIN\"$", "Historical VIN predicted RRI."),
    ("lookat", "$bold(z)^\"VIN,look\"$", "Historical VIN look-at feature."),
    ("face_visibility", "$bold(F)^\"VIN,vis\"$", "Historical VIN cumulative face visibility."),
    ("face_visibility_step", "$bold(f)^\"VIN,vis\"$", "Historical VIN instantaneous face visibility."),
): add("vin", key, expr, comment)

shape_entries = OrderedDict([
    ("batch_count", "$N_B$"), ("sample_count", "$N_\"sample\"$"),
    ("state_count", "$N_s$"), ("candidate_count", "$N_q$"),
    ("candidate_capacity", "$N_q^\"max\"$"), ("target_count", "$N_e$"),
    ("rollout_count", "$N_\"cf\"$"), ("history_count", "$N_\"hist\"$"),
    ("trajectory_length", "$N_\"traj\"$"), ("point_count", "$N_p$"),
    ("point_capacity", "$N_p^\"max\"$"), ("projected_point_count", "$N_p^\"proj\"$"),
    ("frustum_point_count", "$N_p^\"fr\"$"), ("voxel_count", "$N_v$"),
    ("mesh_vertex_count", "$N_\"vert\"$"), ("ordinal_bin_count", "$N_\"bin\"$"),
    ("sem_dense_grid_count", "$N_\"sem-grid\"$"), ("image_height", "$H_\"img\"$"),
    ("image_width", "$W_\"img\"$"), ("feature_dim", "$d_\"feat\"$"),
    ("sem_dense_dim", "$d_\"semi\"$"), ("input_dim", "$d_\"in\"$"),
    ("scene_dim", "$d_\"scene\"$"), ("pose_dim", "$d_\"pose\"$"),
    ("position_dim", "$d_\"pos\"$"), ("candidate_dim", "$d_\"cand\"$"),
    ("global_dim", "$d_\"global\"$"), ("trajectory_dim", "$d_\"traj\"$"),
    ("projection_dim", "$d_\"proj\"$"), ("cnn_dim", "$d_\"cnn\"$"),
    ("token_dim", "$d_\"token\"$"), ("frustum_dim", "$d_\"frustum\"$"),
    ("point_dim", "$d_\"point\"$"), ("auxiliary_dim", "$d_\"aux\"$"),
    ("head_dim", "$d_\"head\"$"), ("hidden_dim", "$d_\"hidden\"$"),
    ("pool_dim", "$d_\"pool\"$"), ("model_dim", "$d_\"model\"$"),
])
for key, expr in shape_entries.items():
    add("shape", key, expr, "Implementation count or tensor dimension; excluded from the thesis symbol list.")

# Discover residual authored references after the migration. Unaffected support
# symbols are retained only when they still have an actual consumer.
REF_PATTERN = re.compile(r"symb\.([a-z_]+)\.([A-Za-z_][A-Za-z0-9_]*)")
references: dict[str, set[str]] = defaultdict(set)
for path in iter_text_files():
    if path == SYMBOL_ROOT or path.parent == SYMBOL_DIR or relative(path) in GENERATED_PATHS:
        continue
    for module, key in REF_PATTERN.findall(read(path)):
        references[module].add(key)
for module, keys in references.items():
    if module not in CURATED:
        raise RuntimeError(f"unknown symbol module after migration: {module}")
    for key in sorted(keys):
        if key in CURATED[module]:
            continue
        old = OLD_MODULES.get(module, {}).get(key)
        if old is None:
            raise RuntimeError(f"missing migrated symbol definition: symb.{module}.{key}")
        CURATED[module][key] = Entry(old.expr, (old.comment or "Support symbol") + "; retained because it remains authored.")

# Migrate old metadata keys and keep records only for final extant definitions.
for record in OLD_RECORDS:
    record.key = KEY_MAP.get(record.key, record.key)
records_by_key: dict[str, Record] = {}
for record in OLD_RECORDS:
    module, _, name = record.key.partition(".")
    if module not in CURATED or name not in CURATED[module]:
        continue
    if module in {"shape", "vin", "frame"}:
        record.thesis_list = False
    records_by_key.setdefault(record.key, record)


def meta(key: str, tex: str, description: str, thesis: bool, order: int) -> None:
    records_by_key[key] = Record(key, tex, description, thesis, order)


for args in (
    ("trajectory.factual", r"\tau", "Factual recorded trajectory.", True, 200),
    ("trajectory.counterfactual", r"\tau_n^{\mathrm{cf}}", "Counterfactual rollout n.", True, 210),
    ("trajectory.composite", r"\bar{\tau}_n", "Factual prefix followed by counterfactual rollout n.", True, 220),
    ("entity.target", "e", "Fixed target for one target-conditioned task.", True, 300),
    ("entity.descriptor", r"\boldsymbol{\phi}_e", "Actor-visible target descriptor.", True, 310),
    ("entity.center_world", r"\boldsymbol{p}_e^w", "Target centre in world coordinates.", True, 320),
    ("entity.extent", r"\boldsymbol{a}_e", "Metric target extent vector.", True, 330),
    ("spatial.transform", r"\boldsymbol{T}_a^b", "Rigid transform from source a to destination b.", True, 400),
    ("spatial.factual_rig_pose", r"\boldsymbol{T}_r^w(t)", "Factual world-from-rig pose.", True, 410),
    ("spatial.factual_camera_pose", r"\boldsymbol{T}_c^w(t)", "Factual world-from-camera pose.", True, 420),
    ("spatial.counterfactual_camera_pose", r"\boldsymbol{T}_{c_n^{\mathrm{cf}}}^w(t)", "Realised counterfactual camera pose.", True, 430),
    ("spatial.candidate_camera_pose", r"\boldsymbol{T}_{\tilde c_i}^w(t)", "Prospective candidate-camera endpoint.", True, 440),
    ("obs.factual", "o_t", "Factual observation.", True, 500),
    ("obs.counterfactual", r"o_{n,t}^{\mathrm{cf}}", "Realised counterfactual observation.", True, 510),
    ("obs.accumulated_points", r"\mathcal{P}_t", "Actor-visible accumulated points.", True, 520),
    ("scene.memory", r"\boldsymbol{\Phi}_t", "Actor-visible scene memory.", True, 600),
    ("metric.point_mesh_error", "D", "Aggregate point-mesh reconstruction error.", True, 700),
    ("metric.target_error", r"\Delta_t^e", "Target reconstruction error.", True, 710),
    ("metric.target_rri", r"\mathrm{RRI}_{t,i}^e", "State-relative target one-step RRI.", True, 720),
    ("metric.candidate_gain", "g_{t,i}^e", "Root-normalized candidate gain.", True, 730),
    ("metric.endpoint_gain", "J_e^{(H)}", "Fixed-budget endpoint gain.", True, 740),
    ("metric.lookahead_headroom", r"\Delta J_e^{\mathrm{look}}", "Bounded-lookahead endpoint headroom.", True, 750),
    ("rl.factual_state", "s_t", "State induced by the factual trajectory.", True, 800),
    ("rl.counterfactual_state", r"s_{n,t}^{\mathrm{cf}}", "State on realised counterfactual rollout n.", True, 810),
    ("rl.candidate_table", r"\mathcal{Q}_t", "Finite permutation-insensitive candidate family.", True, 820),
    ("rl.candidate", "q_{t,i}", "Candidate/action record i.", True, 830),
    ("rl.action_set", r"\mathcal{A}(s_t)", "Admitted candidate-row indices.", True, 840),
    ("rl.admission_mask", r"m_{t,i}^{\mathrm{adm}}", "Candidate-admission indicator.", True, 850),
    ("rl.target_reward", "r_t^e", "Selected target-specific immediate reward.", True, 860),
    ("rl.return", "G_{t,e}^{(h)}", "Target-conditioned residual-horizon return.", True, 870),
    ("rl.q", r"Q_{\theta}", "Shared horizon-conditioned candidate-value function.", True, 880),
    ("rl.candidate_value", r"Q_{\theta}(s_t,e,i,h)", "Candidate value emitted by the shared scorer.", False, 881),
    ("rl.transition", r"\mathcal{T}", "Selected-action state transition.", True, 890),
    ("rl.requested_horizon", "h", "Requested residual horizon.", True, 900),
    ("rl.endpoint_horizon", "H", "Fixed endpoint/evaluation horizon.", True, 910),
    ("rl.max_horizon", r"H_{\mathrm{max}}", "Maximum supported requested horizon.", True, 920),
    ("rl.budget", "b_t", "Remaining acquisition budget.", True, 930),
    ("model.target_token", r"\boldsymbol{z}_e", "Learned target token.", True, 1000),
    ("model.candidate_row", r"\boldsymbol{x}_{t,i}", "Typed candidate input row.", True, 1010),
    ("model.candidate_token", r"\boldsymbol{z}_{t,i}", "Learned candidate token.", True, 1020),
    ("model.history_pose_token", r"\boldsymbol{z}_{t,j}^{\mathrm{hist}}", "Earlier realised pose encoding.", True, 1030),
    ("oracle.target_mesh", r"\mathcal{M}_e^{\mathrm{GT}}", "Privileged target-mesh crop.", True, 1100),
    ("oracle.candidate_depth", r"\widetilde{\boldsymbol{D}}_{t,i}^{\mathrm{GT}}", "Privileged candidate depth render.", True, 1110),
    ("oracle.candidate_points", r"\widetilde{\mathcal{P}}_{t,i}^{\mathrm{GT}}", "Privileged candidate point contribution.", True, 1120),
    ("ase.scene_mesh", r"\mathcal{M}^{\mathrm{GT}}", "Ground-truth ASE scene mesh.", True, 1200),
): meta(*args)

# Verify glossary symbol_refs resolve after migration.
for key in re.findall(r'"([a-z_]+\.[A-Za-z_][A-Za-z0-9_]*)"', replace_symbol_ref_blocks(read(GLOSSARY))):
    module, _, name = key.partition(".")
    if module in CURATED and name in CURATED[module] and key not in records_by_key:
        raise RuntimeError(f"glossary symbol reference lacks metadata: {key}")

# Reject duplicate rendered entries in the public thesis list.
def normalized_tex(tex: str) -> str:
    return re.sub(r"\s+", "", tex).replace("\\mathrm", "\\operatorname")

seen: dict[str, str] = {}
for record in sorted(records_by_key.values(), key=lambda item: (item.order, item.key)):
    if not record.thesis_list:
        continue
    norm = normalized_tex(record.tex)
    if norm in seen:
        record.thesis_list = False
    else:
        seen[norm] = record.key


def render_record(record: Record) -> str:
    return (
        "  (key: " + json.dumps(record.key)
        + ", tex: " + json.dumps(record.tex)
        + ", description: " + json.dumps(record.description)
        + ", thesis_list: " + ("true" if record.thesis_list else "false")
        + ", order: " + str(record.order) + "),"
    )

# Co-locate symbol values and metadata in their semantic owner modules.
for module in MODULE_ORDER:
    lines = [f"// Canonical {module} notation.", f"#let {module} = ("]
    for key, entry in CURATED[module].items():
        lines.append(f"  // {entry.comment}")
        lines.append(f"  {key}: {entry.expr},")
    lines.extend([")", "", f"#let {module}-notation = ("])
    for record in sorted(
        (r for r in records_by_key.values() if r.key.startswith(module + ".")),
        key=lambda item: (item.order, item.key),
    ):
        lines.append(render_record(record))
    lines.append(")")
    write(SYMBOL_DIR / f"{module}.typ", "\n".join(lines))

# symbols.typ becomes a pure facade/aggregator; preserve the existing metadata
# emission suffix used by typst query.
facade = [
    "// Shared symbol facade composed from semantic domain modules.",
    "// Values and metadata are co-located in symbols/*.typ.",
    "",
]
for module in MODULE_ORDER:
    facade.append(f'#import "symbols/{module}.typ": {module}, {module}-notation')
facade.extend(["", "#let symb = ("])
for module in MODULE_ORDER:
    facade.append(f"  {module}: {module},")
facade.extend([")", "", "#let aria-notation-symbols ="])
for index, module in enumerate(MODULE_ORDER):
    facade.append(("  " if index == 0 else "  + ") + f"{module}-notation")
write(SYMBOL_ROOT, "\n".join(facade) + ROOT_SUFFIX)

# Update the central equation metadata without changing stable equation IDs.
EQ_OVERRIDES = {
    "rl.finite_action_set": (
        r"\mathcal{Q}_t=\{q_{t,i}\}_{i=1}^{N_q},\quad \mathcal{A}(s_t)=\{i:m_{t,i}^{\mathrm{adm}}=1\}",
        "Candidate family and admitted action-index set are distinct; candidate order is semantically irrelevant.",
        False,
    ),
    "rl.finite_horizon_return": (
        r"G_{t,e}^{(h)}=\sum_{\ell=0}^{h-1}\gamma^{\ell}r_{t+\ell}^{e}",
        "Target-conditioned return over requested residual horizon h.",
        True,
    ),
    "rl.qh_scorer_interface": (
        r"Q_{\theta}(s_t,e,i,h)",
        "Shared horizon-conditioned candidate-value interface.",
        True,
    ),
    "rl.q_h": (
        r"Q^{\star}(s_t,e,i,h)=\sup_{\pi}\mathbb{E}_{\pi}[G_{t,e}^{(h)}\mid s_t,a_t=i]",
        "Finite-horizon target-conditioned candidate value.",
        True,
    ),
    "rl.qh_exact_q2_target": (
        r"y_{t,e}^{(2,\mathrm{diag})}",
        "Bounded Bellman-target and successor-linkage diagnostic; not a policy-evidence gate.",
        False,
    ),
    "rl.qh_exact_q2_error": (
        r"\varepsilon_{t,e}^{(2,\mathrm{diag})}",
        "Error against the local two-step Bellman diagnostic.",
        False,
    ),
}


def patch_equation_registry(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group("key")
        if key not in EQ_OVERRIDES:
            return match.group(0)
        tex, description, thesis = EQ_OVERRIDES[key]
        order = int(match.group("order"))
        record = Record(key, tex, description, thesis, order)
        return render_record(record)
    return RECORD_PATTERN.sub(repl, text)

write(EQUATION_ROOT, patch_equation_registry(read(EQUATION_ROOT)))

# Strengthen duplicate-render validation if absent.
builder = ROOT / "scripts/glossary_build.py"
builder_text = read(builder)
if "duplicate rendered thesis symbol" not in builder_text:
    start = builder_text.find("def _validate_notation_metadata(")
    if start < 0:
        raise RuntimeError("cannot locate notation metadata validator")
    next_def = builder_text.find("\ndef ", start + 4)
    if next_def < 0:
        raise RuntimeError("cannot locate validator end")
    insertion = '''\n    rendered: dict[str, str] = {}\n    for key, entry in notation["symbols"].items():\n        if not entry.get("thesis_list"):\n            continue\n        normalized = re.sub(r"\\s+", "", str(entry["tex"]))\n        previous = rendered.get(normalized)\n        if previous is not None and previous != key:\n            raise GlossaryError(\n                f"duplicate rendered thesis symbol {entry['tex']!r}: "\n                f"{previous!r} and {key!r}"\n            )\n        rendered[normalized] = key\n'''
    builder_text = builder_text[:next_def] + insertion + builder_text[next_def:]
    write(builder, builder_text)

# Dedicated semantic regression tests.
write(
    ROOT / "scripts/tests/test_symbol_semantics.py",
    r'''from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYMBOLS = ROOT / "docs/typst/shared/symbols"
FACADE = ROOT / "docs/typst/shared/symbols.typ"


def _all() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SYMBOLS.glob("*.typ"))


def test_semantic_owner_modules_exist() -> None:
    assert (SYMBOLS / "metric.typ").is_file()
    assert (SYMBOLS / "trajectory.typ").is_file()


def test_symbols_facade_is_not_a_second_metadata_owner() -> None:
    text = FACADE.read_text(encoding="utf-8")
    assert '(key: "' not in text
    assert "metric-notation" in text and "trajectory-notation" in text


def test_factuality_and_indices_are_canonical() -> None:
    trajectory = (SYMBOLS / "trajectory.typ").read_text(encoding="utf-8")
    rl = (SYMBOLS / "rl.typ").read_text(encoding="utf-8")
    assert 'factual: $tau$' in trajectory
    assert 'counterfactual: $tau_n^"cf"$' in trajectory
    assert '^"Aria"' not in trajectory
    assert 'rollout_index: $n$' in trajectory
    assert 'factual_state: $s_t$' in rl
    assert 'counterfactual_state: $s_(n,t)^"cf"$' in rl


def test_internal_state_discriminators_are_not_public_symbols() -> None:
    text = _all()
    for legacy in ('s_t^"hist"', 's_t^"off"', 's_t^"cf0"', 'S0-pose',
                   'S1-surface', 'S2-ray', 's_t^"cf+"', 'CF-GT-carrier',
                   's_t^"oracle"'):
        assert legacy not in text


def test_value_target_and_objective_families_are_separated() -> None:
    text = _all()
    assert 'target: $e$' in (SYMBOLS / "entity.typ").read_text(encoding="utf-8")
    assert 'candidate_value: $Q_theta(s_t,e,i,h)$' in text
    assert 'target_rri: $op("RRI")_(t,i)^e$' in text
    assert 'candidate_gain: $g_(t,i)^e$' in text
    assert 'target_reward: $r_t^e$' in text
    assert 'return: $G_(t,e)^((h))$' in text
    for legacy in ('Q_H', 'Q_(H,theta)', 'Q_(h,theta,e,i)', '$e_t$'):
        assert legacy not in text


def test_latents_and_physical_points_use_different_families() -> None:
    model = (SYMBOLS / "model.typ").read_text(encoding="utf-8")
    assert 'target_token: $bold(z)_e$' in model
    assert 'history_pose_token: $bold(z)_(t,j)^"hist"$' in model
    assert 'history_pose_token: $bold(p)' not in model


def test_shapes_use_count_and_width_families() -> None:
    shape = (SYMBOLS / "shape.typ").read_text(encoding="utf-8")
    for bare in ('  B:', '  N:', '  Tlen:', '  P:', '  D:', '  H:',
                 '  Wdim:', '  Vvox:', '  M:', '  K:'):
        assert bare not in shape
    assert 'candidate_count: $N_q$' in shape
    assert 'model_dim: $d_"model"$' in shape
    assert 'thesis_list: true' not in shape


def test_shared_equations_do_not_use_arrow_indexed_transforms() -> None:
    equations = ROOT / "docs/typst/shared/equations"
    offenders = []
    pattern = re.compile(r"(?:bold\(T\)|(?<![A-Za-z_])T)_\([^\n]*arrow\.l")
    for path in equations.glob("*.typ"):
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(path.name)
    assert not offenders, offenders
''',
)

# Final static invariants before external tooling regenerates projections.
assert '(key: "' not in read(SYMBOL_ROOT)
assert 'transition: $cal(T)$' in read(SYMBOL_DIR / "rl.typ")
assert '$e_t$' not in read(SYMBOL_DIR / "rl.typ")
assert (SYMBOL_DIR / "metric.typ").exists()
assert (SYMBOL_DIR / "trajectory.typ").exists()
for path in SYMBOL_DIR.glob("*.typ"):
    text = read(path)
    if "unused duplicate" in text or "compatibility alias" in text:
        raise RuntimeError(f"duplicate/compatibility language remains in {path.name}")

print("PR224 semantic notation migration applied")
