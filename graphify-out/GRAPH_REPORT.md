# Graph Report - ARIA-NBV

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 11112 nodes · 20214 edges · 490 communities (476 shown, 14 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 1737 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `380f1d2450ceab247612d3e25d6bcb4ae4d6891a`
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
- Community 11
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
- Community 23
- Community 24
- Community 25
- Community 26
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
- Community 45
- Community 47
- Community 48
- Community 50
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 60
- Community 61
- Community 62
- Community 65
- Community 66
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 74
- Community 76
- Community 77
- Community 78
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 89
- Community 91
- Community 92
- Community 94
- Community 95
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 105
- Community 106
- Community 110
- Community 113
- Community 114
- Community 115
- Community 120
- Community 121
- Community 122
- Community 125
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 136
- Community 138
- Community 139
- Community 143
- Community 144
- Community 145
- Community 146
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 155
- Community 161
- Community 162
- Community 163
- Community 164
- Community 167
- Community 173
- Community 174
- Community 175
- Community 180
- Community 185
- Community 186
- Community 187
- Community 196
- Community 197
- Community 203
- Community 204
- Community 205
- Community 206
- Community 207
- Community 219
- Community 220
- Community 221
- Community 222
- Community 223
- Community 237
- Community 238
- Community 239
- Community 240
- Community 246
- Community 247
- Community 248
- Community 249
- Community 257
- Community 258
- Community 259
- Community 260
- Community 261
- Community 271
- Community 272
- Community 273
- Community 286
- Community 287
- Community 288
- Community 289
- Community 290
- Community 304
- Community 305
- Community 306
- Community 317
- Community 318
- Community 319
- Community 320
- Community 327
- Community 328
- Community 329
- Community 330
- Community 331
- Community 339
- Community 340
- Community 341
- Community 342
- Community 343
- Community 358
- Community 360
- Community 361
- Community 362
- Community 399
- Community 400
- Community 401
- Community 402
- Community 403
- Community 404
- Community 405
- Community 406
- Community 407
- Community 457
- Community 458
- Community 459
- Community 460

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
- `symb_use_L9_1_oracle_points_032d9bc0()` --calls--> `symb_oracle_points()`  [INFERRED]
  docs/typst/shared/equations/metrics.typ → docs/typst/shared/symbols/oracle.typ

## Import Cycles
- None detected.

## Communities (490 total, 14 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (137): eqs_action_candidate_shell(), eqs_action_space(), eqs_coral_loss(), eqs_coral_rel_random(), eqs_entity_objective(), eqs_metrics_candidate_validity(), eqs_metrics_spearman(), eqs_metrics_topk_acc() (+129 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (201): symb_use_L209_1_entity_target_desc_f8bba4f4(), symb_use_L6_1_rl_candidate_table_49aab94c(), symb_use_L13_1_entity_target_desc_f8bba4f4(), symb_use_L78_1_rl_action_set_t_3b273a63(), symb_use_L83_1_rl_action_set_t_3b273a63(), symb_use_L22_1_entity_target_desc_f8bba4f4(), symb_use_L101_1_rl_s_oracle_cd7bc4a5(), symb_use_L104_1_rl_s_cf_geom_7c1e8c4f() (+193 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (96): _add_target_overlays(), _add_target_semidense_crop(), Return a compact dataframe payload for target rows., Add descriptor and GT-only target OBB overlays to a rollout plot., Overlay semidense points cropped to the descriptor or GT target OBB., _target_rows_table(), Shared target-selection tables and plots for actor/oracle boundary audits.  The, Return compact Oracle target-task audit rows. (+88 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (107): _policy_name(), Composed source, target, and policy lineage flattened only by the writer., Return persisted lineage identifiers for one retained chain., RolloutLineage, _termination_reason(), _accumulate_selected_metric(), _add_manifest_hash(), _append_selected_depth_row() (+99 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (66): build_vin_diagnostics_config(), Checkpoint setup and no-gradient forward passes for VIN diagnostics.  This modul, Runtime objects needed for one VIN diagnostics pass., Build an experiment config for one VIN diagnostics run.      Args:         toml_, Build checkpoint-backed VIN diagnostics runtime objects.      Args:         cfg:, setup_vin_diagnostics_runtime(), VinDiagnosticsRuntime, Immutable VIN offline dataset source configuration. (+58 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (113): _activate_query_store(), _apply_query_callback(), _apply_query_state(), _cached_evidence_bundle(), _cached_projection(), _cached_store_bundle(), _cached_topology(), _candidate_flow_figure() (+105 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (96): Canonical root sample for diagnostics and rollout generation.      `VinOfflineSa, VinOfflineSample, camera_tw_pinhole_kwargs(), candidate_centers_world(), depth_hw(), deterministic_downsample(), display_rot90_cw(), image_hwc() (+88 more)

### Community 7 - "Community 7"
Cohesion: 0.04
Nodes (72): FourierFeaturesConfig, Fixed or directly learnable Fourier features for scalar VIN descriptors.  This m, Config-as-factory wrapper for `FourierFeatures`.      The emitted module has no, LearnableFourierFeatures, LearnableFourierFeaturesConfig, Learnable Fourier feature encoders for VIN continuous inputs.  This module provi, Learnable Fourier Features (LFF) positional encoding.      This module maps cont, Return the emitted feature dimension, including raw inputs when enabled. (+64 more)

### Community 8 - "Community 8"
Cohesion: 0.03
Nodes (81): AbstractContextManager, NbvStreamlitApp, Lazy page router for the ARIA-NBV Streamlit application.  The application frame, Render the interactive counterfactual-rollout laboratory., Render proposal diagnostics with page-owned single-step controls., Render one observed snippet with page-owned dataset controls., Render candidate depths with page-owned renderer controls., Render the grouped NBV inspection application from one configuration.      Datas (+73 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (74): EvaluatedRollout, EvaluatedRolloutRecord, OracleReplayAdapter, OracleReplayInvalidityError, ValueError, Join replay transitions with pipeline-local Oracle outputs.  This module provide, Join cached Oracle outputs to retained replay chains., Pipeline control flow carrying a typed Oracle invalidity outcome. (+66 more)

### Community 10 - "Community 10"
Cohesion: 0.04
Nodes (83): _apply_manifest_rows(), Path, Select manifest rows in exact configured sample-key order., Filter and order a VIN reader from validated source-row records., Configuration for building standalone target-RRI rollout Zarr stores.      The s, Resolve a configured source manifest relative to the repository root., Normalize an exact ordered sample-key selection and reject ambiguity., Require direct pilot configs to match their reviewed ordered source rows. (+75 more)

### Community 11 - "Community 11"
Cohesion: 0.02
Nodes (38): symb_use_L71_2_ase_mesh_target_8765011e(), symb_use_L106_1_ase_mesh_target_8765011e(), symb_use_L334_1_oracle_err_0cf392a4(), symb_use_L336_1_oracle_err_0cf392a4(), symb_use_L341_1_oracle_err_0cf392a4(), symb_use_L343_1_oracle_err_0cf392a4(), symb_use_L12_1_oracle_err_0cf392a4(), symb_use_L47_1_oracle_err_0cf392a4() (+30 more)

### Community 13 - "Community 13"
Cohesion: 0.03
Nodes (82): symb_use_L10_1_oracle_points_032d9bc0(), symb_use_L11_1_oracle_reference_geometry_c981bbad(), symb_use_L13_1_oracle_reference_geometry_c981bbad(), symb_use_L13_2_oracle_points_032d9bc0(), symb_use_L14_1_oracle_reference_samples_27045dc4(), symb_use_L14_2_oracle_reference_samples_27045dc4(), symb_use_L15_1_oracle_points_032d9bc0(), symb_use_L19_1_oracle_points_032d9bc0() (+74 more)

### Community 14 - "Community 14"
Cohesion: 0.04
Nodes (87): Own one offline-sample selection and Rerun logging session.      :meth:`run` ope, Initialize the inspector runtime., RerunOfflineInspector, Any, Configuration models for the offline Rerun inspector.  The inspector follows the, Metric display sizes for world-frame Rerun geometry primitives., Bound visualization payload size with reproducible subsampling., Filter the stored VIN oracle-candidate prefix for diagnostic display.      Indic (+79 more)

### Community 15 - "Community 15"
Cohesion: 0.03
Nodes (95): symb_use_L10_2_oracle_points_032d9bc0(), symb_use_L105_1_ase_mesh_74889664(), symb_use_L116_1_ase_mesh_74889664(), symb_use_L155_1_oracle_points_032d9bc0(), symb_use_L155_2_oracle_points_032d9bc0(), symb_use_L155_3_oracle_points_032d9bc0(), symb_use_L334_2_oracle_points_032d9bc0(), symb_use_L334_3_ase_mesh_74889664() (+87 more)

### Community 16 - "Community 16"
Cohesion: 0.02
Nodes (68): symb_use_L208_1_ase_mesh_74889664(), symb_use_L211_1_oracle_center_c037f29d(), symb_use_L226_1_oracle_candidates_t_47cd08c5(), symb_use_L227_1_oracle_candidate_qti_34144333(), symb_use_L228_1_rl_validity_mask_8058869f(), symb_use_L234_1_oracle_depth_q_3b0cfae9(), symb_use_L235_1_oracle_mask_q_96e812ad(), symb_use_L107_1_oracle_depth_q_3b0cfae9() (+60 more)

### Community 17 - "Community 17"
Cohesion: 0.05
Nodes (73): Render VIN model diagnostics., Render ordinal RRI binning diagnostics., _info_popover(), Exception, Shared presentation and error-reporting helpers for Streamlit panels.  The modul, Render a full traceback in the UI and emit it to stdout., _report_exception(), _strip_ansi() (+65 more)

### Community 18 - "Community 18"
Cohesion: 0.04
Nodes (91): _aligned_valid_vector(), _array_value(), _build_fanout_band_figure(), _build_live_dataset_config(), _candidate_config_device(), _candidate_config_for_live_rollout(), _counterfactual_trajectory_rows(), _first_available_step_score_metric() (+83 more)

### Community 19 - "Community 19"
Cohesion: 0.05
Nodes (85): _batch_shape_preview(), _collect_block_diagnostics(), collect_vin_offline_dataset_stats(), _component_for_memory_block(), _component_key(), _finite_values(), _has_record_block(), _memory_diagnostics() (+77 more)

### Community 20 - "Community 20"
Cohesion: 0.05
Nodes (83): Render the training-dataset composition hub., _artifact_identity(), _cached_bundle_summary(), _cached_deep_statistics(), _coral_artifact_identity(), _deep_metric_value(), _download_payload(), _format_bytes() (+75 more)

### Community 21 - "Community 21"
Cohesion: 0.04
Nodes (68): Oracle candidate-depth and backprojected-hit diagnostics.  This panel provides m, Render oracle depth maps and optional world-frame depth-hit clouds.      Args:, render_depth_page(), Oracle relative-reconstruction-improvement inspection plots.  The panel provides, Render oracle RRI and mesh-distance diagnostics for rendered candidates.      Ar, render_rri_page(), End-to-end oracle RRI label generation pipeline (non-Streamlit).  This module pr, _canonical_fused_unions() (+60 more)

### Community 22 - "Community 22"
Cohesion: 0.03
Nodes (83): symb_use_L23_1_scene_target_support_pool_626ec9d6(), symb_use_L39_1_scene_frustum_support_pool_a100875f(), symb_use_L40_1_scene_target_frustum_pool_27e828cf(), symb_use_L41_1_scene_ray_query_ti_54319867(), symb_use_L42_1_scene_evl_support_token_e6562f55(), eqs_scene_scene_memory_decomposition(), symb_use_L11_1_scene_scene_memory_t_f39b4ba7(), symb_use_L20_1_scene_evl_support_frac_c08e3bc3() (+75 more)

### Community 23 - "Community 23"
Cohesion: 0.07
Nodes (66): _add_known_artifacts(), _add_rollout_lineage(), _add_rollout_payload_nodes(), _add_rollout_store(), _add_selected_meshes(), _add_selected_shard(), _add_selected_source(), _add_vin_block_nodes() (+58 more)

### Community 24 - "Community 24"
Cohesion: 0.06
Nodes (79): _add_target_context_overlay(), _candidate_provenance_preview(), _color_payload_np(), _full_shell_color_payload(), _motion_threshold_rows(), _pose_orthonormality_stats(), ndarray, PoseTW (+71 more)

### Community 25 - "Community 25"
Cohesion: 0.05
Nodes (62): Build a target-aware mixed candidate generator from per-family counts., _target_mixture_config(), candidate_config_ui(), Sidebar controls that construct typed NBV pipeline configurations.  The helpers, Render finite-candidate controls and return a validated config copy.      Distan, Generate candidates using an `EfmSnippetView` sample.          Args:, candidate_position_id(), candidate_strategy_id() (+54 more)

### Community 26 - "Community 26"
Cohesion: 0.04
Nodes (58): Run one diagnostic VIN forward pass and restore the prior model mode.      Args:, run_vin_diagnostics(), Minimal snippet payload for VIN v2 batching.      Attributes:         points_wor, VinSnippetView, PerspectiveCameras, PoseTW, Structural scorer contract for VIN-compatible candidate models.  This module nam, Score candidate poses for one actor-visible snippet.          Args: (+50 more)

### Community 28 - "Community 28"
Cohesion: 0.05
Nodes (78): _apply_validity_override(), _as_1d_array(), _as_bool_array(), candidate_rgba(), _interpolate_rgb(), obb_semantic_rgba(), oracle_rri_to_rgba(), dtype (+70 more)

### Community 29 - "Community 29"
Cohesion: 0.05
Nodes (56): CandidateViewGenerator, CandidateViewGeneratorConfig, _clone_camera_template(), _gravity_align_pose(), _maybe_seed(), CameraTW, device, PoseTW (+48 more)

### Community 30 - "Community 30"
Cohesion: 0.06
Nodes (75): _cached_inventory(), Project the immutable rollout-store inventory once per cache root., _array_size(), _arrays_equal(), candidate_flow_rows(), candidate_result_diagnostic_counts(), _cohort_id_from_key(), _cohort_ineligibility_reason() (+67 more)

### Community 31 - "Community 31"
Cohesion: 0.05
Nodes (62): _ase_atek_identifier_variants(), compact_ase_atek_identifiers(), compact_ase_atek_sample_id(), Any, Canonical conversions between raw and compact ASE-ATEK identifiers.  These pure, Return the compact public identifier for one ASE-ATEK sample key., Return the raw ATEK key for a compact ASE-ATEK identifier., Recursively compact ASE-ATEK identifiers inside JSON-like objects. (+54 more)

### Community 32 - "Community 32"
Cohesion: 0.06
Nodes (66): _cached_failures(), Cache failure triage for one immutable store and threshold tuple., Return rollout rows included in branch-aware scalar plots., _resolve_plot_rollout_rows(), candidate_audit_rows(), candidate_group_summary_rows(), _dominant_invalid_reason_rows(), _finite_or_none() (+58 more)

### Community 33 - "Community 33"
Cohesion: 0.05
Nodes (39): Configuration management for aria_nbv.  This module provides centralized configu, OptunaConfig, Any, Callback, Optuna study construction and config-tree search-space application.  This module, Send the most recent suggestions to W&B., Return a PyTorch Lightning pruning callback for the configured monitor., Configure an Optuna study used by :class:`aria_nbv.lightning.AriaNBVExperimentCo (+31 more)

### Community 34 - "Community 34"
Cohesion: 0.06
Nodes (42): CompactObbBlock, CompactTrajectoryBlock, Shared VIN oracle batch records, masking, and collation utilities.  This module, Collatable numeric OBB payload used by training and diagnostics.      ``obbs`` k, Preserve MPS/EFM timing and gravity metadata beside VIN trajectory poses., dtype, ndarray, PerspectiveCameras (+34 more)

### Community 35 - "Community 35"
Cohesion: 0.04
Nodes (36): eqs_action_angle_cap_transform(), eqs_action_capped_direction(), eqs_action_family_directions(), eqs_action_power_spherical_forward(), symb_use_L6_2_shape_Nq_407ef9c0(), symb_use_L70_1_shape_Nq_407ef9c0(), symb_use_L8_1_shape_Nq_407ef9c0(), term_egocentric_voxel_lifting() (+28 more)

### Community 36 - "Community 36"
Cohesion: 0.04
Nodes (36): symb_use_L279_1_shape_B_c1b74290(), symb_use_L280_1_shape_B_c1b74290(), symb_use_L282_1_shape_B_c1b74290(), symb_use_L284_1_shape_B_c1b74290(), symb_use_L287_2_shape_B_c1b74290(), symb_use_L289_2_shape_B_c1b74290(), symb_use_L291_2_shape_B_c1b74290(), symb_use_L292_1_shape_B_c1b74290() (+28 more)

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (45): compute_downloaded_atek_stats(), count_snippets_in_tar(), DownloadedAtekStats, _estimate_snippet_count_from_shards(), _iter_downloaded_shard_tars(), Path, Helpers for reporting local download coverage and snippet counts for ATEK shards, Summary of available vs downloaded ATEK data for a given config. (+37 more)

### Community 38 - "Community 38"
Cohesion: 0.06
Nodes (61): VIN pose-vector and learnable Fourier feature diagnostics.  The tab provides inp, Render the FF Encodings tab.      Args:         ctx: Shared VIN diagnostics cont, render_encodings_tab(), _camera_tw_from_p3d(), _frustum_builder_stub(), _FrustumSnippetStub, _FrustumTrajectoryStub, _pose_from_p3d_camera() (+53 more)

### Community 39 - "Community 39"
Cohesion: 0.04
Nodes (54): symb_use_L106_1_entity_q_recovery_238f4ed4(), symb_use_L10_1_entity_lambda_scene_bb771858(), symb_use_L10_2_oracle_rri_8cfa0f49(), symb_use_L69_1_entity_target_error_3b780437(), symb_use_L73_1_entity_target_error_pm_edc6b8bb(), symb_use_L75_1_entity_target_error_mp_a17da45c(), symb_use_L7_1_entity_E_b6f60f19(), symb_use_L80_1_entity_target_error_3b780437() (+46 more)

### Community 40 - "Community 40"
Cohesion: 0.04
Nodes (55): symb_use_L14_2_spatial_relation_rpe_502d7799(), symb_use_L31_1_spatial_candidate_pose_feat_f8ec6778(), symb_use_L32_1_spatial_candidate_target_rel_fea_db3e373e(), symb_use_L38_1_spatial_dir_moment_7b0efd97(), eqs_spatial_direction_memory_moment(), eqs_spatial_direction_unit(), symb_use_L10_1_spatial_dir_memory_5053b99d(), symb_use_L13_1_spatial_sh_basis_15cf78fe() (+47 more)

### Community 41 - "Community 41"
Cohesion: 0.05
Nodes (57): build_frustum_points_world_p3d(), frustum_points_world_from_cameras(), PerspectiveCameras, PoseTW, Tensor, Frustum point sampling helpers for VIN geometry diagnostics.  The legacy experim, Unproject a square image grid at fixed depths into world points.      Args:, Generate per-candidate frustum sample points in world coordinates.      Args: (+49 more)

### Community 42 - "Community 42"
Cohesion: 0.07
Nodes (57): _pretty_label(), Small deterministic statistics helpers for app, plots, and exports.  The functio, Format labels by replacing underscores and title-casing words., build_alignment_figures(), build_candidate_encoding_figures(), build_field_token_histograms(), build_frustum_samples_figure(), build_lff_response_figures() (+49 more)

### Community 43 - "Community 43"
Cohesion: 0.06
Nodes (36): device, Path, Initialize learnable CORAL bin values from the fitted binner., Initialize CORAL biases from fitted class priors (if configured)., Generate VIN encoding plots for a single oracle-labeled batch.          Args:, Initialize binner-derived scorer state for a Lightning stage.          Lightning, Log the effective VIN config (post-sanitization) and persist it as JSON., Load a checkpoint and return an evaluation-ready scorer module.          Args: (+28 more)

### Community 45 - "Community 45"
Cohesion: 0.04
Nodes (54): symb_use_L13_1_rl_H_b75d2b63(), symb_use_L14_1_model_candidate_row_74c08558(), symb_use_L14_3_shape_Nq_407ef9c0(), symb_use_L18_1_model_target_token_542325d3(), symb_use_L36_1_model_candidate_geometry_token_3ec0f4e4(), symb_use_L47_1_model_candidate_row_74c08558(), symb_use_L51_1_model_candidate_geometry_token_3ec0f4e4(), symb_use_L52_1_model_candidate_validity_token_61ad259f() (+46 more)

### Community 47 - "Community 47"
Cohesion: 0.06
Nodes (56): Render immutable root-observation-store diagnostics., _backbone_rows(), _block_rows(), _component_rows(), _coverage_rows(), _load_offline_store_from_toml(), _memory_rows(), _pose_rows() (+48 more)

### Community 48 - "Community 48"
Cohesion: 0.07
Nodes (53): _as_step_matrix(), _discount_weights(), discounted_selected_return(), _endpoint_errors(), endpoint_log_gain(), endpoint_log_gain_tensor(), endpoint_target_gain(), endpoint_target_gain_tensor() (+45 more)

### Community 50 - "Community 50"
Cohesion: 0.08
Nodes (32): ensure_unbatched_pose(), PoseTW, Squeeze a singleton batch from :class:`PoseTW` while preserving unbatched poses., _angular_separation(), _append_diversity_selection(), _circular_min_delta(), CounterfactualPoseGenerator, _exact_pose_index() (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.04
Nodes (11): symb_use_L27_1_vin_field_evl_0_9d2b1a47(), symb_use_L287_1_vin_occ_in_8dee4cc7(), symb_use_L289_1_vin_free_in_c2b4749b(), symb_use_L304_1_vin_cent_pr_577ebf19(), symb_use_L378_1_vin_occ_in_8dee4cc7(), symb_use_L379_1_vin_free_in_c2b4749b(), symb_use_L407_1_vin_cent_pr_577ebf19(), symb_vin_cent_pr() (+3 more)

### Community 53 - "Community 53"
Cohesion: 0.06
Nodes (29): Avoid propagating rollout Zarr ``store`` into the VIN source config., BaseConfig, Any, Path, PydanticBaseSettingsSource, Self, Keep legacy ``BaseConfig[T]`` subclass declarations working., Track which fields were propagated from a parent config. (+21 more)

### Community 54 - "Community 54"
Cohesion: 0.06
Nodes (31): candidate_topk_oracle_hit(), Tensor, Non-differentiable candidate-ranking evaluation.  This module provides compariso, Compare selected candidate actions against oracle-best candidate labels.      Th, Per-table oracle diagnostics for a selected candidate action.      Attributes:, Report whether predicted top-k rows include an oracle-best candidate.      The o, selected_action_oracle_comparison(), SelectedActionOracleComparison (+23 more)

### Community 55 - "Community 55"
Cohesion: 0.07
Nodes (30): device, PerspectiveCameras, PoseTW, Tensor, Return clamped valid-prefix lengths as ``Tensor["", int64]`` or ``Tensor["B", in, Return ``Tensor["N", bool]`` or ``Tensor["B N", bool]`` valid-prefix masks., Return a copy with candidate ordering randomly permuted.          The permutatio, Collate cached VIN batches by padding candidate sets to a shared length. (+22 more)

### Community 56 - "Community 56"
Cohesion: 0.07
Nodes (42): compress_point_features(), Tensor, Descriptor compression helpers for point-feature banks.  This module provides ex, Apply an explicit descriptor compression transform.      Args:         features:, Return a human-readable label for raw, sliced, or projected descriptors.      Th, resolve_compression_id(), FeaturePoolingResult, Point-feature pooling result container for logged multiview evidence.  This modu (+34 more)

### Community 57 - "Community 57"
Cohesion: 0.05
Nodes (25): term_aria_synthetic_environments(), term_egocentric_foundation_model_3d(), term_next_best_view(), term_relative_reconstruction_improvement(), term_use_L45_1_next_best_view_99059264(), term_use_L45_2_relative_reconstruction_improvem_f9d7e62d(), term_use_L48_1_relative_reconstruction_improvem_f9d7e62d(), term_use_L7_1_relative_reconstruction_improvem_f9d7e62d() (+17 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (39): r"""Train the runnable one-step VIN candidate scorer with Lightning.  This modul, Log configured scorer gradient norms after Lightning backpropagation.          L, Logable, LogSpec, Loss, loss_key(), Metric, metric_key() (+31 more)

### Community 60 - "Community 60"
Cohesion: 0.09
Nodes (47): _render_rerun_launcher(), build_rerun_rollout_command(), build_rerun_rollout_spawn_command(), build_rerun_rollout_web_command(), detect_lan_ip(), format_command(), poll_rerun_launch(), _port_is_available() (+39 more)

### Community 61 - "Community 61"
Cohesion: 0.08
Nodes (21): Any, Figure, Tensor, Log and reset stage-owned candidate ranking accumulators., Compute the configured CORAL loss variant (per-sample)., r"""Own one-step CORAL training state for a VIN candidate scorer.      The modul, Persist fitted ordinal-binner state inside a Lightning checkpoint., Restore embedded ordinal-binner state before stage setup runs. (+13 more)

### Community 62 - "Community 62"
Cohesion: 0.07
Nodes (45): build_offline_command(), build_rollouts_command(), main(), offline_main(), plan_main(), plan_rollout_shards_command(), help, min (+37 more)

### Community 65 - "Community 65"
Cohesion: 0.08
Nodes (45): info_command(), _preflight_payload(), _print_stats(), _print_text_summary(), Any, help, min, Option (+37 more)

### Community 66 - "Community 66"
Cohesion: 0.07
Nodes (37): collect_runtime_provenance(), _git_root(), _git_summary(), manifest_json_bytes(), manifest_sha256(), _package_versions(), Any, Path (+29 more)

### Community 68 - "Community 68"
Cohesion: 0.06
Nodes (22): eqs_model_qh_input_contract(), eqs_use_L59_1_model_qh_input_contract_ee97fd5c(), marker_evidence_L118_1_pending_e2258693(), marker_evidence_L11_1_pending_e2258693(), marker_evidence_L152_1_pending_e2258693(), marker_evidence_L49_1_pending_e2258693(), marker_gate_L118_1_frame_transform_row_shuffle_and__66ca11dc(), marker_gate_L11_1_preserve_row_identity_masks_prov_34558dfb() (+14 more)

### Community 69 - "Community 69"
Cohesion: 0.10
Nodes (43): Render Optuna study analysis., _bin_numeric_series(), _bootstrap_diff(), _bootstrap_slope(), _bucket_param(), _cliffs_delta(), _coerce_numeric(), _duplicate_configs() (+35 more)

### Community 70 - "Community 70"
Cohesion: 0.07
Nodes (32): AseEfmDataset, AseEfmDatasetConfig, _infer_ids(), infer_semidense_bounds(), _matches_snippet_token(), Any, Tensor, Trimesh (+24 more)

### Community 71 - "Community 71"
Cohesion: 0.09
Nodes (39): _decode_dataclass(), _decode_dict_key(), _decode_legacy_perspective_cameras(), _decode_value(), from_serializable(), _move_tensor(), _normalize_payload_dict(), _normalize_payload_value() (+31 more)

### Community 72 - "Community 72"
Cohesion: 0.08
Nodes (43): build_backbone_evidence_figures(), build_geometry_overview_figure(), build_scene_field_evidence_figures(), build_valid_fraction_figure(), build_voxel_frame_figure(), Any, Plot voxel grid bounds and voxel axes in world coordinates., Plot sparse voxel evidence as world-space scatter plots. (+35 more)

### Community 74 - "Community 74"
Cohesion: 0.06
Nodes (21): marker_decision_todo_L131_1(), marker_evidence_L10_1_pending_e2258693(), marker_evidence_L24_1_pending_e2258693(), marker_evidence_L97_1_pending_e2258693(), marker_gate_L10_1_retain_the_one_step_scorer_as_a__3715a485(), marker_gate_L125_1_A0_A1_learning_per_horizon_suppo_57e851af(), marker_gate_L131_1_model_selection_protocol_freeze_b8234a7e(), marker_gate_L24_1_explicit_horizon_query_DTO_dynam_bbb4d931() (+13 more)

### Community 76 - "Community 76"
Cohesion: 0.09
Nodes (42): assign_offline_splits(), _camera_param_to_numpy(), _default_sample_key(), _keep_field(), _pad_first_axis(), _pose_to_numpy(), prepare_vin_offline_sample(), _probabilities_to_numpy() (+34 more)

### Community 77 - "Community 77"
Cohesion: 0.07
Nodes (28): CandidateDepthRenderer, CandidateDepthRendererConfig, CameraTW, PoseTW, Tensor, Return the high-level candidate renderer constructed by this config., Reject half-specified exact render sizes., High-level wrapper that renders depth for compact valid candidate poses. (+20 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (28): Tensor, Instantiate the configured scoring head.          Args:             in_dim: Opti, Predict ordinal RRI logits from per-candidate feature vectors.      `VinScorerHe, Build the MLP and CORAL threshold layer.          Args:             config: Conf, Return CORAL threshold logits for candidate features.          Args:, Configure the shared VIN ordinal scoring head., Factory target for `BaseConfig.setup_target`., VinScorerHead (+20 more)

### Community 80 - "Community 80"
Cohesion: 0.05
Nodes (14): symb_use_L284_2_shape_Vvox_aec1e8cd(), symb_use_L295_2_shape_Fin_0e002e57(), symb_use_L297_2_shape_Fhead_163a8a9a(), symb_use_L298_2_shape_Fhead_163a8a9a(), symb_use_L317_2_shape_Tlen_2e8359f4(), symb_use_L361_2_shape_Vvox_aec1e8cd(), symb_use_L383_2_shape_Fin_0e002e57(), symb_use_L384_2_shape_Fhead_163a8a9a() (+6 more)

### Community 81 - "Community 81"
Cohesion: 0.08
Nodes (22): Console, Any, Shared logger instance across all consoles., Shared global step across all consoles., Remove this instance's contextual prefix and return the console., Emit an informational message when verbosity is enabled., Log a structured summary built from `summarize`., Emit a warning message and include a short caller stack. (+14 more)

### Community 82 - "Community 82"
Cohesion: 0.06
Nodes (28): symb_use_L11_1_vin_unknown_04c57f03(), symb_use_L11_2_vin_counts_norm_db03c706(), symb_use_L12_1_vin_new_surface_prior_7a7ae61a(), symb_use_L12_2_vin_unknown_04c57f03(), symb_use_L12_3_vin_occ_pr_588d0116(), symb_use_L15_1_vin_loss_3f04e1e5(), symb_use_L15_2_vin_loss_3f04e1e5(), symb_use_L15_3_vin_loss_3f04e1e5() (+20 more)

### Community 83 - "Community 83"
Cohesion: 0.06
Nodes (27): symb_use_L1058_1_rl_qh_3a1a25cb(), symb_use_L1186_1_rl_qh_3a1a25cb(), symb_use_L395_1_rl_qh_3a1a25cb(), symb_use_L395_2_rl_qh_3a1a25cb(), symb_use_L498_1_rl_qh_3a1a25cb(), symb_use_L112_1_rl_qh_3a1a25cb(), symb_use_L112_2_rl_qh_3a1a25cb(), symb_use_L42_1_rl_qh_3a1a25cb() (+19 more)

### Community 84 - "Community 84"
Cohesion: 0.07
Nodes (29): BaseView, EfmGtCameraObbView, EfmGtTimestampView, EfmGTView, EfmObbView, EfmTrajectoryView, _extract_field_docs(), _get_field_doc() (+21 more)

### Community 85 - "Community 85"
Cohesion: 0.07
Nodes (25): Self, Configure one-step ordinal candidate scoring and optimization.      The config c, Return the :class:`VinLightningModule` factory target., VinLightningModuleConfig, AdamWConfig, OneCycleSchedulerConfig, Any, Tensor (+17 more)

### Community 86 - "Community 86"
Cohesion: 0.08
Nodes (32): _class_name(), _first_scalar_string(), _float_tuple(), _latest_valid_obb_slice(), _obb_geometry_valid(), OracleTargetTaskSampler, OracleTargetTaskSamplerConfig, OracleTargetTaskSamplingResult (+24 more)

### Community 87 - "Community 87"
Cohesion: 0.09
Nodes (24): Efm3dDepthRenderer, Efm3dDepthRendererConfig, CameraTW, device, ndarray, PoseTW, Tensor, Trimesh (+16 more)

### Community 89 - "Community 89"
Cohesion: 0.05
Nodes (36): eqs_metrics_closest_point_witness(), eqs_metrics_directed_reconstruction_errors(), eqs_metrics_point_to_reference_distance(), eqs_metrics_threshold_reconstruction_diagnostics(), symb_use_L20_2_oracle_tolerance_36f2ebf6(), symb_use_L24_2_oracle_tolerance_36f2ebf6(), eqs_use_L159_1_metrics_closest_point_witness_516f9048(), eqs_use_L159_2_metrics_closest_point_witness_516f9048() (+28 more)

### Community 91 - "Community 91"
Cohesion: 0.05
Nodes (20): symb_use_L71_1_obs_points_t_9aa40fb4(), symb_use_L54_1_obs_img_rgb_0ccbb0a8(), symb_use_L55_1_obs_pose_e941bdab(), symb_use_L97_1_obs_depth_eb85df5a(), symb_use_L97_2_obs_vis_d5922451(), symb_use_L97_3_obs_points_cf_c751f081(), symb_use_L97_4_obs_face_normal_54730b2c(), symb_use_L734_1_obs_points_t_9aa40fb4() (+12 more)

### Community 92 - "Community 92"
Cohesion: 0.09
Nodes (20): _dictionary_preview(), _finite_or_zero(), _plot_color(), Path, Initialize the Rerun recording and configured output sink., Return the selected-path seed point in the displayed world frame., Log one rollout chain from a validated rollout Zarr store., Build the visible rollout-target overlay payload from factual target tables. (+12 more)

### Community 94 - "Community 94"
Cohesion: 0.09
Nodes (19): CandidatePlotBuilder, _pretty_metric_label(), Self, Fluent, snippet-aware builder for full-shell candidate diagnostics.      The bui, Create a snippet plot with candidate results already attached., Attach candidate sampling results for plotting., Attach candidate config for metadata-aware plotting., Add the candidate reference frame axes to the figure.          Notes: (+11 more)

### Community 95 - "Community 95"
Cohesion: 0.12
Nodes (33): BenchmarkRecord, BenchmarkSummary, build_latency_figure(), build_scaling_figure(), build_speedup_figure(), build_throughput_figure(), compute_speedups(), _display_implementation_name() (+25 more)

### Community 98 - "Community 98"
Cohesion: 0.08
Nodes (32): _forward_yaw_delta(), Tensor, Return horizontal forward-axis angle from reference to shell poses., _normalise(), device, dtype, PoseTW, Tensor (+24 more)

### Community 99 - "Community 99"
Cohesion: 0.09
Nodes (28): build_projection_grid(), encode_projection_summary(), project_points_to_candidate_cameras(), Any, device, dtype, PerspectiveCameras, Tensor (+20 more)

### Community 100 - "Community 100"
Cohesion: 0.08
Nodes (23): eqs_scene_actor_state_read(), eqs_use_L37_1_scene_actor_state_read_85d318da(), marker_evidence_L11_1_pending_e2258693(), marker_evidence_L27_1_pending_e2258693(), marker_evidence_L79_1_pending_e2258693(), marker_evidence_L93_1_pending_e2258693(), marker_gate_L11_1_retain_actor_oracle_provenance_c_c376139d(), marker_gate_L27_1_selected_observation_reader_dete_fa2da352() (+15 more)

### Community 101 - "Community 101"
Cohesion: 0.10
Nodes (30): is_efm_snippet_view_instance(), is_vin_snippet_view_instance(), Return whether ``value`` behaves like an `EfmSnippetView`.      The v2 stack acc, Return whether ``value`` behaves like a `VinSnippetView`., CandidateScorerBatchInputs, prepare_candidate_scorer_batch_inputs(), device, Batch input normalization for VIN-compatible Lightning scorers.  :class:`aria_nb (+22 more)

### Community 102 - "Community 102"
Cohesion: 0.09
Nodes (27): marker_archive_note_L6_1(), marker_decision_todo_L40_1(), marker_evidence_L15_1_pending_e2258693(), marker_gate_L15_1_validated_stores_with_matched_ma_276075a7(), marker_gate_L24_1_held_out_target_matching_and_myo_19a1b9a7(), marker_gate_L32_1_positive_uncertainty_qualified_h_f93986e3(), marker_gate_L40_1_confirmatory_bundle_freeze_6291eda3(), marker_gate_L54_1_validated_campaign_and_confirmat_c9ea4499() (+19 more)

### Community 105 - "Community 105"
Cohesion: 0.16
Nodes (28): _as_tensor(), _candidate_count(), collect_offline_visual_inventory(), _finite_prefix(), _first_length(), _get_required(), _invalid(), _missing() (+20 more)

### Community 106 - "Community 106"
Cohesion: 0.10
Nodes (22): PointNeXtSEncoder, PointNeXtSEncoderConfig, Path, Tensor, Optional PointNeXt-S encoder for semidense VIN point clouds.  This module owns `, Switch training mode while keeping frozen OpenPoints weights in eval mode., Call the most specific feature-forward method exposed by OpenPoints., Encode point clouds into a compact semidense embedding.          Args: (+14 more)

### Community 110 - "Community 110"
Cohesion: 0.12
Nodes (14): Optimizable, optimizable_field(), Any, Describe a search space over an explicit finite choice set., Sample a value from Optuna.          Args:             trial: Optuna trial (duck, Convert a suggested value to a JSON/W&B friendly representation., Convert a categorical choice into an Optuna-friendly primitive.          Returns, Stable string representation for categorical sequences. (+6 more)

### Community 113 - "Community 113"
Cohesion: 0.10
Nodes (27): Render Weights & Biases run analysis., _cached_entities(), _cached_projects(), _normalize_step_bounds(), Any, Weights & Biases run comparison and training-dynamics diagnostics.  The panel pr, Normalize step bounds, returning (min,max,error_message)., Render cross-run analytics from W&B run history. (+19 more)

### Community 114 - "Community 114"
Cohesion: 0.11
Nodes (16): _encoded_values(), dtype, Validate that store-global target rows do not mix VIN source snippets., Return true when a structured target id names a different snippet., Validation summary for a rollout Zarr store.      `errors` contains schema, link, Return ``True`` when no validation errors were found., Validate row linkage, masks, and initial ``Q_H`` target availability., Validate a standalone rollout replay store and return all discovered errors. (+8 more)

### Community 115 - "Community 115"
Cohesion: 0.10
Nodes (17): MultiStepCandidateScorer, MultiStepCandidateScorerConfig, Scaffold for finite-horizon candidate-value VIN scorers.  This module owns the p, Config-as-factory placeholder for the planned finite-horizon scorer.      Attrib, Factory target for `BaseConfig.setup_target` once implemented., Non-runnable scaffold for the planned Q_H scorer.      The future implementation, Reject construction until the finite-horizon scorer is implemented., marker_evidence_L37_1_pending_e2258693() (+9 more)

### Community 120 - "Community 120"
Cohesion: 0.08
Nodes (17): Path, Self, Build a block descriptor for one Zarr-backed numeric array.          Args:, Build a block descriptor for indexed per-row MessagePack records.          Args:, Persist the manifest to disk.          Args:             path: Destination manif, Read the global sample index.          Args:             path: ``sample_index.js, Write the global sample index.          Args:             path: Destination ``sa, Load the manifest, sample index, and split metadata.          Args: (+9 more)

### Community 121 - "Community 121"
Cohesion: 0.10
Nodes (21): EfmSnippetView, Own the typed boundary around one adapted ATEK/ASE snippet.      ``efm`` retains, Return whether a ground-truth mesh is attached to the snippet., Return a view with the EFM dict pruned to the requested keys.          Args:, build_root_eval_pointcloud(), _exact_trajectory_index(), observed_prefix_frame_indices(), ValueError (+13 more)

### Community 122 - "Community 122"
Cohesion: 0.14
Nodes (24): Return a summary-focused repr for the snippet view., build_nested(), _extract_tensor(), _format_tensor_summary(), _is_tensor_summary(), _list_desc(), Any, Tensor (+16 more)

### Community 125 - "Community 125"
Cohesion: 0.09
Nodes (5): marker_evidence_L3_1_pending_e2258693(), marker_gate_L3_1_implementation_and_held_out_eval_073c96c3(), marker_implementation_L3_1_planned_80e61027(), marker_source_L3_1_development_only_source_typ_10_7debcf98(), marker_thesis_status_L3_1()

### Community 127 - "Community 127"
Cohesion: 0.08
Nodes (14): Return the hierarchical Zarr path for a logical block name.          Args:, ndarray, Path, Load the global sample indices for one split.          Args:             split:, Choose a chunk shape aligned with row-wise random-access reads.          Args:, Write one fixed-size numeric block into the shard Zarr group.          Args:, Return index records for the requested split.          Args:             split:, Read one numeric block row for a sample.          Args:             record: Glob (+6 more)

### Community 128 - "Community 128"
Cohesion: 0.11
Nodes (23): CLIAriaNBVExperimentConfig, CLIWandbAnalysisConfig, _ensure_run_mode(), _extract_config_path(), fit_binner_main(), main(), _merge_with_toml(), optuna_main() (+15 more)

### Community 129 - "Community 129"
Cohesion: 0.12
Nodes (22): _compact_or_live_gt_obbs(), _latest_valid_obb_slice(), _obb_boxes(), _obb_family(), _obb_line_strips(), ObbTW, PoseTW, Tensor (+14 more)

### Community 130 - "Community 130"
Cohesion: 0.14
Nodes (24): CounterfactualStepResult, CameraTW, Return the selected candidate camera from the compact valid table., Return a new trajectory with one selected transition appended., One selected transition and its finite-candidate decision context.      ``N`` is, _candidate_invalid_reasons(), _full_candidate_vector(), _full_shell_bool_extra() (+16 more)

### Community 131 - "Community 131"
Cohesion: 0.17
Nodes (14): _flatten_edges_for_plotly(), _pose_positions(), ndarray, Tensor, Convert ``(N, 2, 3)`` edges to NaN-separated XYZ for a single Scatter3d trace., Return positions (...,3) as numpy from PoseTW or compatible tensor shapes., Composable builder for mesh/points/frusta visuals using a stored snippet.      A, Add semidense points cropped by a world-frame oriented box. (+6 more)

### Community 132 - "Community 132"
Cohesion: 0.12
Nodes (19): EvlBackbone, EvlBackboneConfig, filter_backbone_output_for_features_mode(), _normalize_evl_model_config_paths(), Any, Path, ValidationInfo, EVL backbone adapter for VIN scorer architectures.  VIN consumes raw EFM snippet (+11 more)

### Community 133 - "Community 133"
Cohesion: 0.10
Nodes (10): marker_evidence_L35_1_pending_e2258693(), marker_evidence_L8_1_pending_e2258693(), marker_gate_L35_1_typed_selected_observation_reade_0cfbd22c(), marker_gate_L8_1_preserve_deterministic_shell_ide_39033443(), marker_implementation_L35_1_planned_80e61027(), marker_implementation_L8_1_implemented_07f151f1(), marker_source_L35_1_docs_contents_theory_efm3d_scene_7648bc00(), marker_source_L8_1_aria_nbv_aria_nbv_rollouts_repla_4b68d23b() (+2 more)

### Community 134 - "Community 134"
Cohesion: 0.12
Nodes (24): _linear_slope(), ndarray, slice, Estimate a linear slope for one x/y series., Compute early/mid/late segment slices for a series., _segment_indices(), build_dynamics_dataframe(), _finite_mean() (+16 more)

### Community 136 - "Community 136"
Cohesion: 0.09
Nodes (5): marker_evidence_L54_1_pending_e2258693(), marker_gate_L54_1_explicit_horizon_query_reader_de_80154dfd(), marker_implementation_L54_1_partial_355705cf(), marker_source_L54_1_aria_nbv_aria_nbv_data_handling__bf9c06e0(), marker_thesis_status_L54_1()

### Community 138 - "Community 138"
Cohesion: 0.11
Nodes (16): Typed config-as-factory foundation for ARIA-NBV runtime objects.  This module pr, Base class for singleton configurations., Return self since this is a singleton., SingletonConfig, Shared Rich formatting helpers for human-facing package CLIs.  The helpers in th, Rich console with shared verbosity, debug state, and structured summaries.  This, Shared configuration, diagnostics, geometry, and visualization utilities.  The p, Optuna-friendly search space helpers.  This mirrors the utility layer from ``ext (+8 more)

### Community 139 - "Community 139"
Cohesion: 0.11
Nodes (14): Reusable candidate scoring heads for VIN architectures.  This module owns small,, CoralLayer, MonotoneBinValues, r"""CORAL ordinal regression and continuous decoding for RRI-derived labels.  Th, Approximate inverse of softplus for positive targets., r"""Parameterize learnable continuous bin representatives monotonically.      We, Return the fixed number ``K`` of monotone representatives., Reset from ``Tensor["K", float32]`` targets while preserving strict positive del (+6 more)

### Community 143 - "Community 143"
Cohesion: 0.14
Nodes (23): _print_samples(), _print_summary(), help, min, Option, random_index_command(), Print a small table of split-local VIN offline rows., Print a deterministic random split-local index for Rerun inspection. (+15 more)

### Community 144 - "Community 144"
Cohesion: 0.11
Nodes (20): _find_tar_for_sample(), _looks_like_shard_id(), _normalize_shard_stem(), Path, Resolve an explicit shard path or relative shard reference., Resolve a shard identifier against the configured scene directories., Find the shard tar that contains the requested sample key., Split mixed snippet identifiers into shard ids and sample keys. (+12 more)

### Community 145 - "Community 145"
Cohesion: 0.09
Nodes (13): Overlay the actor-visible target OBB used for target-conditioned rollout generat, dtype, Tensor, Actor-safe target instruction DTOs., Sanitized target instruction for target-conditioned candidate generation.      T, Target center in world coordinates, metres., Return `center_world` as a 3-vector tensor., Return a stable actor-safe diagnostic id derived from descriptor fields. (+5 more)

### Community 146 - "Community 146"
Cohesion: 0.12
Nodes (17): plot_candidate_pointcloud_scene(), CameraTW, PerspectiveCameras, PoseTW, Self, Rendering-focused extensions on top of `CandidatePlotBuilder`.      This keeps a, Add camera frusta and their image-plane rectangles to the 3D scene., Scatter hit points back-projected from rendered depth maps. (+9 more)

### Community 150 - "Community 150"
Cohesion: 0.09
Nodes (23): symb_use_L287_3_shape_D_781a1f31(), symb_use_L289_3_shape_D_781a1f31(), symb_use_L291_3_shape_D_781a1f31(), symb_use_L292_2_shape_D_781a1f31(), symb_use_L295_3_shape_D_781a1f31(), symb_use_L297_3_shape_D_781a1f31(), symb_use_L298_3_shape_D_781a1f31(), symb_use_L301_3_shape_D_781a1f31() (+15 more)

### Community 151 - "Community 151"
Cohesion: 0.09
Nodes (23): symb_use_L287_4_shape_H_3cbf26bf(), symb_use_L289_4_shape_H_3cbf26bf(), symb_use_L291_4_shape_H_3cbf26bf(), symb_use_L292_3_shape_H_3cbf26bf(), symb_use_L295_4_shape_H_3cbf26bf(), symb_use_L297_4_shape_H_3cbf26bf(), symb_use_L298_4_shape_H_3cbf26bf(), symb_use_L301_4_shape_H_3cbf26bf() (+15 more)

### Community 152 - "Community 152"
Cohesion: 0.09
Nodes (23): symb_use_L287_5_shape_Wdim_31658973(), symb_use_L289_5_shape_Wdim_31658973(), symb_use_L291_5_shape_Wdim_31658973(), symb_use_L292_4_shape_Wdim_31658973(), symb_use_L295_5_shape_Wdim_31658973(), symb_use_L297_5_shape_Wdim_31658973(), symb_use_L298_5_shape_Wdim_31658973(), symb_use_L301_5_shape_Wdim_31658973() (+15 more)

### Community 153 - "Community 153"
Cohesion: 0.11
Nodes (15): CustomRichProgressBar, CustomTQDMProgressBar, Callback, Self, Construct the callback set owned by each Lightning trainer.  This module provide, Build callbacks and adapt trial-specific ownership flags.          Args:, Custom TQDM progress bar that hides the version number (v_num)., Return Lightning progress metrics without the logger version field. (+7 more)

### Community 154 - "Community 154"
Cohesion: 0.09
Nodes (13): Any, device, PoseTW, Tensor, Target center in world coordinates, shape ``(3,)``., Store a copy of the cumulative validity mask for diagnostics., Apply a rejection mask (True = reject) to the current validity mask., Attach debug tensors in a consistent shape (clone kept to avoid side-effects). (+5 more)

### Community 155 - "Community 155"
Cohesion: 0.13
Nodes (19): _filter_runs(), _get_run(), _list_projects(), _list_runs(), _load_runs_filtered(), Protocol, Return available projects for a given entity., Fetch up to max_runs from W&B, ordered by recency when supported. (+11 more)

### Community 161 - "Community 161"
Cohesion: 0.13
Nodes (17): Observed snippet inspection with optional oracle scene overlays.  The panel prov, Render modalities, poses, projections, and 3D context for one snippet.      Args, render_data_page(), apply_scene_plot_options(), Shared controls and typed options for snippet-level Plotly scene views.  This mo, Render shared 3D scene controls and return the chosen camera/options., Default visibility and style choices for a snippet 3D scene view., Apply shared scene options to a `SnippetPlotBuilder` subclass. (+9 more)

### Community 162 - "Community 162"
Cohesion: 0.12
Nodes (12): EfmCameraView, Tensor, Expose one calibrated Aria camera stream view without copying EFM tensors., Return ``Tensor["F 2", float32]`` horizontal/vertical FOV in degrees., Return the number of frames in the camera stream., Resolve user-provided frame indices, supporting negatives and defaults., Return selected camera indices and nearest trajectory indices., Return the requested camera stream view from the backing EFM dict. (+4 more)

### Community 163 - "Community 163"
Cohesion: 0.14
Nodes (13): EfmPointsView, device, dtype, ndarray, Move the camera view tensors to the requested device and dtype., Move the trajectory tensors to the requested device and dtype., Expose actor-visible MPS semidense reconstruction evidence.      The ``ARIA_POIN, Move the semidense point tensors to the requested device and dtype. (+5 more)

### Community 164 - "Community 164"
Cohesion: 0.11
Nodes (21): _apply_overrides(), help, min, Option, Path, StrEnum, Inspect one configured VIN sample or rollout chain in a Rerun session.      CLI, Reject incompatible CLI viewer and SDK-sink combinations. (+13 more)

### Community 167 - "Community 167"
Cohesion: 0.13
Nodes (18): _BackboneAccumulator, _broadcast_ref_pose(), _candidate_pose_values(), _collect_backbone_diagnostics(), _normalise(), ndarray, Tensor, Return unit vectors with stable zero handling. (+10 more)

### Community 173 - "Community 173"
Cohesion: 0.15
Nodes (15): marker_decision_todo_L51_1(), marker_evidence_L8_1_pending_e2258693(), marker_gate_L39_1_artifact_backed_Results_bundle_ec5dee59(), marker_gate_L45_1_architecture_validity_report_364a8856(), marker_gate_L51_1_confirmatory_analysis_freeze_43c07335(), marker_gate_L8_1_frozen_held_out_manifest_complet_2b2db9a7(), marker_implementation_L8_1_partial_355705cf(), marker_source_L39_1_thesis_objective_to_evidence_con_44cf5a1f() (+7 more)

### Community 174 - "Community 174"
Cohesion: 0.17
Nodes (17): _crop_mesh(), load_or_process_mesh(), _mesh_cache_lock(), MeshProcessSpec, _processed_mesh_from_cache(), ProcessedMesh, Path, Tensor (+9 more)

### Community 175 - "Community 175"
Cohesion: 0.18
Nodes (11): PositionSampler, PoseTW, Tensor, Fallback: sample unit vectors via normalized Gaussian noise., Return normalized actor-visible target bearing in the reference frame., Blend a base direction with orthogonal noise in the reference frame., Map raw angular samples to the configured position family., Draw candidate centers and offsets in reference frame.          Args: (+3 more)

### Community 180 - "Community 180"
Cohesion: 0.14
Nodes (14): explicit_hidden_world_view_paths(), hidden_world_view_paths(), log_default_inspector_blueprint(), normalize_blueprint_entity_path(), Compose optional Rerun viewer layouts for offline and rollout inspection.  This, Return the default world-view query rules for Rerun blueprints., Return rooted world-view entity paths hidden by default but still included., Return only caller-selected rooted entity paths hidden by a layer policy. (+6 more)

### Community 185 - "Community 185"
Cohesion: 0.11
Nodes (15): eqs_binning_edges(), eqs_binning_label(), eqs_binning_levels(), eqs_use_L150_1_binning_edges_8f54289a(), eqs_use_L150_2_binning_edges_8f54289a(), eqs_use_L151_1_binning_label_6f29ef54(), eqs_use_L151_2_binning_label_6f29ef54(), eqs_use_L152_1_binning_levels_abdbc9c4() (+7 more)

### Community 186 - "Community 186"
Cohesion: 0.11
Nodes (14): symb_use_L69_1_ase_traj_19445068(), symb_use_L20_1_ase_traj_19445068(), symb_use_L20_2_ase_traj_19445068(), symb_use_L21_1_ase_traj_final_806145af(), symb_use_L21_2_ase_traj_final_806145af(), symb_use_L90_1_ase_traj_19445068(), symb_use_L90_2_ase_traj_19445068(), symb_use_L91_1_ase_traj_final_806145af() (+6 more)

### Community 187 - "Community 187"
Cohesion: 0.15
Nodes (10): plot_trajectory(), ObbTW, Self, Mesh + semidense + trajectory + optional frusta/bounds., Create a builder whose initial bounds cover the snippet evidence., Add the snippet's world-frame GT mesh when one is loaded., Add sampled world-frame semi-dense points colored by world height.          The, Add the world-frame rig trajectory and optional endpoint markers. (+2 more)

### Community 196 - "Community 196"
Cohesion: 0.12
Nodes (7): symb_use_L5_1_vin_global_933fb530(), symb_use_L6_1_vin_gamma_2420325f(), symb_use_L6_2_vin_global_933fb530(), symb_use_L6_3_vin_beta_89b4918a(), symb_vin_beta(), symb_vin_gamma(), symb_vin_global_()

### Community 197 - "Community 197"
Cohesion: 0.15
Nodes (15): bbox_edges(), collect_frame_modalities(), _depth_to_color(), mesh_to_plotly(), Trimesh, Build Streamlit/Plotly views of EFM snippet geometry and frame modalities.  This, Convert tensor image (C,H,W or H,W) to uint8 HWC., Colorise a single depth/distance map to uint8 RGB using a perceptual colormap. (+7 more)

### Community 203 - "Community 203"
Cohesion: 0.12
Nodes (9): symb_use_L278_1_frame_v_4c1d368c(), symb_use_L279_2_frame_w_b7d6a863(), symb_use_L279_3_frame_v_4c1d368c(), symb_use_L358_1_frame_v_4c1d368c(), symb_use_L359_2_frame_w_b7d6a863(), symb_use_L359_3_frame_v_4c1d368c(), symb_frame_v(), symb_frame_w() (+1 more)

### Community 204 - "Community 204"
Cohesion: 0.17
Nodes (10): marker_evidence_L55_1_pending_e2258693(), marker_gate_L55_1_implement_feasibility_head_and_e_967d50d5(), marker_gate_L67_1_feasibility_calibration_and_poli_645aac8b(), marker_implementation_L55_1_planned_80e61027(), marker_research_todo_L67_1(), marker_source_L55_1_aria_nbv_aria_nbv_rollouts_zarr__4b89521c(), marker_source_L67_1_invalid_row_supervision_hypothes_bbdd13aa(), marker_thesis_status_L55_1() (+2 more)

### Community 205 - "Community 205"
Cohesion: 0.15
Nodes (6): marker_archive_note_L252_1(), marker_archive_note_L43_1(), marker_archive_note_L5_1(), marker_source_L252_1_OMX_successor_registry_and_trans_f82bd68f(), marker_source_L43_1_transcript_evidence_boundary_8b6f4de3(), marker_source_L5_1_deduplicated_ARIA_user_records_p_9420e8ed()

### Community 206 - "Community 206"
Cohesion: 0.19
Nodes (14): build_vin_snippet_view(), collapse_vin_points(), empty_vin_snippet(), pad_vin_points(), Any, device, Tensor, Canonical helpers for adapting raw EFM snippets into VIN snippet views.  This mo (+6 more)

### Community 207 - "Community 207"
Cohesion: 0.14
Nodes (11): Return the registered scorer through the structural VIN protocol.          `self, CandidateScorer, CandidateScorerPrediction, Any, Protocol, Tensor, Protocol for trainable candidate scorers consumed by VIN Lightning.      Impleme, Initialize scorer-owned CORAL bin representatives. (+3 more)

### Community 219 - "Community 219"
Cohesion: 0.19
Nodes (9): device, dtype, Tensor, Return the unpadded point cloud for one compact candidate row., Drop non-selected render evidence while preserving configured audits., Normalize candidate evidence and verify compact-row alignment., Return a normalized scorer result aligned with `candidates`., Normalize tensors and verify compact rows against the candidate table. (+1 more)

### Community 220 - "Community 220"
Cohesion: 0.18
Nodes (9): _pose_at(), _pose_row(), PoseTW, Tensor, Return the selected valid pose in world coordinates., Return the root pose or final selected pose., Return root and selected poses in trajectory order.          Returns:, Return camera centres as ``Tensor["T 3", float32]`` in world metres. (+1 more)

### Community 221 - "Community 221"
Cohesion: 0.14
Nodes (8): Tree, Render the nested configuration as a Rich tree on the project console., Return a green `ok` or red `failed` Rich text token., status_text(), Create a console with prefix inferred from the caller's module and function., Compatibility constructor mirroring the PRML VSLAM console API., Set a custom prefix for all log messages.          Enables builder-style chainin, Text

### Community 222 - "Community 222"
Cohesion: 0.18
Nodes (9): Normalize verbosity values accepted across config models., Return the process-wide minimum level for informational output., Set the process-wide verbosity after coercing supported aliases., Set verbosity level (0=quiet, 1=normal, 2=verbose)., Backward-compatible alias for `set_verbosity`., Ordered output gates shared by every :class:`Console` instance., Coerce booleans/ints/strings into a Verbosity level., Verbosity (+1 more)

### Community 223 - "Community 223"
Cohesion: 0.21
Nodes (10): FrameGridBuilder, plot_first_last_frames(), plot_frames(), Figure, Apply equal world-axis scaling and return the accumulated figure., Builder for image grids (2D modalities)., Place one HWC image array into a one-indexed subplot cell., Apply the configured canvas dimensions and return the image grid. (+2 more)

### Community 237 - "Community 237"
Cohesion: 0.23
Nodes (11): _as_candidate_matrix(), _as_path_matrix(), candidate_order_consistency(), _candidate_valid_matrix(), _masked_argmax(), Tensor, Compare candidate scores before and after a candidate-order shuffle.      Args:, Accumulate one batch of selected rollout paths.          Args:             camer (+3 more)

### Community 238 - "Community 238"
Cohesion: 0.19
Nodes (9): CandidateOrderConsistencyMetric, CandidatePrimaryInvalidReasonMetric, CandidateProvenanceShareMetric, MetricBase, Accumulate primary invalid-reason share among rejected candidates.      The conf, Accumulate selected camera-center path cost in metres.      The metric expects r, Accumulate shuffled-candidate order-consistency diagnostics.      This metric su, Accumulate candidate provenance-family share diagnostics.      The metric report (+1 more)

### Community 239 - "Community 239"
Cohesion: 0.21
Nodes (13): build_run_dataframes(), _extract_run_steps(), _flatten_mapping(), _format_timestamp(), Any, Safely coerce a W&B mapping-like object to a plain dict., Extract the best-available step count from a run summary., Render timestamps consistently for run tables. (+5 more)

### Community 240 - "Community 240"
Cohesion: 0.21
Nodes (9): coral_expected_from_logits(), coral_logits_to_prob(), Tensor, Return ``Tensor["K", float32]`` monotone representatives ``u_k``., r"""Decode CORAL logits into expected ordinal rank and normalized rank.      Arg, Decode ``Tensor["... K", float32]`` class probabilities to a continuous RRI prox, Repair ``Tensor["... K-1", float32]`` logits to marginals and decode their RRI p, Return scalar mean-squared deviation from ``Tensor["K", float32]`` target bin va (+1 more)

### Community 246 - "Community 246"
Cohesion: 0.21
Nodes (7): OracleCandidateScorer, OracleInvalidity, Protocol, Expected scorer invalidity accepted by the pipeline adapter., Return the stable domain reason code for hard-invalid control flow., Return an actionable explanation of the invalid outcome., Oracle scorer accepted by the evaluated-rollout adapter.

### Community 247 - "Community 247"
Cohesion: 0.20
Nodes (9): Control whether one Rerun layer is recorded and initially shown.      ``included, Reject a blueprint visibility request for an excluded layer., Resolve recording inclusion and initial visibility by scientific role.      The, RerunInspectorLayerState, RerunInspectorRolloutLayersConfig, LayerOverride, Resolve reproducible layer policies for rollout Rerun inspection.  Layer presets, Expand a preset and optional per-layer overrides into explicit policy.      Args (+1 more)

### Community 248 - "Community 248"
Cohesion: 0.21
Nodes (11): _build_streamlit_argv(), __getattr__(), _has_file_watcher_override(), main(), Any, Path, Launch the configured ARIA-NBV Streamlit application.  This module owns the `nbv, Construct and run the configured ARIA-NBV Streamlit application. (+3 more)

### Community 249 - "Community 249"
Cohesion: 0.26
Nodes (9): get_frustum_segments(), pose_world_cam(), project_pointcloud_on_frame(), CameraTW, PoseTW, Return frustum wireframe segments in world frame using CameraTW.unproject., Project 3D points into image plane and overlay on the frame., r"""Add camera frusta aligned to nearest rig trajectory timestamps.          Pos (+1 more)

### Community 257 - "Community 257"
Cohesion: 0.26
Nodes (8): marker_evidence_L14_1_pending_e2258693(), marker_gate_L14_1_a_measured_limitation_that_the_p_1e4c1569(), marker_gate_L27_1_artifact_backed_failure_analysis_6872de0e(), marker_implementation_L14_1_exploratory_5ea84816(), marker_research_todo_L27_1(), marker_source_L14_1_tab_thesis_scene_representation__d24ca9d2(), marker_source_L27_1_method_design_space_registry_rep_a9e8fe15(), marker_thesis_status_L14_1()

### Community 258 - "Community 258"
Cohesion: 0.20
Nodes (6): Return the msgpack filename used for one logical record block.          Args:, Return the offsets filename used for indexed record blocks.          Args:, Any, Write one indexed per-row diagnostic record block for the shard.          Args:, Read and decode one record by row index., Read one optional per-row diagnostic record.          Args:             record:

### Community 259 - "Community 259"
Cohesion: 0.24
Nodes (9): candidate_best_value(), candidate_masked_mean(), CandidateOrderConsistency, _finite_mask(), Operational validity, provenance, path, and policy audits for rollouts.  This mo, Per-table diagnostics for shuffled-candidate consistency.      Attributes:, Reduce candidate-table values with a hard validity mask.      Args:         valu, Return the best finite candidate value under a hard mask.      Args:         val (+1 more)

### Community 260 - "Community 260"
Cohesion: 0.18
Nodes (8): candidate_path_increment_stats(), CandidatePathIncrementMetric, CandidatePathIncrementStats, Summarize per-candidate path increments under the hard action mask.      Args:, Per-table movement-cost diagnostics for candidate action rows.      The rollout, Accumulate candidate action path-increment diagnostics in metres.      The metri, Accumulate one batch of candidate path-increment tables., Return finite means of candidate path-increment table statistics.

### Community 261 - "Community 261"
Cohesion: 0.18
Nodes (9): candidate_primary_invalid_reason_share(), candidate_provenance_share(), CandidatePrimaryInvalidReasonStats, _id_membership(), Compute per-table share of candidates from selected provenance families.      Ca, Summarize primary invalid-reason concentration among rejected rows.      Args:, Accumulate one batch of primary invalid-reason ids., Per-table primary invalid-reason share among rejected candidate rows.      Rollo (+1 more)

### Community 271 - "Community 271"
Cohesion: 0.24
Nodes (10): _pair_from_tar_member(), Any, Path, Resolve a manifest path snapshot without mutating global path config., Scan raw tar headers for dataset snippet pairs., Infer ``(scene_id, snippet_id)`` from one WebDataset tar member name., Resolve raw EFM tar paths from a stored dataset config snapshot., _resolve_coverage_tar_paths() (+2 more)

### Community 272 - "Community 272"
Cohesion: 0.22
Nodes (9): CandidateScorerConfig, CandidateScorerTrainingContract, Lightning-side validation for VIN candidate scorer contracts.  `aria_nbv.vin.can, Return the scorer contract or reject contracts unsupported by Lightning.      Ar, validate_vin_lightning_candidate_scorer_contract(), candidate_scorer_training_contract(), CandidateScorerConfig, CandidateScorerTrainingContract (+1 more)

### Community 273 - "Community 273"
Cohesion: 0.20
Nodes (6): FourierFeatures, Tensor, Sin/cos Fourier features with optional learnable frequencies.      Args:, Return the raw-input plus sine/cosine output width., Apply Fourier feature mapping to inputs.          Args:             x: ``Tensor[, Return the runtime module type constructed by this config.

### Community 286 - "Community 286"
Cohesion: 0.28
Nodes (9): Export W&B summaries, histories, dynamics, and local figure manifests., wandb_main(), collect_run_media_images(), list_run_dirs(), Path, Resolve the local W&B root directory (auto-detect nested layout)., List local W&B run directories for a run id (and optionally latest-run)., Collect local train/val figure image files for a W&B run. (+1 more)

### Community 287 - "Community 287"
Cohesion: 0.22
Nodes (3): _PipelineOracleState, PoseTW, Tensor

### Community 288 - "Community 288"
Cohesion: 0.25
Nodes (6): IterableDataset, Store the online dataset dependencies., OracleRriLabeler, Compute oracle RRI labels for candidates in a single snippet., Return the runtime pipeline type constructed by this config., _target_cls()

### Community 289 - "Community 289"
Cohesion: 0.22
Nodes (6): candidate_policy_entropy(), CandidatePolicyEntropyMetric, Compute masked per-table entropy from candidate selection probabilities.      Th, Accumulate masked candidate-policy entropy diagnostics.      The metric summariz, Accumulate one batch of candidate selection probabilities., Return mean entropy or ``NaN`` when no table had positive mass.

### Community 290 - "Community 290"
Cohesion: 0.22
Nodes (5): Return reason-group share and denominator-validity rate., Return mean acquisition cost aliases for policy tables., Return shuffled-candidate consistency diagnostics., Return finite mean family share or ``NaN`` when no tables were valid., _safe_mean()

### Community 304 - "Community 304"
Cohesion: 0.25
Nodes (5): Apply Optimizable hints embedded in the config tree., Report whether normal informational logging is currently enabled., Enable normal output when true, otherwise silence informational logs., Return the process-wide debug gate used by :meth:`dbg`., Set the process-wide debug gate for every console instance.

### Community 305 - "Community 305"
Cohesion: 0.29
Nodes (5): Any, Trimesh, Parse scene/snippet identifiers from the cache sample key.          Args:, Infer AABB bounds for cache samples from stored volume metadata., Construct a snippet view from an offline-cache EFM dict.          Args:

### Community 306 - "Community 306"
Cohesion: 0.25
Nodes (7): load_run_histories(), _load_wandb_history(), _load_wandb_history_clean(), Fetch a raw W&B history dataframe (no cleanup)., Load W&B history with basic cleanup (optional inf -> nan).      Returns a new da, Fetch history dataframes for each run (by id)., Return history data (typically a pandas.DataFrame or list of dicts).

### Community 317 - "Community 317"
Cohesion: 0.29
Nodes (6): __dir__(), __getattr__(), Any, Lazy public facade for Streamlit panel renderers.  Importing this package does n, Import and return one panel renderer when first requested., Return package globals plus lazy renderer exports.

### Community 318 - "Community 318"
Cohesion: 0.29
Nodes (4): CandidateTableMetrics, Accumulate hard-mask candidate-table diagnostics.      The metric reports valid/, Accumulate candidate hard-mask validity without value summaries., Return candidate validity and value diagnostics.

### Community 319 - "Community 319"
Cohesion: 0.33
Nodes (5): device, dtype, Tensor, Normalize compact scores and bind them to one hard-masked table., Verify the hard mask and candidate-order link against ``candidates``.

### Community 320 - "Community 320"
Cohesion: 0.33
Nodes (6): encode_shell_pose_descriptor(), PoseTW, Shared shell-pose descriptors for VIN candidate encoders.  The shell encoders de, Canonical shell descriptor for a candidate pose.      Attributes:         center, Build the canonical shell descriptor for poses in a reference frame.      Args:, ShellPoseDescriptor

### Community 327 - "Community 327"
Cohesion: 0.29
Nodes (7): eqs_entity_target_descriptor(), eqs_use_L156_1_entity_target_descriptor_8a6fac85(), eqs_use_L156_2_entity_target_descriptor_8a6fac85(), eqs_use_L232_1_entity_target_descriptor_8a6fac85(), eqs_use_L232_2_entity_target_descriptor_8a6fac85(), eqs_use_L11_1_entity_target_descriptor_8a6fac85(), eqs_use_L106_1_entity_target_descriptor_8a6fac85()

### Community 328 - "Community 328"
Cohesion: 0.29
Nodes (7): symb_use_L121_1_shape_K_67e796fd(), symb_use_L121_2_shape_K_67e796fd(), symb_use_L51_1_shape_K_67e796fd(), symb_use_L51_2_shape_K_67e796fd(), symb_use_L307_2_shape_K_67e796fd(), symb_use_L409_2_shape_K_67e796fd(), symb_shape_K()

### Community 329 - "Community 329"
Cohesion: 0.33
Nodes (4): Render persisted multi-step rollout supervision., Stable public entry point for the stored-rollout inspector., Render the science-first stored-dataset inspection workflow., render_stored_rollouts_panel()

### Community 330 - "Community 330"
Cohesion: 0.33
Nodes (4): Any, Trainer, Instantiate a Trainer after logger and callback ownership is resolved., Return the external Lightning trainer factory target.

### Community 331 - "Community 331"
Cohesion: 0.33
Nodes (4): PlottingConfig, Apply style within a context, restoring previous settings afterwards., Reusable Matplotlib, seaborn, and Plotly presentation settings., Apply plotting style globally (no automatic restore).

### Community 339 - "Community 339"
Cohesion: 0.40
Nodes (4): Protocol, Shared interface for datasets that yield `VinOracleBatch`., Iterate over VIN oracle batches., VinOracleDatasetBase

### Community 340 - "Community 340"
Cohesion: 0.40
Nodes (3): Any, Drop worker-local loader state before pickling.          Returns:             Da, Restore worker-local loader state after unpickling.          Args:             s

### Community 342 - "Community 342"
Cohesion: 0.40
Nodes (3): Add axes for a camera stream or the rig itself.          Args:             frame, Add axes for a named camera stream through :meth:`add_frame_axes`., Add LUF axes for multiple cameras in one go.

### Community 343 - "Community 343"
Cohesion: 0.40
Nodes (3): device, Reconstruct one backbone output from a serialized payload.          Args:, Move all tensors to the specified device.

### Community 358 - "Community 358"
Cohesion: 0.40
Nodes (5): symb_use_L310_2_shape_M_385beb7e(), symb_use_L312_2_shape_M_385beb7e(), symb_use_L411_2_shape_M_385beb7e(), symb_use_L412_2_shape_M_385beb7e(), symb_shape_M()

### Community 360 - "Community 360"
Cohesion: 0.50
Nodes (4): main(), _normalize_default_summary(), Run VIN offline-store inspection.      Args:         argv: Optional argument vec, Preserve the legacy default ``summary`` command.

### Community 361 - "Community 361"
Cohesion: 0.50
Nodes (3): Yield oracle-labelled VIN batches from the wrapped raw dataset., Adapt one online Oracle label result to the model-facing batch., _vin_batch_from_label()

### Community 362 - "Community 362"
Cohesion: 0.50
Nodes (3): _list_entities(), Return available entities (user + teams) for the current API token., Return metadata for the authenticated viewer and its teams.

## Knowledge Gaps
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PathConfig` connect `Community 33` to `Community 128`, `Community 3`, `Community 4`, `Community 5`, `Community 134`, `Community 132`, `Community 9`, `Community 138`, `Community 10`, `Community 271`, `Community 399`, `Community 17`, `Community 144`, `Community 19`, `Community 20`, `Community 400`, `Community 23`, `Community 153`, `Community 286`, `Community 34`, `Community 37`, `Community 43`, `Community 174`, `Community 47`, `Community 58`, `Community 60`, `Community 62`, `Community 69`, `Community 70`, `Community 106`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `EfmSnippetView` connect `Community 121` to `Community 2`, `Community 131`, `Community 4`, `Community 8`, `Community 18`, `Community 19`, `Community 146`, `Community 21`, `Community 24`, `Community 25`, `Community 26`, `Community 29`, `Community 288`, `Community 161`, `Community 34`, `Community 162`, `Community 163`, `Community 38`, `Community 41`, `Community 305`, `Community 50`, `Community 187`, `Community 197`, `Community 70`, `Community 72`, `Community 76`, `Community 77`, `Community 206`, `Community 84`, `Community 86`, `Community 94`, `Community 223`, `Community 99`, `Community 101`, `Community 249`, `Community 122`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `Console` connect `Community 81` to `Community 128`, `Community 2`, `Community 131`, `Community 4`, `Community 132`, `Community 8`, `Community 9`, `Community 138`, `Community 18`, `Community 19`, `Community 21`, `Community 24`, `Community 153`, `Community 25`, `Community 29`, `Community 31`, `Community 33`, `Community 34`, `Community 37`, `Community 174`, `Community 304`, `Community 50`, `Community 53`, `Community 58`, `Community 62`, `Community 197`, `Community 70`, `Community 77`, `Community 341`, `Community 87`, `Community 221`, `Community 222`, `Community 223`, `Community 101`, `Community 122`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `EfmSnippetView` (e.g. with `run_vin_diagnostics()` and `AseEfmDataset`) actually correct?**
  _`EfmSnippetView` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `PathConfig` (e.g. with `OptunaConfig` and `WandbConfig`) actually correct?**
  _`PathConfig` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `RolloutZarrStoreReader` (e.g. with `RolloutSuspiciousQueryConfig` and `StoredRollout`) actually correct?**
  _`RolloutZarrStoreReader` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Console` (e.g. with `BaseConfig` and `SingletonConfig`) actually correct?**
  _`Console` has 7 INFERRED edges - model-reasoned connections that need verification._