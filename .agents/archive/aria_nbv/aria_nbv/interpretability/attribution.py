"""Captum-based attribution utilities."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

import torch
import torch.nn.functional as functional
from captum.attr import (  # type: ignore[import-untyped]
    DeepLift,
    FeatureAblation,
    InputXGradient,
    IntegratedGradients,
    LayerGradCam,
    LayerGradientXActivation,
    NoiseTunnel,
    Occlusion,
)
from torch import Tensor, nn

from ..utils import Console, TargetConfig


class AttributionMethod(StrEnum):
    """Supported Captum algorithms for vision backbones."""

    GRAD_CAM = "grad_cam"
    """Gradient-weighted Class Activation Mapping. Gives a heat map over the input image showing which receptive fields
    contributed most to the activations int the final conv layers."""
    INTEGRATED_GRADIENTS = "integrated_gradients"
    """Attribute a model's prediction back to its input features. I.e. which parts of the input contributed the most to
    the model's prediction. It integrates gradients gradients along a path that describes a morphing from a baseline
    input (i.e. blank image) into the actual input. """
    DEEP_LIFT = "deep_lift"
    """DeepLift back-propagates differences between the prediction given a baseline and actual input to attribute
    changes in the output to differences in the input."""
    INPUT_X_GRADIENT = "input_x_gradient"
    """Multiplies the input features by the gradients of the output with respect to the input. Gives a simple measure of
    which input features have the most influence on the output at a particular point in the feature space."""
    LAYER_GRAD_X_ACT = "layer_grad_x_activation"
    """Layer Gradient x Activation computes the gradients of the output w.r.t. to the activations of a specific layer
    and multiplies them with these activation maps to get a layer-wise view of how indiviual neurons in that layer
    contribute to the final output. Gives insights into which parts of the feature maps in a layer are most influential."""
    OCCLUSION = "occlusion"
    """Occlusion is a perturbation-based method that systematically occludes parts of the input (i.e. by sliding an
    occlusion window over the image) and captures the change in the model's output. Regions that cause significant
    changes in the output when occluded are deemed important for the model's prediction."""
    FEATURE_ABLATION = "feature_ablation"
    """Systematically removes parts of the input to see how the model's predictions change."""
    NOISE_TUNNEL_IG = "noise_tunnel_ig"
    """Noise Tunnel is an extension to Integrated Gradients that adds noise to the input multiple times, runs IG
    and subsequently averages the attributions. This has a smoothing effect and can help reduce noise in the attributions."""


class BaselineStrategy(StrEnum):
    """Reference construction for baseline-dependent methods."""

    ZERO = "zero"
    DATASET_MEAN = "dataset_mean"


