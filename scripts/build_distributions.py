"""Build/check TalkCompress's frozen stdlib bundles with the parent-owned minpy tool.

Same contract as Aoi's ``scripts/build_distributions.py`` (docs/distributions.md):
the compiler is the parent's ``tools/minpy.py`` at the commit pinned in
``distributions.json``; its SHA-256 is verified before it is imported. Only
stdlib bundles (empty ``allow``) are accepted. ``--check`` never writes.

    uv run python scripts/build_distributions.py           # (re)generate dist/
    uv run python scripts/build_distributions.py --check   # committed dist/ == rebuild

Without ``--minpy`` the pinned tool is fetched once into ``.test-deps/`` (gitignored)
and verified by SHA-256 on every run.
"""
from __future__ import annotations

import argparse, hashlib, importlib.util, json, re, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "talkcompress-distributions/1"
REPOSITORY = "myon-bioinformatics/TalkCompress"
CACHE = ".test-deps"
SHA40 = re.compile("[0-9a-f]{40}")


def git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if out.returncode:
        raise ValueError(out.stderr.strip() or "git failed")
    return out.stdout.strip()


def path(value) -> str:
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or any(ord(c) < 32 for c in value) or value.startswith("/")
            or any(p in ("", ".", "..") for p in value.split("/"))):
        raise ValueError("unsafe relative path")
    return value


def tool_url(tool: dict) -> str:
    return f"https://raw.githubusercontent.com/{tool['repository']}/{tool['commit']}/{path(tool['source'])}"


def fetch_tool(root: Path, tool: dict) -> Path:
    """Download the pinned minpy once into .test-deps/ and verify its SHA-256."""
    if not SHA40.fullmatch(tool.get("commit", "")) or tool.get("repository") != "myon-bioinformatics/myon-bioinformatics":
        raise ValueError("tool must be the parent's tools/minpy.py at a full commit SHA")
    target = root / CACHE / f"minpy-{tool['commit']}.py"
    if not target.is_file():
        with urllib.request.urlopen(tool_url(tool), timeout=30) as resp:  # noqa: S310 (pinned https URL)
            data = resp.read()
        if hashlib.sha256(data).hexdigest() != tool["sha256"]:
            raise ValueError("minpy tool SHA-256 mismatch (download)")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return target


def load_tool(filename: Path, expected: str):
    filename = Path(filename).resolve()
    if hashlib.sha256(filename.read_bytes()).hexdigest() != expected:
        raise ValueError("minpy tool SHA-256 mismatch")
    spec = importlib.util.spec_from_file_location("_talkcompress_distribution_minpy", filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _has_commit(root: Path, sha: str) -> bool:
    return subprocess.run(["git", "-C", str(root), "cat-file", "-e", sha + "^{commit}"],
                          capture_output=True).returncode == 0


def build(root: Path, manifest: dict, tool_path: Path, *, check: bool) -> dict:
    if manifest.get("schema") != SCHEMA:
        raise ValueError("expected " + SCHEMA)
    source = manifest["source"]
    if not isinstance(source, str) or not SHA40.fullmatch(source):
        raise ValueError("source must be a full commit SHA")
    tool = load_tool(tool_path, manifest["tool"]["sha256"])
    if manifest["python"] != f"{sys.version_info.major}.{sys.version_info.minor}":
        raise ValueError("use the Python major.minor recorded in distributions.json")
    license_path = path(manifest["license"])
    projects = manifest["projects"]
    if not isinstance(projects, dict) or not projects:
        raise ValueError("projects must be a nonempty object")
    watched, outputs = [license_path], set()
    for name, item in projects.items():
        if not re.fullmatch("[a-z][a-z0-9_]*", name):
            raise ValueError("invalid project name")
        path(item["entry"])
        if not item["output"].startswith("dist/") or not item["output"].endswith("_min.py"):
            raise ValueError("bundle output must be dist/*_min.py")
        if item["output"].casefold() in outputs:
            raise ValueError("duplicate output")
        outputs.add(item["output"].casefold())
        if not isinstance(item["paths"], list) or not item["paths"]:
            raise ValueError("nonempty source search paths required")
        for search in item["paths"]:
            if search != ".":
                path(search)
        watched.extend([item["entry"], *(path(w) for w in item.get("watch", []))])
    # Source pin: the frozen commit must still match the working tree for every
    # watched file. A shallow checkout (CI) without that commit cannot prove the
    # pin, so it rebuilds from the working tree instead; the byte comparison of
    # the committed bundle still detects any source drift.
    pinned = _has_commit(root, source)
    if pinned:
        if git(root, "diff", "--name-only", source, "--", *watched):
            raise ValueError("distribution source changed; commit it and update the source pin")
        if git(root, "ls-files", "--others", "--exclude-standard", "--", *watched):
            raise ValueError("distribution source contains uncommitted files")
    generated: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="talkcompress-minpy-") as tmp:
        snap = Path(tmp) / "src"
        if pinned:
            subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(root), str(snap)], check=True)
            git(snap, "checkout", "-q", "--detach", source)
        else:
            for rel in sorted(set(watched)):
                (snap / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / rel, snap / rel)
        notice = snap / license_path
        if not notice.is_file() or notice.is_symlink():
            raise ValueError("license must be a regular file in the frozen source")
        generated["dist/LICENSE"] = notice.read_bytes()
        for item in projects.values():
            text = tool.bundle(root=str(snap), entry=item["entry"], repository=REPOSITORY, commit=source,
                               search_paths=item["paths"], skip_head_check=not pinned, require_clean=pinned)
            if tool.parse_header(text)["allow"]:
                raise ValueError("only stdlib distributions are allowed")
            generated[item["output"]] = text.encode("utf-8")
    mismatch = []
    for relative in generated:
        target = root / relative
        if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != root.parent):
            raise ValueError("output must not traverse symlinks")
    for relative, data in generated.items():
        target = root / relative
        if check:
            if not target.is_file() or target.is_symlink() or target.read_bytes() != data:
                mismatch.append(relative)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    if mismatch:
        raise ValueError("distribution mismatch: " + ", ".join(mismatch))
    return {"schema": "talkcompress-distribution-check/1", "source": source, "source_pin_verified": pinned,
            "ok": True, "mode": "check" if check else "build", "files": list(generated)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--minpy", type=Path, help="local copy of the pinned tools/minpy.py (default: fetch into .test-deps/)")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    try:
        manifest = json.loads((root / "distributions.json").read_text(encoding="utf-8"))
        tool_path = args.minpy or fetch_tool(root, manifest["tool"])
        result = build(root, manifest, tool_path, check=args.check)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("distributions: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
