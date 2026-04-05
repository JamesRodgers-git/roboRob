#!/usr/bin/env python3
"""
Stereo calibration for RoboBrain: compute rectification maps from chessboard image pairs.

Capture 20–40 synchronized pairs at the same resolution you use in production, with the
board visible in both cameras. Save images then run:

  python tools/stereo_calibrate.py --left_dir ./captures/left --right_dir ./captures/right -o ./calibration/stereo_rectify.npz

Or paired filenames in one folder:

  name_L.png / name_R.png

Requires: opencv-python, numpy
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

# Allow importing robobrain src when run from repo root or robobrain/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pair_from_side_dirs(left_dir: str, right_dir: str) -> list[tuple[str, str]]:
    left_files = sorted(glob.glob(os.path.join(left_dir, "*")))
    right_files = sorted(glob.glob(os.path.join(right_dir, "*")))
    left_files = [f for f in left_files if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    right_files = [f for f in right_files if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    if len(left_files) != len(right_files):
        raise SystemExit(f"Different file counts: left={len(left_files)} right={len(right_files)}")
    if not left_files:
        raise SystemExit("No images found.")
    return list(zip(left_files, right_files))


def pair_from_single_dir(pairs_dir: str) -> list[tuple[str, str]]:
    left = sorted(glob.glob(os.path.join(pairs_dir, "*_L.png")) + glob.glob(os.path.join(pairs_dir, "*_l.png")))
    pairs = []
    for lp in left:
        base = os.path.basename(lp)
        stem = base.rsplit("_", 1)[0]
        rp_candidates = [
            os.path.join(pairs_dir, f"{stem}_R.png"),
            os.path.join(pairs_dir, f"{stem}_r.png"),
        ]
        rp = next((p for p in rp_candidates if os.path.isfile(p)), None)
        if rp:
            pairs.append((lp, rp))
    if not pairs:
        raise SystemExit(f"No *_L.png / *_R.png pairs in {pairs_dir}")
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description="Stereo chessboard calibration for RoboBrain")
    ap.add_argument("--left_dir", help="Directory of left camera images (same order as right)")
    ap.add_argument("--right_dir", help="Directory of right camera images")
    ap.add_argument("--pairs_dir", help="Single dir with name_L.png / name_R.png")
    ap.add_argument("-o", "--output", required=True, help="Output .npz path")
    ap.add_argument("--board_width", type=int, default=9, help="Inner corners along width")
    ap.add_argument("--board_height", type=int, default=6, help="Inner corners along height")
    ap.add_argument("--square_size_m", type=float, default=0.025, help="Square size in meters")
    args = ap.parse_args()

    if args.pairs_dir:
        pairs = pair_from_single_dir(args.pairs_dir)
    elif args.left_dir and args.right_dir:
        pairs = pair_from_side_dirs(args.left_dir, args.right_dir)
    else:
        ap.error("Provide --pairs_dir OR --left_dir and --right_dir")

    board_size = (args.board_width, args.board_height)
    objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0 : board_size[0], 0 : board_size[1]].T.reshape(-1, 2)
    objp *= args.square_size_m

    objpoints = []
    imgpoints_l = []
    imgpoints_r = []
    image_size = None

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    for lp, rp in pairs:
        im_l = cv2.imread(lp, cv2.IMREAD_COLOR)
        im_r = cv2.imread(rp, cv2.IMREAD_COLOR)
        if im_l is None or im_r is None:
            print(f"Skip unreadable: {lp} {rp}")
            continue
        if im_l.shape != im_r.shape:
            raise SystemExit(f"Shape mismatch: {lp} {im_l.shape} vs {rp} {im_r.shape}")
        gray_l = cv2.cvtColor(im_l, cv2.COLOR_BGR2GRAY)
        gray_r = cv2.cvtColor(im_r, cv2.COLOR_BGR2GRAY)
        if image_size is None:
            image_size = (im_l.shape[1], im_l.shape[0])
        elif (im_l.shape[1], im_l.shape[0]) != image_size:
            raise SystemExit(f"All images must be same size; got {(im_l.shape[1], im_l.shape[0])} vs {image_size}")

        ret_l, corners_l = cv2.findChessboardCorners(gray_l, board_size, None)
        ret_r, corners_r = cv2.findChessboardCorners(gray_r, board_size, None)
        if not (ret_l and ret_r):
            print(f"Skip no board: {os.path.basename(lp)}")
            continue

        corners_l = cv2.cornerSubPix(gray_l, corners_l, (11, 11), (-1, -1), criteria)
        corners_r = cv2.cornerSubPix(gray_r, corners_r, (11, 11), (-1, -1), criteria)

        objpoints.append(objp)
        imgpoints_l.append(corners_l)
        imgpoints_r.append(corners_r)

    if len(objpoints) < 3:
        raise SystemExit(f"Need at least 3 valid pairs; got {len(objpoints)}")

    _, K1, D1, _, _ = cv2.calibrateCamera(objpoints, imgpoints_l, image_size, None, None)
    _, K2, D2, _, _ = cv2.calibrateCamera(objpoints, imgpoints_r, image_size, None, None)
    rms, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(
        objpoints,
        imgpoints_l,
        imgpoints_r,
        K1,
        D1,
        K2,
        D2,
        image_size,
        criteria=criteria,
        flags=cv2.CALIB_FIX_INTRINSIC,
    )

    R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
        K1, D1, K2, D2, image_size, R, T, alpha=0,
    )

    map_x_l, map_y_l = cv2.initUndistortRectifyMap(K1, D1, R1, P1, image_size, cv2.CV_32FC1)
    map_x_r, map_y_r = cv2.initUndistortRectifyMap(K2, D2, R2, P2, image_size, cv2.CV_32FC1)

    from src.perception.calibration import save_stereo_npz

    meta = {
        "board_width": args.board_width,
        "board_height": args.board_height,
        "square_size_m": args.square_size_m,
        "num_pairs": len(objpoints),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    save_stereo_npz(
        args.output,
        map_x_l,
        map_y_l,
        map_x_r,
        map_y_r,
        image_size[0],
        image_size[1],
        roi1,
        roi2,
        Q,
        float(rms),
        meta,
    )

    print(f"OK: saved {args.output}")
    print(f"  RMS reprojection error: {rms:.4f}")
    print(f"  Image size (W,H): {image_size}")
    print(f"  Valid pairs: {len(objpoints)}")
    print(f"  Set config.STEREO_CALIB_NPZ_PATH to this file.")


if __name__ == "__main__":
    main()
