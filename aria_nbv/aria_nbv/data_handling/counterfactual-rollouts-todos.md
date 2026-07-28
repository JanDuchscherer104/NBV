# TODOs

- [x] "Open selected rollout in Rerun" button doesn't work (I'm on the streamlit page via Network URL form mac, not directly from the SSH host). It should also allow opening rerun in web-viewer (i.e. --serve-web) or in the native rerun wayland viewer. Resolved by moving stored rollout inspection to the VIN Offline Dataset page and exposing separate web/native Rerun actions.
- [ ] The corresponding command (which works, when I run it on the Ubuntu machine; `uv run nbv-rerun-inspect --config-path /home/jd/repos/ARIA-NBV/.configs/inspection/rerun/rerun_offline.toml --rollout-store /home/jd/repos/ARIA-NBV/.data/offline_cache/rollouts_v1_smoke.zarr --rollout-row-id 4 --spawn`) shows "Rollout RRI" and "Rollout Diagnostics" these plots are not really informative. Streamlit now has richer stored/live rollout plots; the Rerun time-series blueprint still needs a separate design pass if it should match the Streamlit dashboard.
- [x] Plots of the (target) RRI, fixed-horizon endpoint metric (J_e^(H), G_t^(H),  J_(e,"log")^(H)) should be plotted on the Streamlit page using plotly. Live rollouts now plot selected target RRI, G_t^(H), endpoint/log-gain when selected target point-mesh fields are emitted, candidate fanout bands, and top-k candidate RRI. Stored rollouts show persisted cumulative target/scene RRI only until the Zarr schema stores endpoint point-mesh fields.
- [x] We still have the "VIN Offline Dataset" / "_page_offline_dataset". So there is some redundancy with "_page_counterfactual_rollouts#stored-rollout-zarr". How should we optimally resolve and collapse. Moved stored rollout-Zarr inspection to the VIN Offline Dataset page; Counterfactual Rollouts is live generation/evaluation only.
- [x] on `_page_counterfactual_rollouts#Live Rollouts` tab, make cuda default device for "Generator device", and `temperature_softmax` default "Selection policy"
- [x] on `_page_counterfactual_rollouts#Live Rollouts` tab, the "3D rollout scene" plots the rolled out frusta with incorrect "rotation" - I think that we have to apply the `rotate_yaw_cw90` to the frusta before plotting. Also, the color of the frusta should encode the respective target_rri, while the colors of the edges in a trajectory should encode the lineage.
- [x] on `_page_counterfactual_rollouts#Live Rollouts` tab, show Semi-dense points crop within the target's OBB.
- [x] on `_page_counterfactual_rollouts#Live Rollouts` tab add a plotly chart, visualizing the different RRI metrics (target RRI, fixed-horizon endpoint metric (J_e^(H), G_t^(H),  J_(e,"log")^(H))) across the rollout steps / trajectories.

- [x] In the "Rollout row" table, previously in `_page_counterfactual_rollouts#stored-rollout-zarr`, rows looked like this
    ```csv
    candidate_row_id	step_index	shell_index	selected	actor_action	q_train	target_rri	scene_rri	strategy_id	mixture_id
    0	0	0	FALSE	TRUE	TRUE	0.000005025777682021726		3	0
    ```
    Stored rollout candidate rows now decode strategy names, render mixture components as `component_<id>` when names are not persisted, and include an `_info_popover` for displayed columns.