class AttributionEngine:
    """Captum integration wrapper that yields input-aligned heatmaps."""

    def __init__(
        self,
        config: InterpretabilityConfig,
        model: nn.Module,
        forward_func: Callable[[Tensor], Tensor] | None = None,
    ) -> None:
        self.config = config
        self.model = model
        self.forward_func = forward_func or model
        self.console = Console.with_prefix(self.__class__.__name__, "attribute")

    def attribute(
        self,
        inputs: Tensor,
        *,
        target: Tensor | int | None = None,
        additional_forward_args: Sequence[Tensor] | Tensor | None = None,
    ) -> AttributionResult:
        """Compute an attribution heatmap for the given batch.

        Args:
            inputs: Normalised input batch ``(B, C, H, W)`` or feature vectors
                ``(B, F)``.
            target: Class index/indices to attribute. If None, uses argmax per
                example.
            additional_forward_args: Extra tensors forwarded to the model.

        Returns:
            AttributionResult containing a (B, H, W) heatmap and raw attribution.
        """

        was_training = self.model.training
        self.model.eval()

        input_clone = inputs.detach().clone()
        input_clone.requires_grad_(True)

        if target is None:
            with torch.no_grad():
                target = self.forward_func(input_clone).argmax(dim=-1)

        attrib_obj = self._build_attributor()

        with torch.enable_grad():
            raw_attr = self._run_attribution(
                attrib_obj=attrib_obj,
                inputs=input_clone,
                target=target,
                additional_forward_args=additional_forward_args,
            )

        heatmap = self._to_heatmap(raw_attr=raw_attr, reference=input_clone)

        if was_training:
            self.model.train(True)

        return AttributionResult(
            heatmap=heatmap,
            raw_attribution=raw_attr,
            method=self.config.method,
            target=target,
        )

    # ------------------------------------------------------------------ builders
    def _build_attributor(self) -> object:
        match self.config.method:
            case AttributionMethod.GRAD_CAM:
                layer = self._resolve_layer()
                return LayerGradCam(self.forward_func, layer)
            case AttributionMethod.LAYER_GRAD_X_ACT:
                layer = self._resolve_layer()
                return LayerGradientXActivation(self.forward_func, layer)
            case AttributionMethod.INTEGRATED_GRADIENTS:
                return IntegratedGradients(self.forward_func)
            case AttributionMethod.NOISE_TUNNEL_IG:
                ig = IntegratedGradients(self.forward_func)
                return NoiseTunnel(ig)
            case AttributionMethod.DEEP_LIFT:
                return DeepLift(self.forward_func)
            case AttributionMethod.INPUT_X_GRADIENT:
                return InputXGradient(self.forward_func)
            case AttributionMethod.OCCLUSION:
                return Occlusion(self.forward_func)
            case AttributionMethod.FEATURE_ABLATION:
                return FeatureAblation(self.forward_func)

    def _resolve_layer(self) -> nn.Module:
        if self.config.target_layer is not None:
            layer = self._get_nested_attr(self.model, self.config.target_layer)
            if isinstance(layer, nn.Module):
                return layer
            msg = f"Resolved target_layer '{self.config.target_layer}' is not a Module"
            self.console.error(msg)
            raise ValueError(msg)

        conv_layers = [module for module in self.model.modules() if isinstance(module, nn.Conv2d)]
        if not conv_layers:
            raise ValueError("No Conv2d layers found for layer-based attribution.")

        if self.model.__class__.__name__.lower().startswith("visiontransformer"):
            return conv_layers[0]
        return conv_layers[-1]

    @staticmethod
    def _get_nested_attr(root: nn.Module, path: str) -> object:
        current: object = root
        for part in path.split("."):
            current = getattr(current, part)
        return current

    # ---------------------------------------------------------------- attribution
    def _run_attribution(
        self,
        attrib_obj: object,
        inputs: Tensor,
        target: Tensor | int,
        additional_forward_args: Sequence[Tensor] | Tensor | None,
    ) -> Tensor:
        baseline = self._build_baseline(inputs)

        assert NoiseTunnel is not None
        assert IntegratedGradients is not None
        assert DeepLift is not None
        assert InputXGradient is not None
        assert LayerGradCam is not None
        assert LayerGradientXActivation is not None
        assert Occlusion is not None
        assert FeatureAblation is not None

        if isinstance(attrib_obj, NoiseTunnel):
            attr = attrib_obj.attribute(  # type: ignore[arg-type]
                inputs,
                baselines=baseline,
                target=target,
                additional_forward_args=additional_forward_args,
                nt_type="smoothgrad",
                nt_samples=self.config.noise_samples,
                stdevs=self.config.noise_std,
            )
            return attr

        if isinstance(attrib_obj, IntegratedGradients):
            return attrib_obj.attribute(  # type: ignore[arg-type]
                inputs,
                baselines=baseline,
                target=target,
                additional_forward_args=additional_forward_args,
                n_steps=self.config.n_steps,
            )

        if isinstance(attrib_obj, DeepLift):
            return attrib_obj.attribute(  # type: ignore[arg-type]
                inputs,
                baselines=baseline,
                target=target,
                additional_forward_args=additional_forward_args,
            )

        if isinstance(attrib_obj, InputXGradient):
            return attrib_obj.attribute(inputs, target=target, additional_forward_args=additional_forward_args)

        if isinstance(attrib_obj, (LayerGradCam, LayerGradientXActivation)):
            return attrib_obj.attribute(  # type: ignore[arg-type]
                inputs,
                target=target,
                additional_forward_args=additional_forward_args,
                attribute_to_layer_input=False,
            )

        if isinstance(attrib_obj, Occlusion):
            window = (inputs.shape[1], *self.config.occlusion_window)
            stride = (inputs.shape[1], *self.config.occlusion_stride)
            return attrib_obj.attribute(  # type: ignore[arg-type]
                inputs,
                target=target,
                additional_forward_args=additional_forward_args,
                sliding_window_shapes=window,
                strides=stride,
                baselines=baseline,
            )

        if isinstance(attrib_obj, FeatureAblation):
            return attrib_obj.attribute(  # type: ignore[arg-type]
                inputs,
                target=target,
                additional_forward_args=additional_forward_args,
                baselines=baseline,
            )

        raise ValueError(f"Unhandled attribution object: {attrib_obj.__class__.__name__}")

    def _build_baseline(self, inputs: Tensor) -> Tensor:
        match self.config.baseline:
            case BaselineStrategy.ZERO:
                return torch.zeros_like(inputs)
            case BaselineStrategy.DATASET_MEAN:
                return inputs.mean(dim=0, keepdim=True).expand_as(inputs)

    # -------------------------------------------------------------- postprocess
    def _to_heatmap(self, raw_attr: Tensor, reference: Tensor) -> Tensor:
        if raw_attr.dim() == 4 and raw_attr.shape[1] > 1:
            spatial = raw_attr.abs().mean(dim=1) if self.config.use_abs else raw_attr.mean(dim=1)
        elif raw_attr.dim() == 3:
            spatial = raw_attr.abs() if self.config.use_abs else raw_attr
        else:
            spatial = raw_attr.squeeze()
            if spatial.dim() == 3 and spatial.shape[0] == reference.shape[0]:
                spatial = spatial.abs().mean(dim=1) if self.config.use_abs else spatial.mean(dim=1)

        if reference.dim() <= 2 or spatial.dim() <= 2:
            if spatial.dim() == 1:
                spatial = spatial.unsqueeze(0)
            heatmap = self._min_max_normalise(spatial)
            return heatmap

        if spatial.dim() == 2:
            spatial = spatial.unsqueeze(1)

        heatmap = functional.interpolate(
            spatial.unsqueeze(1),
            size=reference.shape[2:],
            mode="bilinear",
            align_corners=False,
        ).squeeze(1)

        heatmap = self._min_max_normalise(heatmap)
        return heatmap

    @staticmethod
    def _min_max_normalise(heatmap: Tensor) -> Tensor:
        if heatmap.dim() == 0:
            return heatmap
        if heatmap.dim() == 1:
            heatmap = heatmap.unsqueeze(0)
        b = heatmap.shape[0]
        flat = heatmap.view(b, -1)
        min_vals, _ = flat.min(dim=1, keepdim=True)
        max_vals, _ = flat.max(dim=1, keepdim=True)
        denom = (max_vals - min_vals).clamp_min(1e-6)
        norm = (flat - min_vals) / denom
        return norm.view_as(heatmap)


