# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""Reproducibility manifest of an experiment run.

The manifest is a JSON document written to `<output_dir>/manifest.json`
at the end of every `benchmark invoke` and `experiment invoke`. It records
what was run: the SeBS source revision, benchmark build provenance, deployed
function configuration, inputs, and the host that drove the experiment.

Collection is passive and best-effort. A probe that fails leaves its value
as `null` and records the reason in the `unavailable` map, keyed by the
dotted path of the missing value. Values that do not apply, such as the
dependencies of a container build, are `null` without an `unavailable` entry.
Collection never fails a run.

Build provenance is collected when a code package is built and stored in the
cache next to the package, so that runs reusing a cached package report the
same provenance. The manifest itself is assembled from end-of-run state.

Function-side environment records are not part of the manifest: wrappers
return them in each invocation's `environment` field, so they are stored
with the invocation results.

The TypedDicts below are the schema; bump SCHEMA_VERSION on incompatible changes.
"""

import datetime
import glob
import hashlib
import json
import os
import platform
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, TypedDict, TypeVar, TYPE_CHECKING

import docker

from sebs.utils import JSONSerializer, get_benchmarks_data_path, get_project_root
from sebs.version import __version__

if TYPE_CHECKING:
    from sebs.benchmark import Benchmark
    from sebs.experiments.config import Config as ExperimentConfig
    from sebs.faas.system import System
    from sebs.sebs import SeBS

SCHEMA_VERSION = 1

T = TypeVar("T")


class Digest(TypedDict):
    sha256: str


class Subject(TypedDict):
    """An artifact identified by its digest, compatible with in-toto subjects."""

    name: str
    digest: Digest


class BuilderImage(TypedDict):
    name: str
    id: str
    repo_digests: List[str]


class Provenance(TypedDict):
    built: str
    artifact: Optional[Subject]
    builder_image: Optional[BuilderImage]
    dependencies: Optional[List[str]]
    unavailable: Dict[str, str]


class Input(TypedDict):
    size: str
    data_revision: Optional[str]
    payload_sha256: str


class BenchmarkEntry(TypedDict):
    name: str
    language: str
    language_version: str
    architecture: str
    variant: str
    system_variant: str
    source: Subject
    provenance: Optional[Provenance]
    inputs: List[Input]


class FunctionEntry(TypedDict):
    name: str
    benchmark: str
    config: Any
    provider: Optional[Dict[str, Any]]
    deployed_artifact_matches: Optional[bool]


class Source(TypedDict):
    revision: Optional[str]
    dirty: Optional[bool]
    diff_sha256: Optional[str]
    data_revision: Optional[str]


class Versions(TypedDict):
    sebs: str
    systems: str
    previous_systems: str


class Host(TypedDict):
    platform: str
    machine: str
    python: str
    docker: Optional[str]


class Deployment(TypedDict):
    name: str
    # Platforms without regions, such as local, report None.
    region: Optional[str]


class Manifest(TypedDict):
    schema_version: int
    created: str
    command: List[str]
    versions: Versions
    source: Source
    host: Host
    deployment: Deployment
    experiment: Dict[str, Any]
    benchmarks: List[BenchmarkEntry]
    functions: List[FunctionEntry]
    unavailable: Dict[str, str]


class Probes:
    """Runs best-effort probes and records why the failed ones are unavailable."""

    def __init__(self) -> None:
        self.unavailable: Dict[str, str] = {}

    def __call__(self, key: str, probe: Callable[[], T]) -> Optional[T]:
        try:
            return probe()
        except Exception as e:
            self.unavailable[key] = f"{type(e).__name__}: {e}"
            return None


def sha256_path(path: str) -> str:
    """SHA-256 of a file, or of a directory's relative paths and file contents."""
    digest = hashlib.sha256()
    if os.path.isfile(path):
        with open(path, "rb") as f:
            digest.update(f.read())
        return digest.hexdigest()
    for root, dirs, files in os.walk(path):
        dirs.sort()
        for file in sorted(files):
            file_path = os.path.join(root, file)
            digest.update(os.path.relpath(file_path, path).encode())
            with open(file_path, "rb") as f:
                digest.update(f.read())
    return digest.hexdigest()


def git(directory: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", directory, *args], capture_output=True, check=True, timeout=10, text=True
    ).stdout


