#!/usr/bin/env python3
import logging
import time

import config
from src.camera_rig import DualCameraRig
from src.movement_client import MovementClient
from src.perception.pipeline import PerceptionPipeline, steer_from_map

LOGGER = logging.getLogger("robobrain")


class RoboBrain:
    """
    Scaffolding entry point for Pi 5 inference and movement requests.
    """

    def __init__(self):
        self.camera_rig = DualCameraRig(
            left_index=config.CAMERA_LEFT_INDEX,
            right_index=config.CAMERA_RIGHT_INDEX,
            width=config.CAMERA_WIDTH,
            height=config.CAMERA_HEIGHT,
            fps=config.CAMERA_FPS,
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

    def run(self) -> None:
        logging.basicConfig(level=logging.INFO)
        pipeline = PerceptionPipeline.from_config(config)
        loop_delay = 1.0 / max(1, config.CONTROL_LOOP_HZ)
        last_log = 0.0
        try:
            pipeline.setup()
            self.camera_rig.start()
            self.movement_client.start()
            self.running = True
            while self.running:
                frame_pair = self.camera_rig.read()
                if frame_pair is None:
                    self.movement_client.send_command(0.0, 0.0, source="robobrain-no-frame")
                    time.sleep(loop_delay)
                    continue

                bundle = pipeline.process(frame_pair)
                now = time.time()
                if now - last_log >= 2.0:
                    last_log = now
                    t = bundle.traversability
                    LOGGER.info(
                        "trav mean_roi=%.3f used_depth=%s heads=%s",
                        t.mean_score_roi,
                        t.used_depth,
                        list(bundle.heads.keys()),
                    )

                throttle, turn = self._decide_movement(bundle)
                self.movement_client.send_command(throttle, turn, source="robobrain-ai")
                time.sleep(loop_delay)
        finally:
            try:
                self.movement_client.send_command(0.0, 0.0, source="robobrain-stop")
            except Exception:
                pass
            self.movement_client.stop()
            self.camera_rig.stop()
            pipeline.teardown()

    def stop(self) -> None:
        self.running = False


def main() -> None:
    brain = RoboBrain()
    try:
        brain.run()
    except KeyboardInterrupt:
        brain.stop()


if __name__ == "__main__":
    main()
