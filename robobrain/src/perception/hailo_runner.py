"""
Synchronous Hailo HEF inference wrapper (HailoRT / hailo_platform).

Requires Raspberry Pi OS packages from `sudo apt install hailo-all` (or equivalent).
API aligned with common Hailo community MWE (HailoRT 4.19+).
"""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

try:
    import hailo_platform as hpf
except ImportError:
    hpf = None  # type: ignore


class HailoSyncInferencer:
    """One HEF, one network group, blocking InferVStreams."""

    def __init__(self, hef_path: str, use_pcie: bool = True):
        if hpf is None:
            raise RuntimeError(
                "hailo_platform not importable. On Raspberry Pi: sudo apt install hailo-all "
                "and use the system Python or venv with access to /usr/lib/python3/dist-packages."
            )
        self._hpf = hpf
        self.hef = hpf.HEF(hef_path)
        self._use_pcie = use_pcie
        self._vdevice: Any = None
        self._target = None
        self._network_group = None
        self._ng_params = None
        self._activate_ctx: Any = None
        self._infer_pipeline: Any = None
        self._input_infos = list(self.hef.get_input_vstream_infos())
        self._output_infos = list(self.hef.get_output_vstream_infos())

    @property
    def input_names(self) -> List[str]:
        return [i.name for i in self._input_infos]

    @property
    def output_names(self) -> List[str]:
        return [o.name for o in self._output_infos]

    def open(self) -> None:
        hpf = self._hpf
        iface = hpf.HailoStreamInterface.PCIe if self._use_pcie else hpf.HailoStreamInterface.INTEGRATED
        self._vdevice = hpf.VDevice()
        self._target = self._vdevice.__enter__()
        configure_params = hpf.ConfigureParams.create_from_hef(self.hef, interface=iface)
        self._network_group = self._target.configure(self.hef, configure_params)[0]
        self._ng_params = self._network_group.create_params()

        input_vstreams_params = hpf.InputVStreamParams.make_from_network_group(
            self._network_group, quantized=False, format_type=hpf.FormatType.FLOAT32
        )
        output_vstreams_params = hpf.OutputVStreamParams.make_from_network_group(
            self._network_group, quantized=False, format_type=hpf.FormatType.FLOAT32
        )
        self._activate_ctx = self._network_group.activate(self._ng_params)
        self._activate_ctx.__enter__()
        self._infer_pipeline = hpf.InferVStreams(
            self._network_group, input_vstreams_params, output_vstreams_params
        )
        self._infer_pipeline.__enter__()

    def close(self) -> None:
        if self._infer_pipeline is not None:
            try:
                self._infer_pipeline.__exit__(None, None, None)
            except Exception:
                pass
            self._infer_pipeline = None
        if self._activate_ctx is not None:
            try:
                self._activate_ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._activate_ctx = None
        if self._vdevice is not None:
            try:
                self._vdevice.__exit__(None, None, None)
            except Exception:
                pass
            self._vdevice = None
        self._network_group = None
        self._target = None

    def __enter__(self) -> "HailoSyncInferencer":
        self.open()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def infer(self, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """
        inputs: stream name -> float32 array shaped as HEF expects (batch added if 3D).
        """
        if not self._infer_pipeline:
            raise RuntimeError("Hailo inferencer not open; call open() or use context manager.")
        feed: Dict[str, np.ndarray] = {}
        for info in self._input_infos:
            if info.name not in inputs:
                raise KeyError(f"Missing input '{info.name}'; have {list(inputs.keys())}")
            arr = inputs[info.name].astype(np.float32, copy=False)
            if arr.ndim == 3:
                arr = np.expand_dims(arr, axis=0)
            feed[info.name] = arr
        raw = self._infer_pipeline.infer(feed)
        return {name: np.asarray(raw[name]) for name in raw}
