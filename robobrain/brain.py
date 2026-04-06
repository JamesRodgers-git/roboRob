#!/usr/bin/env python3
import logging
import os
import time

import config
from src.camera_rig import DualCameraRig
from src.movement_client import MovementClient
from src.perception.heads.segmentation_stdc1 import SegmentationStdc1Head
from src.perception.heads.stereo_stereonet import StereoStereonetHead
from src.perception.heads.stub_segmentation import StubSegmentationHead
from src.perception.heads.stub_stereo import StubStereoHead
from src.perception.pipeline import PerceptionPipeline, steer_from_map

LOGGER = logging.getLogger("robobrain")


def _configure_logging() -> None:
    env_level = os.environ.get("ROBOBRAIN_LOG_LEVEL", "").strip().upper()
    name = env_level or (getattr(config, "LOG_LEVEL", "INFO") or "INFO")
    level = getattr(logging, name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class RoboBrain:
    """
    Scaffolding entry point for Pi 5 inference and movement requests.
    """

    def __init__(self):
        self.camera_rig = DualCameraRig(
            left_index=int(getattr(config, "CAMERA_LEFT_INDEX", 0)),
            right_index=int(getattr(config, "CAMERA_RIGHT_INDEX", 1)),
            width=config.CAMERA_WIDTH,
            height=config.CAMERA_HEIGHT,
            fps=config.CAMERA_FPS,
            left_path=getattr(config, "CAMERA_LEFT_PATH", "") or "",
            right_path=getattr(config, "CAMERA_RIGHT_PATH", "") or "",
            backend=str(getattr(config, "CAMERA_BACKEND", "auto") or "auto"),
            picamera_left=int(getattr(config, "CAMERA_PICAMERA_LEFT", 0)),
            picamera_right=int(getattr(config, "CAMERA_PICAMERA_RIGHT", 1)),
        )
        self.movement_client = MovementClient(
            port=config.MOVEMENT_SERIAL_PORT,
            baudrate=config.MOVEMENT_SERIAL_BAUD_RATE,
        )
        self.running = False

    def _decide_movement(self, bundle):
        """Return throttle and turn in [-1.0, 1.0] from perception bundle."""
        if getattr(config, "REQUIRE_DEPTH_FOR_MOTION", False) and not bundle.traversability.used_depth:
            return 0.0, 0.0
        if getattr(config, "AI_STEER_ENABLE", False):
            return steer_from_map(bundle.traversability)
        return config.DEFAULT_THROTTLE, config.DEFAULT_TURN

    def _log_startup(self, pipeline: PerceptionPipeline) -> None:
        LOGGER.info(
            "Config: CONTROL_LOOP_HZ=%s AI_STEER_ENABLE=%s REQUIRE_DEPTH_FOR_MOTION=%s USE_HAILO=%s",
            config.CONTROL_LOOP_HZ,
            getattr(config, "AI_STEER_ENABLE", False),
            getattr(config, "REQUIRE_DEPTH_FOR_MOTION", False),
            getattr(config, "USE_HAILO", False),
        )
        LOGGER.info(
            "Cameras: left=%r right=%r (%dx%d @ %d fps) — %s",
            self.camera_rig.left_source,
            self.camera_rig.right_source,
            self.camera_rig.width,
            self.camera_rig.height,
            self.camera_rig.fps,
            self.camera_rig.capture_kind,
        )
        LOGGER.info(
            "Serial: port=%r baud=%s",
            config.MOVEMENT_SERIAL_PORT,
            config.MOVEMENT_SERIAL_BAUD_RATE,
        )
        kinds = []
        for h in pipeline.heads:
            if isinstance(h, SegmentationStdc1Head):
                kinds.append("segmentation[hailo-stdc1]")
            elif isinstance(h, StubSegmentationHead):
                kinds.append("segmentation[stub]")
            elif isinstance(h, StereoStereonetHead):
                kinds.append("stereo[hailo-stereonet]")
            elif isinstance(h, StubStereoHead):
                kinds.append("stereo[stub]")
            else:
                kinds.append(getattr(h, "name", type(h).__name__))
        LOGGER.info("Perception heads: %s", " → ".join(kinds))
        if pipeline._hailo_shared is not None:
            LOGGER.info("Hailo: shared VDevice for multiple HEFs")

    def run(self) -> None:
        _configure_logging()
        LOGGER.info("RoboBrain starting")

        pipeline = PerceptionPipeline.from_config(config)
        loop_delay = 1.0 / max(1, config.CONTROL_LOOP_HZ)
        status_interval = float(getattr(config, "BRAIN_STATUS_INTERVAL_S", 2.0) or 2.0)

        last_status = time.monotonic()
        loop_count = 0
        frame_failures = 0
        serial_fail_streak = 0

        try:
            LOGGER.info("Loading perception pipeline…")
            pipeline.setup()
            self._log_startup(pipeline)

            LOGGER.info("Starting cameras…")
            self.camera_rig.start()
            LOGGER.info("Starting movement client thread…")
            self.movement_client.start()

            self.running = True
            LOGGER.info("Main loop running (target period %.3fs)", loop_delay)

            while self.running:
                loop_count += 1
                frame_pair = self.camera_rig.read()
                if frame_pair is None:
                    frame_failures += 1
                    if frame_failures == 1:
                        LOGGER.warning("Camera read failed (no frame); sending zero command")
                    elif frame_failures % 60 == 0:
                        LOGGER.warning(
                            "Still no camera frames (%d consecutive reads)",
                            frame_failures,
                        )
                    self.movement_client.send_command(0.0, 0.0, source="robobrain-no-frame")
                    time.sleep(loop_delay)
                    continue

                if frame_failures > 0:
                    LOGGER.info("Camera OK again after %d bad read(s)", frame_failures)
                    frame_failures = 0

                bundle = pipeline.process(frame_pair)
                throttle, turn = self._decide_movement(bundle)
                sent = self.movement_client.send_command(throttle, turn, source="robobrain-ai")
                if not sent:
                    serial_fail_streak += 1
                    if serial_fail_streak == 1:
                        LOGGER.warning("Movement command not sent (no serial connection?)")
                    elif serial_fail_streak % 40 == 0:
                        LOGGER.warning(
                            "Still cannot send movement commands (%d tries)",
                            serial_fail_streak,
                        )
                else:
                    serial_fail_streak = 0

                now = time.monotonic()
                if now - last_status >= status_interval:
                    dt = now - last_status
                    hz = loop_count / dt if dt > 0 else 0.0
                    loop_count = 0
                    last_status = now

                    t = bundle.traversability
                    st = self.movement_client.get_latest_status()
                    extra = ""
                    if st:
                        extra = (
                            f" | wheels throttle~{st.estimated_throttle:.2f} "
                            f"speed~{st.left_speed_mph:.1f}/{st.right_speed_mph:.1f}mph"
                        )
                    LOGGER.info(
                        "status ~%.1f Hz | trav_roi=%.3f depth=%s | cmd t=%.2f r=%.2f | serial=%s%s",
                        hz,
                        t.mean_score_roi,
                        t.used_depth,
                        throttle,
                        turn,
                        "ok" if sent else "no",
                        extra,
                    )
                    seg_o = bundle.heads.get("segmentation")
                    dep_o = bundle.heads.get("stereo")
                    LOGGER.debug(
                        "heads=%s seg_model=%s stereo_model=%s",
                        list(bundle.heads.keys()),
                        getattr(seg_o, "model_name", None),
                        getattr(dep_o, "model_name", None) if dep_o is not None else None,
                    )

                time.sleep(loop_delay)
        finally:
            LOGGER.info("Shutting down…")
            try:
                self.movement_client.send_command(0.0, 0.0, source="robobrain-stop")
            except Exception:
                pass
            self.movement_client.stop()
            self.camera_rig.stop()
            pipeline.teardown()
            LOGGER.info("RoboBrain stopped")

    def stop(self) -> None:
        self.running = False


def main() -> None:
    _configure_logging()
    brain = RoboBrain()
    try:
        brain.run()
    except KeyboardInterrupt:
        LOGGER.info("Keyboard interrupt — stopping")
        brain.stop()


if __name__ == "__main__":
    main()
