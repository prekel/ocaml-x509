#!/usr/bin/env python3
"""Validate ready-to-copy opam packages without installing them into a switch."""

import argparse
import hashlib
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd, show=True):
    print("+", " ".join(map(str, args)), flush=True)
    result = subprocess.run(list(map(str, args)), cwd=cwd, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=600)
    if show or result.returncode:
        print(result.stdout, end="", flush=True)
    result.check_returncode()
    return result.stdout


def archive(metadata, package):
    url = re.search(r'url\s*\{\s*src:\s*"([^"]+)"', metadata)[1]
    checks = re.findall(r'"(sha256|sha512)=([a-f0-9]+)"',
                       metadata.split("extra-files:")[0])
    assert checks, "Missing archive checksums"
    cache = ROOT / "_build/overlay-validation"
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{package}.tbz"

    def validate(data):
        for algorithm, digest in checks:
            if hashlib.new(algorithm, data).hexdigest() != digest:
                raise ValueError(f"{algorithm} mismatch: {target}")

    if not target.exists():
        algorithm, digest = checks[-1]
        urls = (url, f"https://opam.ocaml.org/cache/{algorithm}/{digest[:2]}/{digest}")
        for source in urls:
            try:
                with urllib.request.urlopen(source, timeout=30) as response:
                    data = response.read()
                validate(data)
                target.write_bytes(data)
                break
            except OSError as error:
                print(f"Download failed: {error}", flush=True)
        else:
            raise RuntimeError("Could not download official archive")
    validate(target.read_bytes())
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", choices=("legacy", "latest", "all"), default="all")
    parser.add_argument("--switch", help="existing switch with build/test dependencies")
    parser.add_argument("--check-only", action="store_true", help="lint and apply only")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not args.check_only and not args.switch:
        parser.error("--switch is required for builds")
    packages = sorted((ROOT / "overlay/packages").glob("*/*/opam"))
    assert len(packages) == 2
    # Versions are sorted numerically, independently of directory name ordering.
    packages.sort(key=lambda p: tuple(map(int, p.parent.name.split(".")[1:])))
    selected = list(zip(("legacy", "latest"), packages))
    prefix = ["opam", "exec", f"--switch={args.switch}", "--"]
    for suite, opam in selected:
        if args.set not in (suite, "all"):
            continue
        package = opam.parent.name
        name = opam.parent.parent.name
        metadata = opam.read_text()
        run("opam", "lint", opam, cwd=ROOT)
        patch_names = re.findall(r'"([^"]+\.patch)"',
                                re.search(r"patches:\s*\[(.*?)\]", metadata, re.S)[1])
        extras = dict(re.findall(r'\["([^"]+\.patch)"\s+"sha256=([a-f0-9]+)"\]', metadata))
        assert set(patch_names) == set(extras)
        for patch in patch_names:
            assert hashlib.sha256((opam.parent / "files" / patch).read_bytes()).hexdigest() == extras[patch]
        with tempfile.TemporaryDirectory(prefix=f"{package}-check-") as tmp:
            work = Path(tmp)
            with tarfile.open(archive(metadata, package)) as tar:
                tar.extractall(work, filter="data")
            roots = list(work.iterdir())
            assert len(roots) == 1 and roots[0].is_dir()
            stage = roots[0]
            for patch in patch_names:
                path = opam.parent / "files" / patch
                output = run("patch", "--dry-run", "--batch", "--fuzz=0", "-p1", "-i", path, cwd=stage)
                assert "offset" not in output.lower() and "fuzz" not in output.lower()
                run("patch", "--batch", "--fuzz=0", "-p1", "-i", path, cwd=stage)
            if args.check_only:
                print(f"PASS {package}: lint, checksums, exact patch application", flush=True)
                continue
            run(*prefix, "dune", "build", "-p", name, "-j", args.jobs, "@install", cwd=stage, show=False)
            if name == "x509":
                run(*prefix, "dune", "runtest", "-p", name, "-j", args.jobs, cwd=stage, show=False)
            tests = stage / "overlay_check"
            shutil.copytree(ROOT / "test_overlay", tests)
            shutil.copyfile(tests / "dune.inc", tests / "dune")
            if (tests / f"{suite}.ml").exists():
                shutil.copyfile(tests / f"{suite}.ml", tests / "compat.ml")
            run(*prefix, "dune", "build", "--profile", "release", "overlay_check/check.exe", cwd=stage, show=False)
            spec = importlib.util.spec_from_file_location("overlay_checks", tests / "check.py")
            checks = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(checks)
            checks.verify(stage, prefix, suite, run)
            print(f"PASS {package}: build and behavioral tests", flush=True)


if __name__ == "__main__":
    main()
