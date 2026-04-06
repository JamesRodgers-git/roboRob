"""
Synchronous HEF inference via HailoRT InferModel API (Hailo-10H / modern pyhailort).

Uses ``VDevice`` + ``create_infer_model`` + ``ConfiguredInferModel.run()``. Multiple HEFs on one
chip must share a **single** ``VDevice`` (``group_id="SHARED"`` + scheduler); a second ``VDevice``
on the same device raises ``HAILO_DEVICE_IN_USE``.

Requires: ``sudo apt install hailo-all`` (or equivalent) and system ``hailo_platform``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

try:
    import hailo_platform as hpf
except ImportError:
    hpf = None  # type: ignore


def _resolve_device_ids(hpf_mod: Any, device_id_index: int) -> Optional[List[str]]:
    if device_id_index is None or device_id_index < 0:
        return None
    scanned = hpf_mod.Device.scan()
    if not scanned:
        return None
    if device_id_index >= len(scanned):
        raise RuntimeError(
            f"HAILO_DEVICE_ID index {device_id_index} out of range; "
            f"Device.scan() has {len(scanned)} device(s)"
        )
    return [scanned[device_id_index]]


class HailoSharedVDevice:
    """
    One VDevice session for multiple ``HailoSyncInferencer`` instances (two HEFs on one NPU).

    Call :meth:`ensure_open` before creating inferencers; call :meth:`close` after all inferencers
    are torn down.
    """

    def __init__(self, device_id_index: int = 0):
        if hpf is None:
            raise RuntimeError(
                "hailo_platform not importable. On Raspberry Pi: sudo apt install hailo-all "
                "and use the system Python or venv with access to /usr/lib/python3/dist-packages."
            )
        self._hpf = hpf
        self._device_id_index = device_id_index
        self._vd: Any = None

    def ensure_open(self) -> Any:
        if self._vd is not None:
            return self._vd
        p = self._hpf
        params = p.VDevice.create_params()
        params.scheduling_algorithm = p.HailoSchedulingAlgorithm.ROUND_ROBIN
        params.group_id = "SHARED"
        device_ids = _resolve_device_ids(p, self._device_id_index)
        self._vd = p.VDevice(params, device_ids=device_ids)
        self._vd.__enter__()
        return self._vd

    def close(self) -> None:
        if self._vd is not None:
            try:
                self._vd.__exit__(None, None, None)
            except Exception:
                pass
            self._vd = None


class HailoSyncInferencer:
    """One HEF on a VDevice (owned or shared); blocking inference through ConfiguredInferModel."""

    def __init__(
        self,
        hef_path: str,
        stream_interface: str = "integrated",
        device_id_index: int = 0,
        vdevice: Any = None,
    ):
        """
        Args:
            hef_path: Path to ``.hef`` file.
            stream_interface: Kept for API compatibility; unused with InferModel.
            device_id_index: Used only when ``vdevice`` is None (this inferencer creates the VDevice).
            vdevice: Optional opened ``VDevice`` from :class:`HailoSharedVDevice` for multi-model use.
        """
        if hpf is None:
            raise RuntimeError(
                "hailo_platform not importable. On Raspberry Pi: sudo apt install hailo-all "
                "and use the system Python or venv with access to /usr/lib/python3/dist-packages."
            )
        self._hpf = hpf
        self._hef_path = hef_path
        self._stream_interface = stream_interface
        self._device_id_index = device_id_index
        self._external_vdevice = vdevice

        self._vdevice: Any = None
        self._owns_vdevice = False
        self._infer_model: Any = None
        self._config_ctx: Any = None
        self._configured_model: Any = None

    def open(self) -> None:
        hpf = self._hpf
        if self._external_vdevice is not None:
            self._vdevice = self._external_vdevice
            self._owns_vdevice = False
        else:
            params = hpf.VDevice.create_params()
            params.scheduling_algorithm = hpf.HailoSchedulingAlgorithm.ROUND_ROBIN
            params.group_id = "SHARED"
            device_ids = _resolve_device_ids(hpf, self._device_id_index)
            self._vdevice = hpf.VDevice(params, device_ids=device_ids)
            self._vdevice.__enter__()
            self._owns_vdevice = True

        infer = self._vdevice.create_infer_model(self._hef_path)
        infer.set_batch_size(1)
        for name in infer.input_names:
            infer.input(name).set_format_type(hpf.FormatType.FLOAT32)
        for name in infer.output_names:
            infer.output(name).set_format_type(hpf.FormatType.FLOAT32)

        self._infer_model = infer
        self._config_ctx = infer.configure()
        self._configured_model = self._config_ctx.__enter__()

    def close(self) -> None:
        if self._config_ctx is not None:
            try:
                self._config_ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._config_ctx = None
            self._configured_model = None
            self._infer_model = None
        if self._owns_vdevice and self._vdevice is not None:
            try:
                self._vdevice.__exit__(None, None, None)
            except Exception:
                pass
        self._vdevice = None
        self._owns_vdevice = False

    def __enter__(self) -> "HailoSyncInferencer":
        self.open()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @property
    def input_names(self) -> List[str]:
        if self._infer_model is None:
            raise RuntimeError("Hailo inferencer not open; call open() first.")
        return list(self._infer_model.input_names)

    @property
    def output_names(self) -> List[str]:
        if self._infer_model is None:
            raise RuntimeError("Hailo inferencer not open; call open() first.")
        return list(self._infer_model.output_names)

    def infer(self, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """
        inputs: stream name -> float32 tensor; 3D NHWC images get a batch dimension if needed.
        """
        if self._configured_model is None or self._infer_model is None:
            raise RuntimeError("Hailo inferencer not open; call open() or use context manager.")

        infer = self._infer_model
        cfg = self._configured_model

        output_buffers: Dict[str, np.ndarray] = {}
        for name in infer.output_names:
            shp = infer.output(name).shape
            output_buffers[name] = np.empty(shp, dtype=np.float32)

        bindings = cfg.create_bindings(output_buffers=output_buffers)

        for in_name, arr in inputs.items():
            arr = np.asarray(arr, dtype=np.float32)
            if arr.ndim == 3:
                arr = np.expand_dims(arr, axis=0)
            if not arr.flags.c_contiguous:
                arr = np.ascontiguousarray(arr)
            bindings.input(in_name).set_buffer(arr)

        cfg.wait_for_async_ready(timeout_ms=10_000, frames_count=1)
        cfg.run([bindings], 60_000)
        return {name: output_buffers[name] for name in output_buffers}
