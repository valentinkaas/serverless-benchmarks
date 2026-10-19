#!/usr/bin/env python3
"""Lock the Node.js dependencies of every benchmark for every deployment.

npm has no optional dependency groups, so each deployment gets its own install
specification in `nodejs/locks/<deployment>/`: a package.json that merges the
benchmark's package.json with the deployment's `packages` in configs/systems.json,
and the package-lock.json locking it. SeBS installs both unchanged.

    tools/lock_nodejs_benchmarks.py            # lock new and changed dependencies
    tools/lock_nodejs_benchmarks.py --upgrade  # also upgrade all packages within their ranges
    tools/lock_nodejs_benchmarks.py --check    # fail if a lockfile is stale (CI)
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEMS = json.loads((ROOT / "configs" / "systems.json").read_text())
PACKAGES = {
    deployment: config["languages"]["nodejs"]["deployment"]["packages"]
    for deployment, config in sorted(SYSTEMS.items())
    if "nodejs" in config.get("languages", {})
}


def lock(package_json: str, locks: Path, upgrade: bool) -> dict[str, str]:
    """Return package.json and its lockfile, reusing the locked versions unless upgrading."""
    with tempfile.TemporaryDirectory() as tmp:
        # npm records the directory name in the lockfile; keep it stable.
        work = Path(tmp) / "function"
        work.mkdir()
        (work / "package.json").write_text(package_json)
        if (locks / "package-lock.json").exists() and not upgrade:
            shutil.copy(locks / "package-lock.json", work)
        subprocess.run(
            [
                "npm",
                "install",
                "--package-lock-only",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
            ],
            cwd=work,
            check=True,
            capture_output=True,
        )
        return {
            "package.json": package_json,
            "package-lock.json": (work / "package-lock.json").read_text(),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--upgrade", action="store_true", help="upgrade all packages")
    mode.add_argument("--check", action="store_true", help="only verify that lockfiles are current")
    args = parser.parse_args()

    jobs = []
    for package_file in sorted(ROOT.glob("benchmarks/[0-9]*/*/nodejs/package.json")):
        benchmark = json.loads(package_file.read_text())
        for deployment, packages in PACKAGES.items():
            name = f"{package_file.parent.parent.relative_to(ROOT / 'benchmarks')} ({deployment})"
            package_json = {
                **benchmark,
                "dependencies": {**benchmark.get("dependencies", {}), **packages},
            }
            locks = package_file.parent / "locks" / deployment
            jobs.append((name, json.dumps(package_json, indent=2) + "\n", locks))

    def run(job):
        name, package_json, locks = job
        try:
            return lock(package_json, locks, args.upgrade)
        except subprocess.CalledProcessError as e:
            print(f"{name}: npm failed:\n{e.stderr.decode()}", file=sys.stderr)
            return None

    # npm spends most of its time waiting on the registry; lock the combinations in parallel.
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, jobs))

    failed = []
    for (name, _, locks), files in zip(jobs, results):
        print(name)
        if files is None:
            failed.append(name)
        elif args.check:
            if any(
                not (locks / file).exists() or (locks / file).read_text() != content
                for file, content in files.items()
            ):
                print(f"{name}: lockfile is missing or stale", file=sys.stderr)
                failed.append(name)
        else:
            locks.mkdir(parents=True, exist_ok=True)
            for file, content in files.items():
                (locks / file).write_text(content)

    if failed:
        print("failed: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
