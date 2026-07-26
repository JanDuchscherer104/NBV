# Graph Report - ARIA-NBV

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 11110 nodes · 20212 edges · 475 communities (465 shown, 10 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 1737 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0ce5946a109a70f948e2215e4588d1ffb199be70`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 49
- Community 52
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 61
- Community 62
- Community 65
- Community 67
- Community 68
- Community 70
- Community 71
- Community 72
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 90
- Community 91
- Community 92
- Community 93
- Community 95
- Community 97
- Community 98
- Community 99
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 110
- Community 112
- Community 116
- Community 117
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 128
- Community 129
- Community 133
- Community 134
- Community 135
- Community 136
- Community 139
- Community 140
- Community 144
- Community 146
- Community 150
- Community 151
- Community 152
- Community 153
- Community 158
- Community 159
- Community 160
- Community 163
- Community 167
- Community 171
- Community 172
- Community 173
- Community 174
- Community 179
- Community 184
- Community 185
- Community 194
- Community 195
- Community 196
- Community 202
- Community 203
- Community 204
- Community 205
- Community 217
- Community 218
- Community 219
- Community 233
- Community 234
- Community 235
- Community 240
- Community 242
- Community 243
- Community 244
- Community 245
- Community 253
- Community 254
- Community 255
- Community 256
- Community 266
- Community 279
- Community 280
- Community 281
- Community 295
- Community 304
- Community 305
- Community 308
- Community 309
- Community 310
- Community 311
- Community 312
- Community 319
- Community 320
- Community 321
- Community 322
- Community 323
- Community 331
- Community 332
- Community 347
- Community 349
- Community 350
- Community 351
- Community 388
- Community 389
- Community 390
- Community 391
- Community 392
- Community 442
- Community 443
- Community 444
- Community 445

## God Nodes (most connected - your core abstractions)
1. `EfmSnippetView` - 123 edges
2. `PathConfig` - 96 edges
3. `RolloutZarrStoreReader` - 90 edges
4. `Console` - 86 edges
5. `CandidateSamplingResult` - 84 edges
6. `BaseConfig` - 83 edges
7. `VinOfflineSample` - 76 edges
8. `VinOracleBatch` - 68 edges
9. `VinOfflineIndexRecord` - 65 edges
10. `VinOfflineStoreConfig` - 57 edges

## Surprising Connections (you probably didn't know these)
- `symb_use_L208_1_ase_mesh_74889664()` --calls--> `symb_ase_mesh()`  [INFERRED]
  docs/typst/shared/data-layout-trees.typ → docs/typst/shared/symbols/ase.typ
- `symb_use_L6_2_shape_Nq_407ef9c0()` --calls--> `symb_shape_Nq()`  [INFERRED]
  docs/typst/shared/equations/action.typ → docs/typst/shared/symbols/shape.typ
- `symb_use_L8_1_shape_Nq_407ef9c0()` --calls--> `symb_shape_Nq()`  [INFERRED]
  docs/typst/shared/equations/action.typ → docs/typst/shared/symbols/shape.typ
- `symb_use_L70_1_shape_Nq_407ef9c0()` --calls--> `symb_shape_Nq()`  [INFERRED]
  docs/typst/shared/equations/action.typ → docs/typst/shared/symbols/shape.typ
- `symb_use_L13_1_entity_target_desc_f8bba4f4()` --calls--> `symb_entity_target_desc()`  [INFERRED]
  docs/typst/shared/equations/entity.typ → docs/typst/shared/symbols/entity.typ

## Import Cycles
- None detected.

## Communities (475 total, 10 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (120): eqs_action_candidate_shell(), eqs_action_space(), eqs_metrics_candidate_validity(), eqs_metrics_spearman(), eqs_metrics_topk_acc(), eqs_rl_mdp(), eqs_rl_nbv_mdp(), eqs_rl_nbv_process_tuple() (+112 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (139): AbstractContextManager, NbvStreamlitApp, Lazy page router for the ARIA-NBV Streamlit application.  The application frame, Render proposal diagnostics with page-owned single-step controls., Render one observed snippet with page-owned dataset controls., Render candidate depths with page-owned renderer controls., Render the grouped NBV inspection application from one configuration.      Datas, Render oracle RRI with page-owned scoring controls. (+131 more)

### Community 2 - "Community 2"
Cohesion: 0.02
Nodes (158): symb_use_L209_1_entity_target_desc_f8bba4f4(), symb_use_L78_1_rl_action_set_t_3b273a63(), symb_use_L83_1_rl_action_set_t_3b273a63(), symb_use_L22_1_entity_target_desc_f8bba4f4(), symb_use_L104_1_rl_s_cf_geom_7c1e8c4f(), symb_use_L114_1_rl_o_d8804e95(), symb_use_L116_2_rl_x_76387f89(), symb_use_L119_1_rl_m_74e7e94a() (+150 more)

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (101): Configuration management for aria_nbv.  This module provides centralized configu, OptunaConfig, Any, Callback, Optuna study construction and config-tree search-space application.  This module, Send the most recent suggestions to W&B., Return a PyTorch Lightning pruning callback for the configured monitor., Configure an Optuna study used by :class:`aria_nbv.lightning.AriaNBVExperimentCo (+93 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (105): Create the scorer and target runtime context for a live rollout., Generate one live rollout result and capture Console logs for display., _run_live_rollout(), _score_context_for_mode(), Sidebar controls that construct typed NBV pipeline configurations.  The helpers, build_root_eval_pointcloud(), canonical_fuse_points(), crop_mesh_to_obb() (+97 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (112): Render immutable root-observation-store diagnostics., _coverage_rows(), _load_offline_store_from_toml(), Path, Standalone diagnostics for immutable VIN offline datasets.  The module provides, Return per-scene coverage rows., Render raw-dataset coverage diagnostics., Return the immutable VIN store configured by an experiment TOML. (+104 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (113): _activate_query_store(), _apply_query_callback(), _apply_query_state(), _cached_evidence_bundle(), _cached_projection(), _cached_store_bundle(), _cached_topology(), _candidate_flow_figure() (+105 more)

### Community 7 - "Community 7"
Cohesion: 0.04
Nodes (88): _apply_manifest_rows(), Path, Select manifest rows in exact configured sample-key order., Filter and order a VIN reader from validated source-row records., Configuration for building standalone target-RRI rollout Zarr stores.      The s, Resolve a configured source manifest relative to the repository root., Normalize an exact ordered sample-key selection and reject ambiguity., Require direct pilot configs to match their reviewed ordered source rows. (+80 more)

### Community 8 - "Community 8"
Cohesion: 0.04
Nodes (102): Render Weights & Biases run analysis., _cached_entities(), _cached_projects(), _normalize_step_bounds(), Any, Weights & Biases run comparison and training-dynamics diagnostics.  The panel pr, Normalize step bounds, returning (min,max,error_message)., Render cross-run analytics from W&B run history. (+94 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (102): Render the interactive counterfactual-rollout laboratory., _add_target_overlays(), _add_target_semidense_crop(), _aligned_valid_vector(), _array_value(), _build_fanout_band_figure(), _build_live_dataset_config(), _candidate_config_device() (+94 more)

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (82): Initialize the inspector runtime., Display selected-only mesh depth retained by a rollout Zarr store.      Depth is, Compose source selection, recording lifecycle, and visualization policy.      Th, Resolve offline and rollout context with deterministic selector precedence., Require scene/snippet selectors to be supplied together., RerunInspectorRolloutDepthConfig, RerunInspectorSelectionConfig, RerunOfflineInspectorConfig (+74 more)

### Community 12 - "Community 12"
Cohesion: 0.03
Nodes (81): symb_use_L10_1_oracle_points_032d9bc0(), symb_use_L10_2_oracle_points_032d9bc0(), symb_use_L11_1_oracle_reference_geometry_c981bbad(), symb_use_L13_1_oracle_reference_geometry_c981bbad(), symb_use_L13_2_oracle_points_032d9bc0(), symb_use_L14_1_oracle_reference_samples_27045dc4(), symb_use_L14_2_oracle_reference_samples_27045dc4(), symb_use_L15_1_oracle_points_032d9bc0() (+73 more)

### Community 13 - "Community 13"
Cohesion: 0.05
Nodes (91): _policy_name(), Composed source, target, and policy lineage flattened only by the writer., Return persisted lineage identifiers for one retained chain., RolloutLineage, _termination_reason(), _accumulate_selected_metric(), _add_manifest_hash(), _append_candidate_diagnostic_row() (+83 more)

### Community 14 - "Community 14"
Cohesion: 0.02
Nodes (68): symb_use_L208_1_ase_mesh_74889664(), symb_use_L211_1_oracle_center_c037f29d(), symb_use_L226_1_oracle_candidates_t_47cd08c5(), symb_use_L227_1_oracle_candidate_qti_34144333(), symb_use_L228_1_rl_validity_mask_8058869f(), symb_use_L234_1_oracle_depth_q_3b0cfae9(), symb_use_L235_1_oracle_mask_q_96e812ad(), symb_use_L107_1_oracle_depth_q_3b0cfae9() (+60 more)

### Community 15 - "Community 15"
Cohesion: 0.03
Nodes (59): symb_use_L279_1_shape_B_c1b74290(), symb_use_L280_1_shape_B_c1b74290(), symb_use_L282_1_shape_B_c1b74290(), symb_use_L284_1_shape_B_c1b74290(), symb_use_L287_2_shape_B_c1b74290(), symb_use_L287_3_shape_D_781a1f31(), symb_use_L289_2_shape_B_c1b74290(), symb_use_L289_3_shape_D_781a1f31() (+51 more)

### Community 16 - "Community 16"
Cohesion: 0.02
Nodes (29): symb_use_L334_1_oracle_err_0cf392a4(), symb_use_L336_1_oracle_err_0cf392a4(), symb_use_L341_1_oracle_err_0cf392a4(), symb_use_L343_1_oracle_err_0cf392a4(), symb_use_L12_1_oracle_err_0cf392a4(), symb_use_L47_1_oracle_err_0cf392a4(), symb_use_L49_1_oracle_err_0cf392a4(), symb_use_L52_1_oracle_err_0cf392a4() (+21 more)

### Community 17 - "Community 17"
Cohesion: 0.04
Nodes (81): symb_use_L105_1_ase_mesh_74889664(), symb_use_L116_1_ase_mesh_74889664(), symb_use_L334_3_ase_mesh_74889664(), symb_use_L336_3_ase_mesh_74889664(), symb_use_L341_3_ase_mesh_74889664(), symb_use_L343_3_ase_mesh_74889664(), symb_use_L12_2_oracle_points_032d9bc0(), symb_use_L12_3_ase_mesh_74889664() (+73 more)

### Community 18 - "Community 18"
Cohesion: 0.06
Nodes (55): Join replay transitions with pipeline-local Oracle outputs.  This module provide, ensure_unbatched_pose(), PoseTW, Squeeze a singleton batch from :class:`PoseTW` while preserving unbatched poses., Target-conditioned replay transitions and persisted rollout stores.  `aria_nbv.r, _angular_separation(), _append_diversity_selection(), _CandidateDiversityMetadata (+47 more)

### Community 19 - "Community 19"
Cohesion: 0.05
Nodes (60): Build a target-aware mixed candidate generator from per-family counts., _target_mixture_config(), candidate_config_ui(), Render finite-candidate controls and return a validated config copy.      Distan, CandidateViewGeneratorConfig, r"""Candidate pose generation with modular sampling and pruning rules.  This mod, Return the lower candidate elevation bound in radians., Return the upper candidate elevation bound in radians. (+52 more)

### Community 20 - "Community 20"
Cohesion: 0.03
Nodes (78): symb_use_L23_1_scene_target_support_pool_626ec9d6(), symb_use_L39_1_scene_frustum_support_pool_a100875f(), symb_use_L40_1_scene_target_frustum_pool_27e828cf(), symb_use_L41_1_scene_ray_query_ti_54319867(), symb_use_L42_1_scene_evl_support_token_e6562f55(), symb_use_L77_1_scene_scene_memory_t_f39b4ba7(), symb_use_L9_1_scene_scene_memory_t_f39b4ba7(), eqs_scene_scene_memory_decomposition() (+70 more)

### Community 21 - "Community 21"
Cohesion: 0.06
Nodes (79): _add_target_context_overlay(), _candidate_provenance_preview(), _color_payload_np(), _full_shell_color_payload(), _motion_threshold_rows(), _pose_orthonormality_stats(), ndarray, PoseTW (+71 more)

### Community 22 - "Community 22"
Cohesion: 0.05
Nodes (45): Checkpoint setup and no-gradient forward passes for VIN diagnostics.  This modul, Run one diagnostic VIN forward pass and restore the prior model mode.      Args:, run_vin_diagnostics(), device, PerspectiveCameras, PoseTW, Tensor, Return clamped valid-prefix lengths as ``Tensor["", int64]`` or ``Tensor["B", in (+37 more)

### Community 24 - "Community 24"
Cohesion: 0.03
Nodes (73): eqs_entity_objective(), eqs_entity_target_descriptor(), symb_use_L106_1_entity_q_recovery_238f4ed4(), symb_use_L10_1_entity_lambda_scene_bb771858(), symb_use_L10_2_oracle_rri_8cfa0f49(), symb_use_L13_1_entity_target_desc_f8bba4f4(), symb_use_L69_1_entity_target_error_3b780437(), symb_use_L71_2_ase_mesh_target_8765011e() (+65 more)

### Community 25 - "Community 25"
Cohesion: 0.06
Nodes (62): Render VIN model diagnostics., Render ordinal RRI binning diagnostics., _info_popover(), Exception, Shared presentation and error-reporting helpers for Streamlit panels.  The modul, Render a full traceback in the UI and emit it to stdout., _report_exception(), _strip_ansi() (+54 more)

### Community 26 - "Community 26"
Cohesion: 0.05
Nodes (78): _apply_validity_override(), _as_1d_array(), _as_bool_array(), candidate_rgba(), _interpolate_rgb(), obb_semantic_rgba(), oracle_rri_to_rgba(), dtype (+70 more)

### Community 27 - "Community 27"
Cohesion: 0.04
Nodes (52): CandidateScorerConfig, CandidateScorerTrainingContract, Lightning-side validation for VIN candidate scorer contracts.  `aria_nbv.vin.can, Return the scorer contract or reject contracts unsupported by Lightning.      Ar, validate_vin_lightning_candidate_scorer_contract(), r"""Train the runnable one-step VIN candidate scorer with Lightning.  This modul, Log configured scorer gradient norms after Lightning backpropagation.          L, candidate_topk_oracle_hit() (+44 more)

### Community 28 - "Community 28"
Cohesion: 0.04
Nodes (37): term_aria_synthetic_environments(), term_egocentric_foundation_model_3d(), term_egocentric_voxel_lifting(), term_ground_truth(), term_use_L7_1_relative_reconstruction_improvem_f9d7e62d(), term_use_L7_2_aria_synthetic_environments_57d9ab1a(), term_use_L7_3_egocentric_foundation_model_3d_a3428ddc(), term_use_L9_1_ground_truth_short_f1a35f23() (+29 more)

### Community 29 - "Community 29"
Cohesion: 0.06
Nodes (75): _cached_inventory(), Project the immutable rollout-store inventory once per cache root., _array_size(), _arrays_equal(), candidate_flow_rows(), candidate_result_diagnostic_counts(), _cohort_id_from_key(), _cohort_ineligibility_reason() (+67 more)

### Community 30 - "Community 30"
Cohesion: 0.06
Nodes (69): camera_tw_pinhole_kwargs(), candidate_centers_world(), depth_hw(), deterministic_downsample(), display_rot90_cw(), image_hwc(), p3d_param_at(), p3d_pinhole_kwargs() (+61 more)

### Community 31 - "Community 31"
Cohesion: 0.03
Nodes (65): symb_use_L14_2_spatial_relation_rpe_502d7799(), symb_use_L31_1_spatial_candidate_pose_feat_f8ec6778(), symb_use_L32_1_spatial_candidate_target_rel_fea_db3e373e(), symb_use_L38_1_spatial_dir_moment_7b0efd97(), eqs_spatial_direction_memory_moment(), eqs_spatial_direction_memory_sh(), eqs_spatial_direction_unit(), symb_use_L10_1_spatial_dir_memory_5053b99d() (+57 more)

### Community 32 - "Community 32"
Cohesion: 0.06
Nodes (69): _cached_failures(), Cache failure triage for one immutable store and threshold tuple., candidate_audit_rows(), candidate_group_summary_rows(), decode_strategy_id(), _dominant_invalid_reason_rows(), _finite_or_none(), _high_score_invalid_target_rows() (+61 more)

### Community 33 - "Community 33"
Cohesion: 0.04
Nodes (51): Shared VIN oracle batch records, masking, and collation utilities.  This module, Summarize model-facing VIN batch shapes for diagnostics and logging.      Args:, summarize_vin_batch_shapes(), Raw ASE/EFM data interfaces used by ``aria_nbv.data_handling``.  This module pro, BaseView, EfmCameraView, EfmGtCameraObbView, EfmGtTimestampView (+43 more)

### Community 34 - "Community 34"
Cohesion: 0.05
Nodes (43): CompactObbBlock, CompactTrajectoryBlock, Collatable numeric OBB payload used by training and diagnostics.      ``obbs`` k, Preserve MPS/EFM timing and gravity metadata beside VIN trajectory poses., Any, dtype, ndarray, PerspectiveCameras (+35 more)

### Community 35 - "Community 35"
Cohesion: 0.05
Nodes (48): EvaluatedRollout, EvaluatedRolloutRecord, OracleReplayAdapter, OracleReplayInvalidityError, ValueError, Join cached Oracle outputs to retained replay chains., Pipeline control flow carrying a typed Oracle invalidity outcome., Replay result joined to Oracle outputs by chain and step index. (+40 more)

### Community 36 - "Community 36"
Cohesion: 0.05
Nodes (53): _ase_atek_identifier_variants(), Return raw and compact variants for matching one ASE-ATEK identifier., AseEfmDataset, AseEfmDatasetConfig, _find_tar_for_sample(), _infer_ids(), infer_semidense_bounds(), _looks_like_shard_id() (+45 more)

### Community 37 - "Community 37"
Cohesion: 0.05
Nodes (49): CandidateViewGenerator, _clone_camera_template(), _gravity_align_pose(), _maybe_seed(), CameraTW, device, PoseTW, Tensor (+41 more)

### Community 38 - "Community 38"
Cohesion: 0.06
Nodes (45): compute_downloaded_atek_stats(), count_snippets_in_tar(), DownloadedAtekStats, _estimate_snippet_count_from_shards(), _iter_downloaded_shard_tars(), Path, Helpers for reporting local download coverage and snippet counts for ATEK shards, Summary of available vs downloaded ATEK data for a given config. (+37 more)

### Community 39 - "Community 39"
Cohesion: 0.07
Nodes (56): Path, Typed manifest and index records for the VIN offline dataset format.  The new of, Top-level manifest for one immutable VIN offline dataset.      Attributes:, Persist the manifest to disk.          Args:             path: Destination manif, Load a manifest from disk.          Args:             path: Manifest JSON path., Global sample-index entry for VIN offline random access.      Attributes:, Read the global sample index.          Args:             path: ``sample_index.js, Write the global sample index.          Args:             path: Destination ``sa (+48 more)

### Community 40 - "Community 40"
Cohesion: 0.07
Nodes (64): VIN pose-vector and learnable Fourier feature diagnostics.  The tab provides inp, Render the FF Encodings tab.      Args:         ctx: Shared VIN diagnostics cont, render_encodings_tab(), _pretty_label(), Format labels by replacing underscores and title-casing words., _build_radius_fourier_figure(), Plot sin radius Fourier features for linear r (meters)., _histogram_bar() (+56 more)

### Community 41 - "Community 41"
Cohesion: 0.06
Nodes (59): Declare optional payload families present in a VIN offline store.      The flags, VinOfflineMaterializedBlocks, assign_offline_splits(), _camera_param_to_numpy(), _default_sample_key(), flush_prepared_samples_to_shard(), _keep_field(), _pad_first_axis() (+51 more)

### Community 42 - "Community 42"
Cohesion: 0.05
Nodes (46): PerspectiveCameras, PoseTW, Score candidate poses for one actor-visible snippet.          Args:, device, dtype, PerspectiveCameras, PoseTW, Tensor (+38 more)

### Community 43 - "Community 43"
Cohesion: 0.05
Nodes (57): compact_ase_atek_identifiers(), compact_ase_atek_sample_id(), Any, Canonical conversions between raw and compact ASE-ATEK identifiers.  These pure, Return the compact public identifier for one ASE-ATEK sample key., Return the raw ATEK key for a compact ASE-ATEK identifier., Recursively compact ASE-ATEK identifiers inside JSON-like objects., raw_ase_atek_sample_id() (+49 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (47): Canonical root sample for diagnostics and rollout generation.      `VinOfflineSa, VinOfflineSample, Return rotation and translation (world←cam) as numpy arrays., _compact_or_live_gt_obbs(), _detected_obb_semantic_names(), _detected_obbs(), _field_voxel_centers_world(), _gt_obb_semantic_names() (+39 more)

### Community 45 - "Community 45"
Cohesion: 0.06
Nodes (59): _render_rerun_launcher(), build_rerun_rollout_command(), build_rerun_rollout_spawn_command(), build_rerun_rollout_web_command(), detect_lan_ip(), format_command(), poll_rerun_launch(), _port_is_available() (+51 more)

### Community 46 - "Community 46"
Cohesion: 0.05
Nodes (57): build_frustum_points_world_p3d(), frustum_points_world_from_cameras(), PerspectiveCameras, PoseTW, Tensor, Frustum point sampling helpers for VIN geometry diagnostics.  The legacy experim, Unproject a square image grid at fixed depths into world points.      Args:, Generate per-candidate frustum sample points in world coordinates.      Args: (+49 more)

### Community 47 - "Community 47"
Cohesion: 0.08
Nodes (35): bbox_edges(), _flatten_edges_for_plotly(), get_frustum_segments(), plot_trajectory(), _pose_positions(), CameraTW, ndarray, ObbTW (+27 more)

### Community 49 - "Community 49"
Cohesion: 0.06
Nodes (35): device, Path, Initialize learnable CORAL bin values from the fitted binner., Initialize CORAL biases from fitted class priors (if configured)., Initialize binner-derived scorer state for a Lightning stage.          Lightning, Log the effective VIN config (post-sanitization) and persist it as JSON., Load a checkpoint and return an evaluation-ready scorer module.          Args:, Initialize mandatory binner-derived state before direct inference.          This (+27 more)

### Community 52 - "Community 52"
Cohesion: 0.06
Nodes (50): Small deterministic statistics helpers for app, plots, and exports.  The functio, build_alignment_figures(), build_candidate_encoding_figures(), build_field_token_histograms(), build_frustum_samples_figure(), build_lff_response_figures(), _build_lff_weight_figures(), build_prediction_alignment_figure() (+42 more)

### Community 54 - "Community 54"
Cohesion: 0.04
Nodes (11): symb_use_L27_1_vin_field_evl_0_9d2b1a47(), symb_use_L287_1_vin_occ_in_8dee4cc7(), symb_use_L289_1_vin_free_in_c2b4749b(), symb_use_L304_1_vin_cent_pr_577ebf19(), symb_use_L378_1_vin_occ_in_8dee4cc7(), symb_use_L379_1_vin_free_in_c2b4749b(), symb_use_L407_1_vin_cent_pr_577ebf19(), symb_vin_cent_pr() (+3 more)

### Community 55 - "Community 55"
Cohesion: 0.08
Nodes (49): _as_step_matrix(), _discount_weights(), discounted_selected_return(), _endpoint_errors(), endpoint_log_gain(), endpoint_log_gain_tensor(), endpoint_target_gain(), endpoint_target_gain_tensor() (+41 more)

### Community 56 - "Community 56"
Cohesion: 0.04
Nodes (36): symb_use_L71_1_obs_points_t_9aa40fb4(), symb_use_L54_1_obs_img_rgb_0ccbb0a8(), symb_use_L55_1_obs_pose_e941bdab(), symb_use_L56_1_obs_points_semi_6a3eef5c(), symb_use_L68_1_obs_points_semi_6a3eef5c(), symb_use_L97_1_obs_depth_eb85df5a(), symb_use_L97_2_obs_vis_d5922451(), symb_use_L97_3_obs_points_cf_c751f081() (+28 more)

### Community 57 - "Community 57"
Cohesion: 0.07
Nodes (44): Observed snippet inspection with optional oracle scene overlays.  The panel prov, Render modalities, poses, projections, and 3D context for one snippet.      Args, render_data_page(), apply_scene_plot_options(), Shared controls and typed options for snippet-level Plotly scene views.  This mo, Render shared 3D scene controls and return the chosen camera/options., Default visibility and style choices for a snippet 3D scene view., Apply shared scene options to a `SnippetPlotBuilder` subclass. (+36 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (44): Resolve an Oracle-selected target's matched GT OBB in world coordinates., target_gt_obb_world(), _class_name(), _compact_obb_block(), _first_scalar_string(), _float_tuple(), _latest_valid_obb_slice(), _obb_geometry_valid() (+36 more)

### Community 59 - "Community 59"
Cohesion: 0.05
Nodes (47): symb_use_L13_1_rl_H_b75d2b63(), symb_use_L14_1_model_candidate_row_74c08558(), symb_use_L14_3_shape_Nq_407ef9c0(), symb_use_L18_1_model_target_token_542325d3(), symb_use_L36_1_model_candidate_geometry_token_3ec0f4e4(), symb_use_L47_1_model_candidate_row_74c08558(), symb_use_L51_1_model_candidate_geometry_token_3ec0f4e4(), symb_use_L52_1_model_candidate_validity_token_61ad259f() (+39 more)

### Community 61 - "Community 61"
Cohesion: 0.07
Nodes (30): Figure, Log and reset stage-owned candidate ranking accumulators., Emit and reset accumulated training metrics at the epoch boundary., Emit/reset validation metrics and expected-RRI error statistics., Emit and reset accumulated test metrics at the epoch boundary., Logable, LogSpec, Loss (+22 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (45): Render the training-dataset composition hub., _artifact_identity(), _cached_bundle_summary(), _cached_deep_statistics(), _coral_artifact_identity(), _deep_metric_value(), _download_payload(), _format_bytes() (+37 more)

### Community 65 - "Community 65"
Cohesion: 0.07
Nodes (37): Build the configured rollout store.          In normal mode the configured sourc, collect_runtime_provenance(), _git_root(), _git_summary(), manifest_json_bytes(), manifest_sha256(), _package_versions(), Any (+29 more)

### Community 67 - "Community 67"
Cohesion: 0.07
Nodes (26): CandidatePlotBuilder, CounterfactualPlotBuilder, _pretty_metric_label(), Self, Fluent, snippet-aware builder for full-shell candidate diagnostics.      The bui, Create a snippet plot with candidate results already attached., Attach candidate sampling results for plotting., Attach candidate config for metadata-aware plotting. (+18 more)

### Community 68 - "Community 68"
Cohesion: 0.06
Nodes (22): eqs_model_qh_input_contract(), eqs_use_L59_1_model_qh_input_contract_ee97fd5c(), marker_evidence_L118_1_pending_e2258693(), marker_evidence_L11_1_pending_e2258693(), marker_evidence_L152_1_pending_e2258693(), marker_evidence_L49_1_pending_e2258693(), marker_gate_L118_1_frame_transform_row_shuffle_and__66ca11dc(), marker_gate_L11_1_preserve_row_identity_masks_prov_34558dfb() (+14 more)

### Community 70 - "Community 70"
Cohesion: 0.06
Nodes (21): marker_decision_todo_L131_1(), marker_evidence_L10_1_pending_e2258693(), marker_evidence_L24_1_pending_e2258693(), marker_evidence_L97_1_pending_e2258693(), marker_gate_L10_1_retain_the_one_step_scorer_as_a__3715a485(), marker_gate_L125_1_A0_A1_learning_per_horizon_suppo_57e851af(), marker_gate_L131_1_model_selection_protocol_freeze_b8234a7e(), marker_gate_L24_1_explicit_horizon_query_DTO_dynam_bbb4d931() (+13 more)

### Community 71 - "Community 71"
Cohesion: 0.09
Nodes (21): AriaNBVExperimentConfig, Any, Path, Trainer, Return `out_dir` resolved under the configured repository run root., Default path for saving the experiment TOML., Resolve ckpt_path using PathConfig when provided., Save this config (and nested configs) as TOML.          Args:             path: (+13 more)

### Community 72 - "Community 72"
Cohesion: 0.08
Nodes (30): LearnableFourierFeaturesConfig, Learnable Fourier feature encoders for VIN continuous inputs.  This module provi, Config-as-factory wrapper for `LearnableFourierFeatures`., Encoder modules for VIN candidate, trajectory, and coordinate features.  The pac, PoseEncoder, Pose encoder modules for VIN candidate views.  This module owns the active candi, Base interface for encoders of poses already in a reference frame., Return the final pose-embedding feature width. (+22 more)

### Community 74 - "Community 74"
Cohesion: 0.11
Nodes (42): _bin_numeric_series(), _bootstrap_diff(), _bootstrap_slope(), _bucket_param(), _cliffs_delta(), _coerce_numeric(), _duplicate_configs(), _evidence_overview() (+34 more)

### Community 75 - "Community 75"
Cohesion: 0.07
Nodes (40): build_offline_command(), build_rollouts_command(), main(), offline_main(), plan_main(), plan_rollout_shards_command(), help, min (+32 more)

### Community 76 - "Community 76"
Cohesion: 0.07
Nodes (29): Reusable candidate scoring heads for VIN architectures.  This module owns small,, coral_logits_to_label(), coral_logits_to_prob(), coral_loss(), coral_monotonicity_violation_rate(), coral_random_loss(), CoralLayer, MonotoneBinValues (+21 more)

### Community 77 - "Community 77"
Cohesion: 0.06
Nodes (30): symb_use_L11_1_vin_unknown_04c57f03(), symb_use_L11_2_vin_counts_norm_db03c706(), symb_use_L12_1_vin_new_surface_prior_7a7ae61a(), symb_use_L12_2_vin_unknown_04c57f03(), symb_use_L12_3_vin_occ_pr_588d0116(), symb_use_L15_1_vin_loss_3f04e1e5(), symb_use_L15_2_vin_loss_3f04e1e5(), symb_use_L15_3_vin_loss_3f04e1e5() (+22 more)

### Community 78 - "Community 78"
Cohesion: 0.06
Nodes (24): Immutable VIN offline dataset source configuration., Configuration for the immutable VIN offline dataset source., Return the factory target for `BaseConfig.setup_target`., Instantiate the immutable offline VIN dataset for the requested split., Return whether this source yields a map-style dataset., VinOfflineSourceConfig, Self, Compose and execute reproducible Lightning VIN experiments.  This module provide (+16 more)

### Community 79 - "Community 79"
Cohesion: 0.10
Nodes (36): _decode_dataclass(), _decode_dict_key(), _decode_legacy_perspective_cameras(), _decode_value(), from_serializable(), _move_tensor(), _normalize_payload_dict(), _normalize_payload_value() (+28 more)

### Community 80 - "Community 80"
Cohesion: 0.08
Nodes (26): PoseEncodingOutput, PoseTW, Tensor, R6dLffPoseEncoder, R6dLffPoseEncoderConfig, Encode poses in the reference rig frame.          Args:             pose_rig: ``, Configure reference-frame R6D plus LFF pose encoding., Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`. (+18 more)

### Community 82 - "Community 82"
Cohesion: 0.05
Nodes (14): symb_use_L284_2_shape_Vvox_aec1e8cd(), symb_use_L295_2_shape_Fin_0e002e57(), symb_use_L297_2_shape_Fhead_163a8a9a(), symb_use_L298_2_shape_Fhead_163a8a9a(), symb_use_L317_2_shape_Tlen_2e8359f4(), symb_use_L361_2_shape_Vvox_aec1e8cd(), symb_use_L383_2_shape_Fin_0e002e57(), symb_use_L384_2_shape_Fhead_163a8a9a() (+6 more)

### Community 83 - "Community 83"
Cohesion: 0.10
Nodes (38): _print_samples(), _print_summary(), info_command(), _preflight_payload(), _print_stats(), _print_text_summary(), Any, help (+30 more)

### Community 84 - "Community 84"
Cohesion: 0.07
Nodes (24): _iter_stage_batches(), Runtime objects needed for one VIN diagnostics pass., Build checkpoint-backed VIN diagnostics runtime objects.      Args:         cfg:, setup_vin_diagnostics_runtime(), VinDiagnosticsRuntime, Protocol, Shared interface for datasets that yield `VinOracleBatch`., Iterate over VIN oracle batches. (+16 more)

### Community 85 - "Community 85"
Cohesion: 0.07
Nodes (25): Self, Configure one-step ordinal candidate scoring and optimization.      The config c, Return the :class:`VinLightningModule` factory target., VinLightningModuleConfig, AdamWConfig, OneCycleSchedulerConfig, Any, Tensor (+17 more)

### Community 86 - "Community 86"
Cohesion: 0.10
Nodes (22): _build_q_h_arrays(), _encoded_values(), _max_candidates_per_step(), dtype, ndarray, Path, _q_h_arrays_differ(), _q_h_arrays_for_validation() (+14 more)

### Community 87 - "Community 87"
Cohesion: 0.07
Nodes (31): build_projection_grid(), encode_projection_summary(), project_points_to_candidate_cameras(), Any, device, dtype, PerspectiveCameras, Tensor (+23 more)

### Community 88 - "Community 88"
Cohesion: 0.07
Nodes (27): Tensor, Instantiate the configured scoring head.          Args:             in_dim: Opti, Predict ordinal RRI logits from per-candidate feature vectors.      `VinScorerHe, Build the MLP and CORAL threshold layer.          Args:             config: Conf, Return CORAL threshold logits for candidate features.          Args:, Configure the shared VIN ordinal scoring head., Factory target for `BaseConfig.setup_target`., VinScorerHead (+19 more)

### Community 90 - "Community 90"
Cohesion: 0.05
Nodes (36): eqs_metrics_closest_point_witness(), eqs_metrics_directed_reconstruction_errors(), eqs_metrics_point_to_reference_distance(), eqs_metrics_threshold_reconstruction_diagnostics(), symb_use_L20_2_oracle_tolerance_36f2ebf6(), symb_use_L24_2_oracle_tolerance_36f2ebf6(), eqs_use_L159_1_metrics_closest_point_witness_516f9048(), eqs_use_L159_2_metrics_closest_point_witness_516f9048() (+28 more)

### Community 91 - "Community 91"
Cohesion: 0.06
Nodes (15): term_next_best_view(), term_relative_reconstruction_improvement(), term_use_L45_1_next_best_view_99059264(), term_use_L45_2_relative_reconstruction_improvem_f9d7e62d(), term_use_L48_1_relative_reconstruction_improvem_f9d7e62d(), term_use_L23_1_relative_reconstruction_improvem_0f3919f5(), term_use_L3_3_relative_reconstruction_improvem_f9d7e62d(), term_use_L119_1_relative_reconstruction_improvem_0f3919f5() (+7 more)

### Community 92 - "Community 92"
Cohesion: 0.09
Nodes (19): _default_root(), PathConfig, Path, ValidationInfo, Resolve metadata cache path but don't create it yet., Resolve a checkpoint path relative to the checkpoints directory.          Args:, Resolve and validate a checkpoint under `external_checkpoints`.          Absolut, Resolve path to GT mesh for a scene.          Args:             scene_id: Scene (+11 more)

### Community 93 - "Community 93"
Cohesion: 0.10
Nodes (33): Return a summary-focused repr for the snippet view., Return a green `ok` or red `failed` Rich text token., status_text(), build_nested(), capture_tree(), _extract_tensor(), _format_tensor_summary(), _is_tensor_summary() (+25 more)

### Community 95 - "Community 95"
Cohesion: 0.06
Nodes (25): symb_use_L1058_1_rl_qh_3a1a25cb(), symb_use_L1186_1_rl_qh_3a1a25cb(), symb_use_L395_1_rl_qh_3a1a25cb(), symb_use_L395_2_rl_qh_3a1a25cb(), symb_use_L498_1_rl_qh_3a1a25cb(), symb_use_L112_1_rl_qh_3a1a25cb(), symb_use_L112_2_rl_qh_3a1a25cb(), symb_use_L42_1_rl_qh_3a1a25cb() (+17 more)

### Community 97 - "Community 97"
Cohesion: 0.07
Nodes (25): explicit_hidden_world_view_paths(), hidden_world_view_paths(), log_default_inspector_blueprint(), normalize_blueprint_entity_path(), Compose optional Rerun viewer layouts for offline and rollout inspection.  This, Return the default world-view query rules for Rerun blueprints., Return rooted world-view entity paths hidden by default but still included., Return only caller-selected rooted entity paths hidden by a layer policy. (+17 more)

### Community 98 - "Community 98"
Cohesion: 0.12
Nodes (33): BenchmarkRecord, BenchmarkSummary, build_latency_figure(), build_scaling_figure(), build_speedup_figure(), build_throughput_figure(), compute_speedups(), _display_implementation_name() (+25 more)

### Community 99 - "Community 99"
Cohesion: 0.10
Nodes (34): build_geometry_overview_figure(), Plot grid bounds, reference/voxel axes, and candidate centers in one figure., _as_pose_batch(), _as_pose_tw(), _broadcast_pose_batch(), _candidate_valid_fraction(), _centers_rig_from_poses(), _pose_first_batch() (+26 more)

### Community 102 - "Community 102"
Cohesion: 0.08
Nodes (21): Self, Build a block descriptor for one Zarr-backed numeric array.          Args:, Build a block descriptor for indexed per-row MessagePack records.          Args:, Descriptor for one stored block inside a shard.      Attributes:         name: L, Return the hierarchical Zarr path for a logical block name.          Args:, Return the msgpack filename used for one logical record block.          Args:, Return the offsets filename used for indexed record blocks.          Args:, VinOfflineBlockSpec (+13 more)

### Community 103 - "Community 103"
Cohesion: 0.16
Nodes (29): _add_known_artifacts(), _add_rollout_payload_nodes(), _add_rollout_store(), _add_selected_meshes(), _add_selected_shard(), _add_vin_block_nodes(), _add_vin_index_nodes(), _add_vin_source_roots() (+21 more)

### Community 104 - "Community 104"
Cohesion: 0.08
Nodes (23): eqs_scene_actor_state_read(), eqs_use_L37_1_scene_actor_state_read_85d318da(), marker_evidence_L11_1_pending_e2258693(), marker_evidence_L27_1_pending_e2258693(), marker_evidence_L79_1_pending_e2258693(), marker_evidence_L93_1_pending_e2258693(), marker_gate_L11_1_retain_actor_oracle_provenance_c_c376139d(), marker_gate_L27_1_selected_observation_reader_dete_fa2da352() (+15 more)

### Community 105 - "Community 105"
Cohesion: 0.08
Nodes (20): Any, device, dtype, ndarray, Tensor, Trimesh, Move the camera view tensors to the requested device and dtype., Return ``Tensor["F 2", float32]`` horizontal/vertical FOV in degrees. (+12 more)

### Community 106 - "Community 106"
Cohesion: 0.09
Nodes (27): marker_archive_note_L6_1(), marker_decision_todo_L40_1(), marker_evidence_L15_1_pending_e2258693(), marker_gate_L15_1_validated_stores_with_matched_ma_276075a7(), marker_gate_L24_1_held_out_target_matching_and_myo_19a1b9a7(), marker_gate_L32_1_positive_uncertainty_qualified_h_f93986e3(), marker_gate_L40_1_confirmatory_bundle_freeze_6291eda3(), marker_gate_L54_1_validated_campaign_and_confirmat_c9ea4499() (+19 more)

### Community 107 - "Community 107"
Cohesion: 0.08
Nodes (24): build_vin_diagnostics_config(), Build an experiment config for one VIN diagnostics run.      Args:         toml_, _default_source(), IterableDataset, Online Oracle-label dataset source for VIN training.  This module provides an it, Configuration for online oracle VIN datasets., Return the factory target for `BaseConfig.setup_target`., Instantiate the online VIN dataset for the requested split. (+16 more)

### Community 108 - "Community 108"
Cohesion: 0.11
Nodes (27): compress_point_features(), Tensor, Descriptor compression helpers for point-feature banks.  This module provides ex, Apply an explicit descriptor compression transform.      Args:         features:, Return a human-readable label for raw, sliced, or projected descriptors.      Th, resolve_compression_id(), PointFeatureBank, Point-feature bank container with actor-source validation.  The module owns the (+19 more)

### Community 110 - "Community 110"
Cohesion: 0.09
Nodes (29): _normalise(), device, dtype, PoseTW, Tensor, Construct cam2world candidate poses for given centers.          Args:, Build a roll-free rotation matrix for yaw (about +Y) then pitch (about +X)., Build a rotation matrix for roll about +Z (forward). (+21 more)

### Community 112 - "Community 112"
Cohesion: 0.06
Nodes (15): eqs_binning_edges(), eqs_binning_label(), eqs_binning_levels(), eqs_use_L150_1_binning_edges_8f54289a(), eqs_use_L150_2_binning_edges_8f54289a(), eqs_use_L151_1_binning_label_6f29ef54(), eqs_use_L151_2_binning_label_6f29ef54(), eqs_use_L152_1_binning_levels_abdbc9c4() (+7 more)

### Community 116 - "Community 116"
Cohesion: 0.10
Nodes (30): _backbone_rows(), _block_rows(), _component_rows(), _memory_rows(), _pose_rows(), Return sampled per-row sanity summaries as table rows., Return memory diagnostic rows., Return backbone diagnostic rows. (+22 more)

### Community 117 - "Community 117"
Cohesion: 0.07
Nodes (16): OracleCandidateScorer, OracleInvalidity, _PipelineOracleState, PoseTW, Protocol, Tensor, Expected scorer invalidity accepted by the pipeline adapter., Return the stable domain reason code for hard-invalid control flow. (+8 more)

### Community 119 - "Community 119"
Cohesion: 0.18
Nodes (26): _as_tensor(), _candidate_count(), collect_offline_visual_inventory(), _finite_prefix(), _first_length(), _get_required(), _invalid(), _missing() (+18 more)

### Community 120 - "Community 120"
Cohesion: 0.10
Nodes (19): _aggregate_availability(), _aggregate_graph(), DatasetTopology, DatasetTopologyEdge, Return a deterministic JSON-compatible edge row., Immutable aggregate topology and selected-source drill-down projection., Collapse detailed VIN block nodes into one family per role and store., Return complete graph-node rows without heavy payload data. (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.10
Nodes (21): PointNeXtSEncoder, PointNeXtSEncoderConfig, Path, Tensor, Switch training mode while keeping frozen OpenPoints weights in eval mode., Call the most specific feature-forward method exposed by OpenPoints., Encode point clouds into a compact semidense embedding.          Args:, Config-as-factory wrapper for `PointNeXtSEncoder`.      Paths are resolved again (+13 more)

### Community 122 - "Community 122"
Cohesion: 0.13
Nodes (18): Efm3dDepthRenderer, CameraTW, device, ndarray, PoseTW, Tensor, Trimesh, Return the Torch device receiving rendered ``Tensor[\"H W\"]`` maps. (+10 more)

### Community 123 - "Community 123"
Cohesion: 0.13
Nodes (12): Optimizable, Any, Describe a search space over an explicit finite choice set., Sample a value from Optuna.          Args:             trial: Optuna trial (duck, Convert a suggested value to a JSON/W&B friendly representation., Convert a categorical choice into an Optuna-friendly primitive.          Returns, Stable string representation for categorical sequences., Declarative description of an optimisable parameter.      The class intentionall (+4 more)

### Community 128 - "Community 128"
Cohesion: 0.10
Nodes (24): Own one offline-sample selection and Rerun logging session.      :meth:`run` ope, RerunOfflineInspector, Any, Configuration models for the offline Rerun inspector.  The inspector follows the, Metric display sizes for world-frame Rerun geometry primitives., Bound visualization payload size with reproducible subsampling., Filter the stored VIN oracle-candidate prefix for diagnostic display.      Indic, Branch-aware rollout scalar plotting policy. (+16 more)

### Community 129 - "Community 129"
Cohesion: 0.10
Nodes (19): Structural scorer contract for VIN-compatible candidate models.  This module nam, Configuration for `VinModelV3` (streamlined one-step VIN baseline)., VinModelV3Config, MultiStepCandidateScorer, MultiStepCandidateScorerConfig, Scaffold for finite-horizon candidate-value VIN scorers.  This module owns the p, Config-as-factory placeholder for the planned finite-horizon scorer.      Attrib, Factory target for `BaseConfig.setup_target` once implemented. (+11 more)

### Community 133 - "Community 133"
Cohesion: 0.11
Nodes (23): CLIAriaNBVExperimentConfig, CLIWandbAnalysisConfig, _ensure_run_mode(), _extract_config_path(), fit_binner_main(), main(), _merge_with_toml(), optuna_main() (+15 more)

### Community 134 - "Community 134"
Cohesion: 0.09
Nodes (16): FourierFeatures, FourierFeaturesConfig, Tensor, Fixed or directly learnable Fourier features for scalar VIN descriptors.  This m, Sin/cos Fourier features with optional learnable frequencies.      Args:, Return the raw-input plus sine/cosine output width., Apply Fourier feature mapping to inputs.          Args:             x: ``Tensor[, Config-as-factory wrapper for `FourierFeatures`.      The emitted module has no (+8 more)

### Community 135 - "Community 135"
Cohesion: 0.10
Nodes (10): marker_evidence_L35_1_pending_e2258693(), marker_evidence_L8_1_pending_e2258693(), marker_gate_L35_1_typed_selected_observation_reade_0cfbd22c(), marker_gate_L8_1_preserve_deterministic_shell_ide_39033443(), marker_implementation_L35_1_planned_80e61027(), marker_implementation_L8_1_implemented_07f151f1(), marker_source_L35_1_docs_contents_theory_efm3d_scene_7648bc00(), marker_source_L8_1_aria_nbv_aria_nbv_rollouts_repla_4b68d23b() (+2 more)

### Community 136 - "Community 136"
Cohesion: 0.09
Nodes (6): marker_evidence_L54_1_pending_e2258693(), marker_gate_L54_1_explicit_horizon_query_reader_de_80154dfd(), marker_implementation_L54_1_partial_355705cf(), marker_source_L54_1_aria_nbv_aria_nbv_data_handling__bf9c06e0(), marker_thesis_status_L54_1(), symb_use_L46_1_rl_qh_3a1a25cb()

### Community 139 - "Community 139"
Cohesion: 0.16
Nodes (23): Return an ISO-8601 UTC timestamp for metadata payloads., utc_timestamp(), _default_chunks(), _q_h_chunks(), Write selected-action depth rasters and row metadata., Write oracle/eval-only target crop point payloads and row metadata., Write the derived dense finite-candidate training view., Materialize the configured rollout traces to disk. (+15 more)

### Community 140 - "Community 140"
Cohesion: 0.11
Nodes (18): EvlBackbone, EvlBackboneConfig, filter_backbone_output_for_features_mode(), _normalize_evl_model_config_paths(), Any, Path, ValidationInfo, Patch EFM Hydra config paths that are checkout-local assets. (+10 more)

### Community 144 - "Community 144"
Cohesion: 0.08
Nodes (10): eqs_coral_loss(), eqs_coral_rel_random(), eqs_use_L153_1_coral_loss_89ab7495(), eqs_use_L153_2_coral_loss_89ab7495(), eqs_use_L154_1_coral_rel_random_3b95dbbb(), eqs_use_L154_2_coral_rel_random_3b95dbbb(), eqs_use_L229_1_coral_loss_89ab7495(), eqs_use_L229_2_coral_loss_89ab7495() (+2 more)

### Community 146 - "Community 146"
Cohesion: 0.13
Nodes (12): Any, Emit an informational message when verbosity is enabled., Log a structured summary built from `summarize`., Emit a warning message and include a short caller stack., Emit an error message and show the relevant caller stack., Pretty-print an object using the best available formatter., Emit a debug message when debug mode is enabled., Emit a compact tensor-aware summary when debug logging is enabled. (+4 more)

### Community 150 - "Community 150"
Cohesion: 0.09
Nodes (23): symb_use_L287_4_shape_H_3cbf26bf(), symb_use_L289_4_shape_H_3cbf26bf(), symb_use_L291_4_shape_H_3cbf26bf(), symb_use_L292_3_shape_H_3cbf26bf(), symb_use_L295_4_shape_H_3cbf26bf(), symb_use_L297_4_shape_H_3cbf26bf(), symb_use_L298_4_shape_H_3cbf26bf(), symb_use_L301_4_shape_H_3cbf26bf() (+15 more)

### Community 151 - "Community 151"
Cohesion: 0.09
Nodes (23): symb_use_L287_5_shape_Wdim_31658973(), symb_use_L289_5_shape_Wdim_31658973(), symb_use_L291_5_shape_Wdim_31658973(), symb_use_L292_4_shape_Wdim_31658973(), symb_use_L295_5_shape_Wdim_31658973(), symb_use_L297_5_shape_Wdim_31658973(), symb_use_L298_5_shape_Wdim_31658973(), symb_use_L301_5_shape_Wdim_31658973() (+15 more)

### Community 152 - "Community 152"
Cohesion: 0.12
Nodes (18): NbvStreamlitAppConfig, Compose the actor input source and oracle diagnostics pipeline., Return the lazily imported Streamlit application type., __getattr__(), Any, Grouped Streamlit inspection application with lazy page imports.  The package ex, Lazily import Streamlit-heavy modules.      This keeps configuration and non-UI, _build_streamlit_argv() (+10 more)

### Community 153 - "Community 153"
Cohesion: 0.09
Nodes (13): Any, device, PoseTW, Tensor, Target center in world coordinates, shape ``(3,)``., Store a copy of the cumulative validity mask for diagnostics., Apply a rejection mask (True = reject) to the current validity mask., Attach debug tensors in a consistent shape (clone kept to avoid side-effects). (+5 more)

### Community 158 - "Community 158"
Cohesion: 0.13
Nodes (15): CameraTW, PerspectiveCameras, PoseTW, Self, Rendering-focused extensions on top of `CandidatePlotBuilder`.      This keeps a, Add camera frusta and their image-plane rectangles to the 3D scene., Scatter hit points back-projected from rendered depth maps., Return 4x3 world coords of image-plane corners at distance ``dist``. (+7 more)

### Community 159 - "Community 159"
Cohesion: 0.11
Nodes (21): _apply_overrides(), help, min, Option, Path, StrEnum, Inspect one configured VIN sample or rollout chain in a Rerun session.      CLI, Reject incompatible CLI viewer and SDK-sink combinations. (+13 more)

### Community 160 - "Community 160"
Cohesion: 0.10
Nodes (12): dtype, Tensor, Actor-safe target instruction DTOs., Sanitized target instruction for target-conditioned candidate generation.      T, Target center in world coordinates, metres., Return `center_world` as a 3-vector tensor., Return a stable actor-safe diagnostic id derived from descriptor fields., TargetDescriptor (+4 more)

### Community 163 - "Community 163"
Cohesion: 0.25
Nodes (18): _add_rollout_lineage(), _add_selected_source(), _as_int(), _canonical_sample_key(), _inventory_snapshots(), _matching_samples(), Any, Read-only cross-store topology projections for scientific dataset inspection.  T (+10 more)

### Community 167 - "Community 167"
Cohesion: 0.10
Nodes (17): eqs_action_angle_cap_transform(), eqs_action_capped_direction(), eqs_action_family_directions(), eqs_action_power_spherical_forward(), symb_use_L6_1_rl_candidate_table_49aab94c(), symb_use_L6_2_shape_Nq_407ef9c0(), symb_use_L70_1_shape_Nq_407ef9c0(), symb_use_L8_1_shape_Nq_407ef9c0() (+9 more)

### Community 171 - "Community 171"
Cohesion: 0.15
Nodes (15): marker_decision_todo_L51_1(), marker_evidence_L8_1_pending_e2258693(), marker_gate_L39_1_artifact_backed_Results_bundle_ec5dee59(), marker_gate_L45_1_architecture_validity_report_364a8856(), marker_gate_L51_1_confirmatory_analysis_freeze_43c07335(), marker_gate_L8_1_frozen_held_out_manifest_complet_2b2db9a7(), marker_implementation_L8_1_partial_355705cf(), marker_source_L39_1_thesis_objective_to_evidence_con_44cf5a1f() (+7 more)

### Community 172 - "Community 172"
Cohesion: 0.17
Nodes (17): _crop_mesh(), load_or_process_mesh(), _mesh_cache_lock(), MeshProcessSpec, _processed_mesh_from_cache(), ProcessedMesh, Path, Tensor (+9 more)

### Community 173 - "Community 173"
Cohesion: 0.18
Nodes (11): PositionSampler, PoseTW, Tensor, Fallback: sample unit vectors via normalized Gaussian noise., Return normalized actor-visible target bearing in the reference frame., Blend a base direction with orthogonal noise in the reference frame., Map raw angular samples to the configured position family., Draw candidate centers and offsets in reference frame.          Args: (+3 more)

### Community 174 - "Community 174"
Cohesion: 0.18
Nodes (15): FeaturePoolingResult, Point-feature pooling result container for logged multiview evidence.  This modu, Weighted point descriptors pooled over logged observations., Feature-bank containers and pooling helpers for VIN readers.  This package owns, PointQueryPool, Masked query-pooling result container for unordered point selections.  The modul, Permutation-invariant descriptor statistics for a masked point query., _broadcast_point_weights() (+7 more)

### Community 179 - "Community 179"
Cohesion: 0.15
Nodes (17): _camera_tw_from_p3d(), _frustum_builder_stub(), _FrustumSnippetStub, _FrustumTrajectoryStub, _pose_from_p3d_camera(), CameraTW, PerspectiveCameras, PoseTW (+9 more)

### Community 184 - "Community 184"
Cohesion: 0.16
Nodes (10): marker_evidence_L37_1_pending_e2258693(), marker_evidence_L9_1_pending_e2258693(), marker_gate_L37_1_promote_a_level_only_after_lower_83e50a10(), marker_gate_L9_1_end_to_end_permutation_mask_dupl_f9c4e3e0(), marker_implementation_L37_1_partial_355705cf(), marker_implementation_L9_1_partial_355705cf(), marker_source_L37_1_aria_nbv_aria_nbv_vin_models_tar_8454cb95(), marker_source_L9_1_aria_nbv_aria_nbv_vin_models_tar_43cd0c7b() (+2 more)

### Community 185 - "Community 185"
Cohesion: 0.16
Nodes (16): Return candidate centers relative to each rollout root in Z-up metres.      The, root_relative_candidate_rows(), Typed, presentation-free projections over persisted rollout stores., One selected-depth lookup outcome without display-specific processing., Resolve one rollout by physical row position., Resolve one rollout by its stable row id., Read all persisted target rows with decoded factual fields., Return one target by stable row id, or None when absent. (+8 more)

### Community 194 - "Community 194"
Cohesion: 0.12
Nodes (7): symb_use_L5_1_vin_global_933fb530(), symb_use_L6_1_vin_gamma_2420325f(), symb_use_L6_2_vin_global_933fb530(), symb_use_L6_3_vin_beta_89b4918a(), symb_vin_beta(), symb_vin_gamma(), symb_vin_global_()

### Community 195 - "Community 195"
Cohesion: 0.12
Nodes (13): symb_use_L106_1_ase_mesh_target_8765011e(), symb_use_L57_3_ase_mesh_target_8765011e(), symb_use_L59_4_ase_mesh_target_8765011e(), symb_use_L62_3_ase_mesh_target_8765011e(), symb_use_L249_10_ase_mesh_target_8765011e(), symb_use_L249_3_ase_mesh_target_8765011e(), symb_use_L249_7_ase_mesh_target_8765011e(), symb_use_L18_1_ase_mesh_target_8765011e() (+5 more)

### Community 196 - "Community 196"
Cohesion: 0.18
Nodes (13): r"""Compute candidate-aligned oracle RRI labels in one forward pass.          Ar, chamfer_point_mesh(), chamfer_point_mesh_batched(), DistanceBreakdown, Tensor, r"""Low-level squared point--mesh distance primitives for oracle RRI.  This modu, Directional point-mesh distances produced by the Chamfer primitive., r"""Compute directional mean-squared distances for one point cloud and mesh. (+5 more)

### Community 202 - "Community 202"
Cohesion: 0.12
Nodes (9): symb_use_L278_1_frame_v_4c1d368c(), symb_use_L279_2_frame_w_b7d6a863(), symb_use_L279_3_frame_v_4c1d368c(), symb_use_L358_1_frame_v_4c1d368c(), symb_use_L359_2_frame_w_b7d6a863(), symb_use_L359_3_frame_v_4c1d368c(), symb_frame_v(), symb_frame_w() (+1 more)

### Community 203 - "Community 203"
Cohesion: 0.15
Nodes (6): marker_archive_note_L252_1(), marker_archive_note_L43_1(), marker_archive_note_L5_1(), marker_source_L252_1_OMX_successor_registry_and_trans_f82bd68f(), marker_source_L43_1_transcript_evidence_boundary_8b6f4de3(), marker_source_L5_1_deduplicated_ARIA_user_records_p_9420e8ed()

### Community 204 - "Community 204"
Cohesion: 0.19
Nodes (14): build_vin_snippet_view(), collapse_vin_points(), empty_vin_snippet(), pad_vin_points(), Any, device, Tensor, Canonical helpers for adapting raw EFM snippets into VIN snippet views.  This mo (+6 more)

### Community 205 - "Community 205"
Cohesion: 0.14
Nodes (11): Return the registered scorer through the structural VIN protocol.          `self, CandidateScorer, CandidateScorerPrediction, Any, Protocol, Tensor, Protocol for trainable candidate scorers consumed by VIN Lightning.      Impleme, Initialize scorer-owned CORAL bin representatives. (+3 more)

### Community 217 - "Community 217"
Cohesion: 0.19
Nodes (9): marker_evidence_L55_1_pending_e2258693(), marker_gate_L55_1_implement_feasibility_head_and_e_967d50d5(), marker_gate_L67_1_feasibility_calibration_and_poli_645aac8b(), marker_implementation_L55_1_planned_80e61027(), marker_research_todo_L67_1(), marker_source_L55_1_aria_nbv_aria_nbv_rollouts_zarr__4b89521c(), marker_source_L67_1_invalid_row_supervision_hypothes_bbdd13aa(), marker_thesis_status_L55_1() (+1 more)

### Community 218 - "Community 218"
Cohesion: 0.19
Nodes (9): device, dtype, Tensor, Return the unpadded point cloud for one compact candidate row., Drop non-selected render evidence while preserving configured audits., Normalize candidate evidence and verify compact-row alignment., Return a normalized scorer result aligned with `candidates`., Normalize tensors and verify compact rows against the candidate table. (+1 more)

### Community 219 - "Community 219"
Cohesion: 0.18
Nodes (9): _pose_at(), _pose_row(), PoseTW, Tensor, Return the selected valid pose in world coordinates., Return the root pose or final selected pose., Return root and selected poses in trajectory order.          Returns:, Return camera centres as ``Tensor["T 3", float32]`` in world metres. (+1 more)

### Community 233 - "Community 233"
Cohesion: 0.17
Nodes (10): CustomRichProgressBar, CustomTQDMProgressBar, Callback, Build callbacks and adapt trial-specific ownership flags.          Args:, Custom TQDM progress bar that hides the version number (v_num)., Return Lightning progress metrics without the logger version field., Custom Rich progress bar that hides the version number (v_num)., Return Rich progress metrics without the logger version field. (+2 more)

### Community 234 - "Community 234"
Cohesion: 0.23
Nodes (11): _as_candidate_matrix(), candidate_order_consistency(), candidate_provenance_share(), _candidate_valid_matrix(), _id_membership(), _masked_argmax(), Tensor, Compare candidate scores before and after a candidate-order shuffle.      Args: (+3 more)

### Community 235 - "Community 235"
Cohesion: 0.27
Nodes (12): finite_1d(), ordinal_ranks(), pearson_corr(), Tensor, quantile_stats(), Small tensor statistics used by VIN diagnostic summaries.  The helpers in this m, Return finite values from ``values`` as a detached float32 vector.      Paramete, Compute a finite-value Pearson correlation for diagnostic reporting.      ``x`` (+4 more)

### Community 240 - "Community 240"
Cohesion: 0.14
Nodes (13): symb_use_L101_1_rl_s_oracle_cd7bc4a5(), symb_use_L51_1_rl_s_hist_9b9feb11(), symb_use_L105_1_rl_s_hist_9b9feb11(), symb_use_L105_2_rl_s_hist_9b9feb11(), symb_use_L109_1_rl_s_oracle_cd7bc4a5(), symb_use_L109_2_rl_s_oracle_cd7bc4a5(), symb_use_L35_1_rl_s_hist_9b9feb11(), symb_use_L35_2_rl_s_hist_9b9feb11() (+5 more)

### Community 242 - "Community 242"
Cohesion: 0.26
Nodes (11): _axis_stats(), project_horizontal(), Tensor, Frame-preserving pose and directional statistics for candidate generation.  Help, Project vectors `v` onto the horizontal plane defined by world up `wup`., Summarize radii and angles for LUF offsets ``Tensor[\"N 3\"]`` in metres., Summarize azimuth/elevation of LUF directions ``Tensor[\"N 3\"]``., Return rejected candidate poses as a tensor (or None if none rejected). (+3 more)

### Community 243 - "Community 243"
Cohesion: 0.21
Nodes (11): _as_path_matrix(), candidate_best_value(), candidate_masked_mean(), CandidateOrderConsistency, _finite_mask(), Operational validity, provenance, path, and policy audits for rollouts.  This mo, Per-table diagnostics for shuffled-candidate consistency.      Attributes:, Reduce candidate-table values with a hard validity mask.      Args:         valu (+3 more)

### Community 244 - "Community 244"
Cohesion: 0.17
Nodes (7): LearnableFourierFeatures, Tensor, Learnable Fourier Features (LFF) positional encoding.      This module maps cont, Return the emitted feature dimension, including raw inputs when enabled., Encode vectors with learned sinusoidal features.          Args:             x: `, Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`., Return the LFF sub-encoder when present (else ``None``).          Useful for dia

### Community 245 - "Community 245"
Cohesion: 0.20
Nodes (9): encode_shell_pose_descriptor(), PoseTW, Shared shell-pose descriptors for VIN candidate encoders.  The shell encoders de, Canonical shell descriptor for a candidate pose.      Attributes:         center, Build the canonical shell descriptor for poses in a reference frame.      Args:, ShellPoseDescriptor, PoseTW, Encode shell pose descriptors with spherical harmonics. (+1 more)

### Community 253 - "Community 253"
Cohesion: 0.26
Nodes (8): marker_evidence_L14_1_pending_e2258693(), marker_gate_L14_1_a_measured_limitation_that_the_p_1e4c1569(), marker_gate_L27_1_artifact_backed_failure_analysis_6872de0e(), marker_implementation_L14_1_exploratory_5ea84816(), marker_research_todo_L27_1(), marker_source_L14_1_tab_thesis_scene_representation__d24ca9d2(), marker_source_L27_1_method_design_space_registry_rep_a9e8fe15(), marker_thesis_status_L14_1()

### Community 254 - "Community 254"
Cohesion: 0.24
Nodes (8): CameraTW, dtype, PerspectiveCameras, PoseTW, Tensor, Rasterize metric z-depth for world-from-camera candidate poses.          Args:, Return a per-candidate or single-frame ``CameraTW`` entry., Return intrinsics ready for ``PerspectiveCameras``.          Args:             c

### Community 255 - "Community 255"
Cohesion: 0.18
Nodes (8): candidate_primary_invalid_reason_share(), CandidatePrimaryInvalidReasonMetric, CandidatePrimaryInvalidReasonStats, Summarize primary invalid-reason concentration among rejected rows.      Args:, Accumulate primary invalid-reason share among rejected candidates.      The conf, Accumulate one batch of primary invalid-reason ids., Return reason-group share and denominator-validity rate., Per-table primary invalid-reason share among rejected candidate rows.      Rollo

### Community 256 - "Community 256"
Cohesion: 0.22
Nodes (7): CandidateOrderConsistencyMetric, CandidatePathIncrementMetric, CandidateProvenanceShareMetric, MetricBase, Accumulate candidate action path-increment diagnostics in metres.      The metri, Accumulate shuffled-candidate order-consistency diagnostics.      This metric su, Accumulate candidate provenance-family share diagnostics.      The metric report

### Community 266 - "Community 266"
Cohesion: 0.24
Nodes (10): _pair_from_tar_member(), Any, Path, Resolve a manifest path snapshot without mutating global path config., Scan raw tar headers for dataset snippet pairs., Infer ``(scene_id, snippet_id)`` from one WebDataset tar member name., Resolve raw EFM tar paths from a stored dataset config snapshot., _resolve_coverage_tar_paths() (+2 more)

### Community 279 - "Community 279"
Cohesion: 0.22
Nodes (5): Path, Return the resolved path to the store-owned ``manifest.json``., Return the resolved path to the global ``sample_index.jsonl``., Return the absolute shard root directory., Return the absolute split-array directory.

### Community 280 - "Community 280"
Cohesion: 0.25
Nodes (5): CandidateTableMetrics, Accumulate hard-mask candidate-table diagnostics.      The metric reports valid/, Accumulate candidate hard-mask validity without value summaries., Accumulate validity-aware candidate table summaries.          Args:, Return candidate validity and value diagnostics.

### Community 281 - "Community 281"
Cohesion: 0.44
Nodes (8): _candidate_invalid_reasons(), _full_candidate_vector(), _full_shell_bool_extra(), _full_shell_or_default(), _primary_candidate_invalid_reason(), Any, Tensor, Minimal rollout replay inputs shared by the Zarr writer.  `rollouts.zarr` stores

### Community 295 - "Community 295"
Cohesion: 0.25
Nodes (5): Any, device, Return a copy with every present tensor moved to ``device``., Serialize tensors into a cache-friendly CPU payload without changing candidate o, Reconstruct one candidate-aligned result on a requested device.          Args:

### Community 304 - "Community 304"
Cohesion: 0.25
Nodes (8): symb_use_L58_1_rl_target_e7e520ca(), symb_use_L84_1_rl_target_e7e520ca(), symb_use_L117_1_rl_target_e7e520ca(), symb_use_L117_2_rl_target_e7e520ca(), symb_use_L47_1_rl_target_e7e520ca(), symb_use_L47_2_rl_target_e7e520ca(), symb_rl_target(), symb_use_L35_1_rl_target_e7e520ca()

### Community 305 - "Community 305"
Cohesion: 0.25
Nodes (8): symb_use_L21_1_ase_traj_final_806145af(), symb_use_L21_2_ase_traj_final_806145af(), symb_use_L91_1_ase_traj_final_806145af(), symb_use_L91_2_ase_traj_final_806145af(), symb_use_L278_2_ase_traj_final_806145af(), symb_use_L358_2_ase_traj_final_806145af(), symb_ase_traj_final(), symb_use_L70_1_ase_traj_final_806145af()

### Community 308 - "Community 308"
Cohesion: 0.29
Nodes (6): __dir__(), __getattr__(), Any, Lazy public facade for Streamlit panel renderers.  Importing this package does n, Import and return one panel renderer when first requested., Return package globals plus lazy renderer exports.

### Community 309 - "Community 309"
Cohesion: 0.33
Nodes (7): _broadcast_ref_pose(), _normalise(), Tensor, Return unit vectors with stable zero handling., Broadcast one reference pose to candidate-pose leading dimensions., Compute roll angle around the camera forward vector., _roll_about_forward()

### Community 310 - "Community 310"
Cohesion: 0.33
Nodes (6): CandidateScorerBatchInputs, prepare_candidate_scorer_batch_inputs(), device, Batch input normalization for VIN-compatible Lightning scorers.  :class:`aria_nb, Device-normalized inputs for a candidate scorer forward pass.      Attributes:, Prepare actor-visible scorer inputs from one oracle-labelled batch.      Args:

### Community 311 - "Community 311"
Cohesion: 0.29
Nodes (4): Return finite means of candidate path-increment table statistics., Return shuffled-candidate consistency diagnostics., Return finite mean family share or ``NaN`` when no tables were valid., _safe_mean()

### Community 312 - "Community 312"
Cohesion: 0.29
Nodes (4): CandidatePolicyEntropyMetric, Accumulate masked candidate-policy entropy diagnostics.      The metric summariz, Accumulate one batch of candidate selection probabilities., Return mean entropy or ``NaN`` when no table had positive mass.

### Community 319 - "Community 319"
Cohesion: 0.29
Nodes (7): symb_use_L83_1_rl_invalid_reason_3b6dd7dc(), symb_use_L116_1_rl_invalid_reason_3b6dd7dc(), symb_use_L116_2_rl_invalid_reason_3b6dd7dc(), symb_use_L46_1_rl_invalid_reason_3b6dd7dc(), symb_use_L46_2_rl_invalid_reason_3b6dd7dc(), symb_rl_invalid_reason(), symb_use_L47_4_rl_invalid_reason_3b6dd7dc()

### Community 320 - "Community 320"
Cohesion: 0.48
Nodes (5): marker_evidence_L3_1_pending_e2258693(), marker_gate_L3_1_implementation_and_held_out_eval_073c96c3(), marker_implementation_L3_1_planned_80e61027(), marker_source_L3_1_development_only_source_typ_10_7debcf98(), marker_thesis_status_L3_1()

### Community 321 - "Community 321"
Cohesion: 0.33
Nodes (4): Any, Return Lightning's W&B logger class for config-factory inspection., Instantiate a logger rooted in :class:`PathConfig`'s W&B directory., WandbLogger

### Community 322 - "Community 322"
Cohesion: 0.33
Nodes (5): candidate_path_increment_stats(), CandidatePathIncrementStats, Summarize per-candidate path increments under the hard action mask.      Args:, Per-table movement-cost diagnostics for candidate action rows.      The rollout, Accumulate one batch of candidate path-increment tables.

### Community 323 - "Community 323"
Cohesion: 0.33
Nodes (4): Accumulate selected camera-center path cost in metres.      The metric expects r, Accumulate one batch of selected rollout paths.          Args:             camer, Return mean acquisition cost aliases for policy tables., SelectedPathCostMetrics

### Community 331 - "Community 331"
Cohesion: 0.33
Nodes (6): symb_use_L65_1_rl_s_off_0c0be6b0(), symb_use_L106_1_rl_s_off_0c0be6b0(), symb_use_L106_2_rl_s_off_0c0be6b0(), symb_use_L36_1_rl_s_off_0c0be6b0(), symb_use_L36_2_rl_s_off_0c0be6b0(), symb_rl_s_off()

### Community 332 - "Community 332"
Cohesion: 0.33
Nodes (6): symb_use_L8_1_rl_mdp_nbv_2177a1a7(), symb_use_L102_1_rl_mdp_nbv_2177a1a7(), symb_use_L102_2_rl_mdp_nbv_2177a1a7(), symb_use_L32_1_rl_mdp_nbv_2177a1a7(), symb_use_L32_2_rl_mdp_nbv_2177a1a7(), symb_rl_mdp_nbv()

### Community 347 - "Community 347"
Cohesion: 0.40
Nodes (5): symb_use_L310_2_shape_M_385beb7e(), symb_use_L312_2_shape_M_385beb7e(), symb_use_L411_2_shape_M_385beb7e(), symb_use_L412_2_shape_M_385beb7e(), symb_shape_M()

### Community 349 - "Community 349"
Cohesion: 0.50
Nodes (3): Render persisted multi-step rollout supervision., Render the science-first stored-dataset inspection workflow., render_stored_rollouts_panel()

### Community 351 - "Community 351"
Cohesion: 0.50
Nodes (4): main(), _normalize_default_summary(), Run VIN offline-store inspection.      Args:         argv: Optional argument vec, Preserve the legacy default ``summary`` command.

## Knowledge Gaps
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PathConfig` connect `Community 92` to `Community 3`, `Community 388`, `Community 5`, `Community 6`, `Community 389`, `Community 133`, `Community 8`, `Community 266`, `Community 7`, `Community 140`, `Community 13`, `Community 25`, `Community 27`, `Community 163`, `Community 36`, `Community 35`, `Community 38`, `Community 39`, `Community 41`, `Community 172`, `Community 45`, `Community 49`, `Community 62`, `Community 321`, `Community 74`, `Community 75`, `Community 78`, `Community 350`, `Community 103`, `Community 233`, `Community 107`, `Community 121`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `EfmSnippetView` connect `Community 57` to `Community 1`, `Community 129`, `Community 3`, `Community 4`, `Community 9`, `Community 18`, `Community 19`, `Community 21`, `Community 22`, `Community 33`, `Community 34`, `Community 36`, `Community 37`, `Community 40`, `Community 41`, `Community 42`, `Community 46`, `Community 47`, `Community 310`, `Community 58`, `Community 67`, `Community 204`, `Community 87`, `Community 93`, `Community 99`, `Community 105`, `Community 107`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `Console` connect `Community 3` to `Community 1`, `Community 4`, `Community 133`, `Community 9`, `Community 18`, `Community 19`, `Community 146`, `Community 21`, `Community 27`, `Community 35`, `Community 36`, `Community 37`, `Community 38`, `Community 41`, `Community 43`, `Community 172`, `Community 47`, `Community 57`, `Community 71`, `Community 78`, `Community 83`, `Community 93`, `Community 107`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `EfmSnippetView` (e.g. with `run_vin_diagnostics()` and `AseEfmDataset`) actually correct?**
  _`EfmSnippetView` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `PathConfig` (e.g. with `OptunaConfig` and `WandbConfig`) actually correct?**
  _`PathConfig` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `RolloutZarrStoreReader` (e.g. with `RolloutSuspiciousQueryConfig` and `StoredRollout`) actually correct?**
  _`RolloutZarrStoreReader` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Console` (e.g. with `BaseConfig` and `SingletonConfig`) actually correct?**
  _`Console` has 7 INFERRED edges - model-reasoned connections that need verification._