"""
Fetch compiled .hef URLs from a local hailo_model_zoo git clone, then download if missing.

Public-model docs use `` `HEF <url.hef>`_ `` or (HAILO8L) `` `H <url.hef>`_ ``.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

_HEF_LINK_RE = re.compile(r"`(?:HEF|H) <(https://[^>]+\.hef)>`")


def default_clone_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "robobrain" / "hailo_model_zoo"


def _anchor_chunk(rst: str, anchor_prefix: str) -> str:
    pat = re.compile(rf"^\s*\* - {re.escape(anchor_prefix)}", re.MULTILINE)
    m = pat.search(rst)
    if not m:
        raise ValueError(f"No table row for anchor {anchor_prefix!r} in model zoo RST")
    return rst[m.start() : m.start() + 5000]


def hef_url_from_rst(rst: str, anchor_prefix: str, hef_basename: str) -> str:
    chunk = _anchor_chunk(rst, anchor_prefix)
    for lm in _HEF_LINK_RE.finditer(chunk):
        url = lm.group(1)
        if url.endswith(hef_basename):
            return url
    raise ValueError(f"No HEF/H link for {hef_basename!r} near anchor {anchor_prefix!r}")


def _run_git(args: list[str], *, env: dict[str, str], timeout: int) -> None:
    try:
        r = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or "").strip()
        raise RuntimeError(f"git {' '.join(args[1:4])}... failed: {msg or e}") from e


def _ensure_git_clone(git_url: str, clone_path: Path, git_ref: str) -> None:
    clone_path = clone_path.resolve()
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    if (clone_path / ".git").is_dir():
        _run_git(
            ["git", "-C", str(clone_path), "fetch", "--depth", "1", "origin", git_ref],
            env=env,
            timeout=180,
        )
        _run_git(
            ["git", "-C", str(clone_path), "reset", "--hard", f"origin/{git_ref}"],
            env=env,
            timeout=120,
        )
        return
    clone_path.parent.mkdir(parents=True, exist_ok=True)
    if clone_path.exists():
        raise FileExistsError(f"Cannot clone: path exists and is not a git repo: {clone_path}")
    _run_git(
        ["git", "clone", "--depth", "1", "--branch", git_ref, git_url, str(clone_path)],
        env=env,
        timeout=600,
    )


def _download_to(url: str, dest: Path) -> None:
    dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=dest.name + ".", suffix=".part", dir=str(dest.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "robobrain/hailo_model_zoo_fetch"})
        with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as out:
            shutil.copyfileobj(resp, out)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _read_rst(clone_path: Path, docs_family: str, category_rst: str) -> str:
    rst_path = clone_path / "docs" / "public_models" / docs_family / f"{docs_family}_{category_rst}.rst"
    if not rst_path.is_file():
        raise FileNotFoundError(f"Model zoo RST not found: {rst_path}")
    return rst_path.read_text(encoding="utf-8", errors="replace")


def ensure_hef_from_docs(
    local_path: str,
    *,
    anchor_prefix: str,
    hef_basename: str,
    category_rst: str,
    clone_path: Path,
    docs_family: str,
    git_url: str,
    git_ref: str,
    force: bool = False,
) -> None:
    """Clone/update model zoo git if needed, parse RST for HEF URL, download to local_path."""
    dest = Path(os.path.expanduser(local_path)).resolve()
    if dest.is_file() and not force:
        return
    LOGGER.info(
        "Fetching %s -> %s (clone/update model zoo if needed)",
        hef_basename,
        dest,
    )
    _ensure_git_clone(git_url, clone_path, git_ref)
    rst = _read_rst(clone_path, docs_family, category_rst)
    url = hef_url_from_rst(rst, anchor_prefix, hef_basename)
    LOGGER.info("Downloading %s from model zoo docs link", hef_basename)
    try:
        _download_to(url, dest)
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"Failed to download HEF from {url}: {e}") from e


def ensure_hailo_hefs_from_config(cfg: Any) -> tuple[str, str]:
    """
    Expand HEF paths; if HAILO_AUTO_FETCH_HEFS and USE_HAILO, fetch missing files from model zoo git.
    Returns (seg_path_expanded, stereo_path_expanded).
    """
    seg = os.path.expanduser(getattr(cfg, "HAILO_STDC1_HEF", "") or "")
    stereo = os.path.expanduser(getattr(cfg, "HAILO_STEREONET_HEF", "") or "")
    if not getattr(cfg, "USE_HAILO", False):
        return seg, stereo
    if not getattr(cfg, "HAILO_AUTO_FETCH_HEFS", True):
        return seg, stereo

    git_url = getattr(cfg, "HAILO_MODEL_ZOO_GIT_URL", "https://github.com/hailo-ai/hailo_model_zoo.git")
    git_ref = getattr(cfg, "HAILO_MODEL_ZOO_GIT_REF", "master")
    docs_family = getattr(cfg, "HAILO_MODEL_ZOO_DOCS_FAMILY", "HAILO10H")
    clone_raw = getattr(cfg, "HAILO_MODEL_ZOO_CLONE_PATH", "") or ""
    clone_path = Path(os.path.expanduser(clone_raw)).resolve() if clone_raw else default_clone_dir()

    if seg:
        ensure_hef_from_docs(
            seg,
            anchor_prefix="stdc1",
            hef_basename="stdc1.hef",
            category_rst="semantic_segmentation",
            clone_path=clone_path,
            docs_family=docs_family,
            git_url=git_url,
            git_ref=git_ref,
        )
    if stereo:
        ensure_hef_from_docs(
            stereo,
            anchor_prefix="stereonet",
            hef_basename="stereonet.hef",
            category_rst="stereo_depth_estimation",
            clone_path=clone_path,
            docs_family=docs_family,
            git_url=git_url,
            git_ref=git_ref,
        )
    return seg, stereo
