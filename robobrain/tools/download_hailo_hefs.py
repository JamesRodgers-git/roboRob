#!/usr/bin/env python3
"""Download STDC1 and StereoNet .hef files for Hailo-10H (model zoo git + S3). Requires git and network."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from src.perception.hailo_model_zoo_fetch import (  # noqa: E402
    default_clone_dir,
    ensure_hef_from_docs,
)


def _parse_args() -> argparse.Namespace:
    epilog = """Examples (from robobrain repo root; default family is HAILO10H from config):
  python tools/download_hailo_hefs.py
  python tools/download_hailo_hefs.py --dest ~/Downloads --force
  python tools/download_hailo_hefs.py --family HAILO8L   # Hailo-8 / 8L silicon only"""
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    p.add_argument(
        "--dest",
        default="",
        metavar="DIR",
        help="Write stdc1.hef and stereonet.hef here (default: paths from config.py)",
    )
    p.add_argument(
        "--family",
        default="",
        help="Docs family, e.g. HAILO10H, HAILO8L (default: config.HAILO_MODEL_ZOO_DOCS_FAMILY)",
    )
    p.add_argument(
        "--clone-path",
        default="",
        metavar="DIR",
        help="Model zoo git clone cache (default: ~/.cache/robobrain/hailo_model_zoo or config)",
    )
    p.add_argument("--git-url", default="", help="Override model zoo git URL")
    p.add_argument("--git-ref", default="", help="Git branch/ref (default: config or master)")
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-download even when the .hef file already exists",
    )
    p.add_argument("--no-stdc1", action="store_true", help="Only fetch stereonet.hef")
    p.add_argument("--no-stereonet", action="store_true", help="Only fetch stdc1.hef")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    docs_family = args.family or getattr(config, "HAILO_MODEL_ZOO_DOCS_FAMILY", "HAILO10H")
    git_url = args.git_url or getattr(
        config, "HAILO_MODEL_ZOO_GIT_URL", "https://github.com/hailo-ai/hailo_model_zoo.git"
    )
    git_ref = args.git_ref or getattr(config, "HAILO_MODEL_ZOO_GIT_REF", "master")
    clone_raw = args.clone_path or getattr(config, "HAILO_MODEL_ZOO_CLONE_PATH", "") or ""
    clone_path = (
        Path(os.path.expanduser(clone_raw)).resolve() if clone_raw else default_clone_dir()
    )

    dest_dir = Path(os.path.expanduser(args.dest)).resolve() if args.dest else None
    if dest_dir is not None:
        stdc1_path = str(dest_dir / "stdc1.hef")
        stereonet_path = str(dest_dir / "stereonet.hef")
    else:
        stdc1_path = os.path.expanduser(getattr(config, "HAILO_STDC1_HEF", "") or "")
        stereonet_path = os.path.expanduser(getattr(config, "HAILO_STEREONET_HEF", "") or "")

    if not args.no_stdc1 and not stdc1_path:
        logging.error("STDC1 output path is empty; set HAILO_STDC1_HEF or use --dest DIR")
        return 1
    if not args.no_stereonet and not stereonet_path:
        logging.error("StereoNet output path is empty; set HAILO_STEREONET_HEF or use --dest DIR")
        return 1

    if args.no_stdc1 and args.no_stereonet:
        logging.error("Nothing to download (--no-stdc1 and --no-stereonet)")
        return 1

    logging.info("Docs family: %s", docs_family)
    logging.info("Clone: %s", clone_path)

    try:
        if not args.no_stdc1:
            ensure_hef_from_docs(
                stdc1_path,
                anchor_prefix="stdc1",
                hef_basename="stdc1.hef",
                category_rst="semantic_segmentation",
                clone_path=clone_path,
                docs_family=docs_family,
                git_url=git_url,
                git_ref=git_ref,
                force=args.force,
            )
            logging.info("STDC1 HEF -> %s", os.path.abspath(os.path.expanduser(stdc1_path)))
        if not args.no_stereonet:
            ensure_hef_from_docs(
                stereonet_path,
                anchor_prefix="stereonet",
                hef_basename="stereonet.hef",
                category_rst="stereo_depth_estimation",
                clone_path=clone_path,
                docs_family=docs_family,
                git_url=git_url,
                git_ref=git_ref,
                force=args.force,
            )
            logging.info("StereoNet HEF -> %s", os.path.abspath(os.path.expanduser(stereonet_path)))
    except Exception as e:
        logging.error("%s", e)
        return 1
    logging.info("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
