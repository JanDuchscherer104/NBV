import torch

from aria_nbv.app.state import config_signature
from aria_nbv.data_handling import AseEfmDatasetConfig
from aria_nbv.oracle.pipelines.scene_labels import OracleRriLabelerConfig
from aria_nbv.pose_generation import CandidateViewGeneratorConfig
from aria_nbv.rendering import CandidateDepthRendererConfig


def test_config_signature_handles_torch_and_enums() -> None:
    sig = config_signature(CandidateViewGeneratorConfig())
    assert isinstance(sig, str) and sig

    cfg = CandidateViewGeneratorConfig(view_target_point_world=torch.tensor([1.0, 2.0, 3.0]))
    sig = config_signature(cfg)
    assert isinstance(sig, str) and sig


def test_config_signature_handles_nested_configs() -> None:
    sig = config_signature(OracleRriLabelerConfig())
    assert isinstance(sig, str) and sig


def test_config_signature_handles_dataset_and_renderer_configs() -> None:
    sig = config_signature(AseEfmDatasetConfig(batch_size=None))
    assert isinstance(sig, str) and sig

    sig = config_signature(CandidateDepthRendererConfig())
    assert isinstance(sig, str) and sig