@dataclass(slots=True)
class AttributionResult:
    """Container for processed attribution outputs.

    Attributes:
        heatmap: Attribution map normalised to [0, 1] with shape ``(B, H, W)``
            for image inputs or ``(B, F)`` for feature vectors.
        raw_attribution: Captum-native attribution tensor prior to projection.
        method: Algorithm used.
        target: Class index/indices the attribution was computed for.
    """

    heatmap: Tensor
    raw_attribution: Tensor
    method: AttributionMethod
    target: Tensor | int | None


class InterpretabilityConfig(TargetConfig["AttributionEngine"]):
    """Factory config that builds an `AttributionEngine`."""

    @property
    def target_type(self) -> type["AttributionEngine"]:
        """Factory target for the config."""
        return AttributionEngine

    method: AttributionMethod = AttributionMethod.GRAD_CAM
    """Attribution algorithm to apply."""

    target_layer: str | None = None
    """Optional dotted path to the layer used for layer-based methods."""

    baseline: BaselineStrategy = BaselineStrategy.ZERO
    """Reference construction for baseline-aware methods (IG/DeepLift)."""

    n_steps: int = 32
    """Number of integration steps for Integrated Gradients."""

    use_abs: bool = True
    """Take absolute value before heatmap normalisation."""

    occlusion_window: tuple[int, int] = (32, 32)
    """(height, width) of the occlusion window."""

    occlusion_stride: tuple[int, int] = (16, 16)
    """(height, width) stride for occlusion sliding window."""

    noise_samples: int = 8
    """Number of noisy samples for NoiseTunnel smoothing."""

    noise_std: float = 0.1
    """Standard deviation for NoiseTunnel Gaussian noise."""

    def setup_target(
        self,
        model: nn.Module,
        *,
        forward_func: Callable[[Tensor], Tensor] | None = None,
    ) -> "AttributionEngine":
        """Instantiate an `AttributionEngine` bound to ``model``."""

        return AttributionEngine(config=self, model=model, forward_func=forward_func)


__all__ = [
    "AttributionEngine",
    "AttributionMethod",
    "AttributionResult",
    "BaselineStrategy",
    "InterpretabilityConfig",
]
