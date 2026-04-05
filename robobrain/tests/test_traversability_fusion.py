import numpy as np

from src.perception.fusion.traversability import TraversabilityFusion
from src.perception.types import DepthOutput, SegmentationOutput


def test_fuse_seg_only():
    class_weights = {0: 1.0, 10: 0.0}
    fusion = TraversabilityFusion(class_weights, stride=2, seg_weight=1.0, geom_weight=0.0)
    labels = np.zeros((20, 20), dtype=np.uint8)
    labels[:10] = 10
    seg = SegmentationOutput(labels=labels, source_size_hw=(20, 20))
    out = fusion.fuse(seg, None)
    assert out.scores.shape[0] == 10
    assert out.used_depth is False
    assert 0.0 <= out.mean_score_roi <= 1.0


def test_fuse_with_smooth_disparity():
    class_weights = {0: 1.0}
    fusion = TraversabilityFusion(class_weights, stride=1, seg_weight=0.5, geom_weight=0.5)
    seg = SegmentationOutput(labels=np.zeros((16, 16), dtype=np.uint8), source_size_hw=(16, 16))
    u = np.linspace(0, 1, 16, dtype=np.float32)
    disp = np.outer(np.ones(16, dtype=np.float32), u) * 10.0
    depth = DepthOutput(data=disp, kind="disparity", source_size_hw=(16, 16))
    out = fusion.fuse(seg, depth)
    assert out.used_depth is True
