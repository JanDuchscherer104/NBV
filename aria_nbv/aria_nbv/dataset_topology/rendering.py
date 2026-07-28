"""Shared Streamlit rendering for topology snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd
import streamlit as st

from .contracts import TopologySnapshot


def render_topology_snapshot(
    *,
    snapshot: TopologySnapshot | None = None,
    node_rows: Sequence[Mapping[str, object]] | None = None,
    edge_rows: Sequence[Mapping[str, object]] | None = None,
    tree_text: str | None = None,
    diagram_dot: str | None = None,
) -> None:
    """Render a shared topology snapshot or legacy row projections.

    ``node_rows``, ``edge_rows``, and ``tree_text`` remain accepted together
    for existing app call sites. New consumers should pass ``snapshot`` so the
    common typed boundary owns every projection.
    """

    if snapshot is not None:
        if node_rows is not None or edge_rows is not None or tree_text is not None:
            raise ValueError("Pass either snapshot or explicit topology rows, not both.")
        node_rows = snapshot.node_rows()
        edge_rows = snapshot.edge_rows()
        tree_text = snapshot.tree_text()
        diagram_dot = snapshot.diagram_dot()
    if node_rows is None or edge_rows is None or tree_text is None:
        raise ValueError("Topology rows and tree_text are required when snapshot is omitted.")

    if diagram_dot:
        st.graphviz_chart(diagram_dot, width="stretch")
    node_tab, relation_tab, tree_tab = st.tabs(["Fields and arrays", "Relationships", "Raw tree"])
    with node_tab:
        st.dataframe(pd.DataFrame(node_rows), hide_index=True, width="stretch")
    with relation_tab:
        st.dataframe(pd.DataFrame(edge_rows), hide_index=True, width="stretch")
    with tree_tab:
        st.code(tree_text or "No metadata nodes were resolved.", language="text")


__all__ = ["render_topology_snapshot"]