def installed_dependencies(output_dir: str) -> List[str]:
    """Resolved third-party packages in a built code package, as `name==version`.

    Reads package metadata directly from the installed directories, so it works
    without the package manager and regardless of the builder image version.
    """
    deps = []
    site_packages = os.path.join(output_dir, ".python_packages", "lib", "site-packages")
    for metadata in glob.glob(os.path.join(site_packages, "*.dist-info", "METADATA")):
        fields = {}
        with open(metadata, encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    break
                key, _, value = line.partition(":")
                fields[key] = value.strip()
        deps.append(f"{fields['Name']}=={fields['Version']}")
    node_modules = os.path.join(output_dir, "node_modules")
    for package_json in glob.glob(os.path.join(node_modules, "*", "package.json")) + glob.glob(
        os.path.join(node_modules, "@*", "*", "package.json")
    ):
        with open(package_json) as f:
            package = json.load(f)
        deps.append(f"{package['name']}=={package['version']}")
    return sorted(deps)


def build_provenance(
    code_location: Optional[str],
    container_uri: Optional[str],
    builder_image: Optional[str],
    output_dir: str,
    docker_client: docker.client.DockerClient,
) -> Provenance:
    """Collect provenance of a freshly built code package or container.

    Args:
        code_location: Built code package, if any
        container_uri: Built function image, if this is a container deployment
        builder_image: Builder image used to install dependencies, if any
        output_dir: Build directory with installed dependencies
        docker_client: Docker client to resolve image digests
    """
    probe = Probes()

    def artifact() -> Optional[Subject]:
        if container_uri is not None:
            image = docker_client.images.get(container_uri)
            return {"name": container_uri, "digest": {"sha256": image.id.split(":")[-1]}}
        if code_location is not None:
            return {
                "name": os.path.basename(code_location),
                "digest": {"sha256": sha256_path(code_location)},
            }
        return None

    def builder(name: str) -> BuilderImage:
        image = docker_client.images.get(name)
        return {"name": name, "id": image.id, "repo_digests": image.attrs.get("RepoDigests", [])}

    return {
        "built": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "artifact": probe("artifact", artifact),
        "builder_image": (
            probe("builder_image", lambda: builder(builder_image)) if builder_image else None
        ),
        # Container builds install dependencies inside the image.
        "dependencies": (
            probe("dependencies", lambda: installed_dependencies(output_dir))
            if container_uri is None
            else None
        ),
        "unavailable": probe.unavailable,
    }


def collect_source(probe: Probes) -> Source:
    root = str(get_project_root())
    data_dir = str(get_benchmarks_data_path())
    status = probe("source.dirty", lambda: git(root, "status", "--porcelain"))
    return {
        "revision": probe("source.revision", lambda: git(root, "rev-parse", "HEAD").strip()),
        "dirty": bool(status) if status is not None else None,
        "diff_sha256": probe(
            "source.diff_sha256",
            lambda: hashlib.sha256(git(root, "diff", "HEAD").encode()).hexdigest(),
        ),
        "data_revision": probe(
            "source.data_revision", lambda: git(data_dir, "rev-parse", "HEAD").strip()
        ),
    }


def benchmark_entry(benchmark: "Benchmark", data_revision: Optional[str]) -> BenchmarkEntry:
    inputs: List[Input] = [
        {
            "size": size,
            "data_revision": data_revision,
            "payload_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True, cls=JSONSerializer).encode()
            ).hexdigest(),
        }
        for size, payload in benchmark.prepared_inputs.items()
    ]
    return {
        "name": benchmark.benchmark,
        "language": benchmark.language_name,
        "language_version": benchmark.language_version,
        "architecture": benchmark.architecture,
        "variant": benchmark.language_variant,
        "system_variant": benchmark.system_variant.serialize(),
        "source": {"name": benchmark.benchmark, "digest": {"sha256": benchmark.hash}},
        "provenance": benchmark.provenance,
        "inputs": inputs,
    }


def experiment_entry(config: "ExperimentConfig", experiment: Optional[str]) -> Dict[str, Any]:
    """Experiment configuration, keeping only the settings of the experiment that ran.

    Args:
        config: Experiment configuration of the run
        experiment: Name of the experiment, or None for a plain benchmark invocation
    """
    entry = config.serialize()
    entry["experiments"] = (
        {experiment: config.experiment_settings(experiment)} if experiment is not None else {}
    )
    return entry


def build_manifest(
    sebs_client: "SeBS",
    deployment_client: "System",
    experiment_config: "ExperimentConfig",
    experiment: Optional[str],
) -> Manifest:
    """Assemble the manifest from the state at the end of a run.

    Args:
        sebs_client: SeBS client of the run
        deployment_client: Deployment client that created the functions
        experiment_config: Experiment configuration of the run
        experiment: Name of the experiment, or None for a plain benchmark invocation
    """
    probe = Probes()
    source = collect_source(probe)

    benchmarks: Dict[int, "Benchmark"] = {}
    functions: List[FunctionEntry] = []
    for benchmark, function in deployment_client.used_functions:
        benchmarks[id(benchmark)] = benchmark
        provider = probe(
            f"functions.{function.name}.provider",
            lambda: deployment_client.describe_function(function),
        )
        provenance = benchmark.provenance
        artifact = provenance["artifact"] if provenance else None
        provider_digest = provider.get("code_digest") if provider else None
        functions.append(
            {
                "name": function.name,
                "benchmark": benchmark.benchmark,
                "config": function.config,
                "provider": provider,
                "deployed_artifact_matches": (
                    provider_digest == artifact["digest"] if provider_digest and artifact else None
                ),
            }
        )

    docker_version = probe("host.docker", lambda: sebs_client.docker_client.version()["Version"])
    return {
        "schema_version": SCHEMA_VERSION,
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command": sys.argv[1:],
        "versions": {
            "sebs": __version__,
            "systems": sebs_client.config.version(),
            "previous_systems": sebs_client.config.previous_version(),
        },
        "source": source,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "docker": docker_version,
        },
        "deployment": {
            "name": deployment_client.name(),
            "region": deployment_client.config.region or None,
        },
        "experiment": experiment_entry(experiment_config, experiment),
        "benchmarks": [
            benchmark_entry(benchmark, source["data_revision"]) for benchmark in benchmarks.values()
        ],
        "functions": functions,
        "unavailable": probe.unavailable,
    }


def write_manifest(
    output_dir: str,
    sebs_client: "SeBS",
    deployment_client: "System",
    experiment_config: "ExperimentConfig",
    experiment: Optional[str],
) -> str:
    """Write `manifest.json` into the output directory and return its path."""
    manifest = build_manifest(sebs_client, deployment_client, experiment_config, experiment)
    path = os.path.join(output_dir, "manifest.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True, cls=JSONSerializer)
    return path
