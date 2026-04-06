"""
Integration: load STDC1 + Stereonet the same way as `brain.py` (two Hailo inferencers).

Skips when `hailo_platform` is missing, HEF paths are unset, or HEF files are absent.
Set ``ROBOBRAIN_TEST_HAILO_FETCH=1`` to allow auto-fetch (git + S3) like production.
"""
from __future__ import annotations

import os

import pytest

import config
from src.perception.heads.segmentation_stdc1 import SegmentationStdc1Head
from src.perception.heads.stereo_stereonet import StereoStereonetHead
from src.perception.hailo_model_zoo_fetch import ensure_hailo_hefs_from_config
from src.perception.pipeline import PerceptionPipeline


@pytest.mark.integration
def test_hailo_models_pipeline_setup_teardown():
    pytest.importorskip("hailo_platform")
    if not getattr(config, "USE_HAILO", False):
        pytest.skip("USE_HAILO is False")

    if not (getattr(config, "HAILO_STDC1_HEF", "") and getattr(config, "HAILO_STEREONET_HEF", "")):
        pytest.skip("HAILO_STDC1_HEF / HAILO_STEREONET_HEF not set")

    fetch = os.environ.get("ROBOBRAIN_TEST_HAILO_FETCH", "").lower() in ("1", "true", "yes")
    old_auto = config.HAILO_AUTO_FETCH_HEFS
    config.HAILO_AUTO_FETCH_HEFS = fetch
    try:
        seg_path, stereo_path = ensure_hailo_hefs_from_config(config)
        if not fetch:
            if not os.path.isfile(seg_path) or not os.path.isfile(stereo_path):
                pytest.skip(
                    "HEF files missing; add them or run with ROBOBRAIN_TEST_HAILO_FETCH=1 "
                    "(network + git required)"
                )

        pipeline = PerceptionPipeline.from_config(config)
        assert any(isinstance(h, SegmentationStdc1Head) for h in pipeline.heads), (
            "expected SegmentationStdc1Head; got stubs — check HEF paths and USE_HAILO"
        )
        assert any(isinstance(h, StereoStereonetHead) for h in pipeline.heads), (
            "expected StereoStereonetHead; got stubs — check HEF paths and USE_HAILO"
        )

        pipeline.setup()
        try:
            stdc1 = next(h for h in pipeline.heads if isinstance(h, SegmentationStdc1Head))
            stereo = next(h for h in pipeline.heads if isinstance(h, StereoStereonetHead))
            assert stdc1._infer is not None
            assert stereo._infer is not None
        finally:
            pipeline.teardown()
    finally:
        config.HAILO_AUTO_FETCH_HEFS = old_auto
