# Reproducibility Manifest

Every `sebs benchmark invoke` and `sebs experiment invoke` writes `manifest.json` to the output
directory, next to the results. It records what was run: the SeBS revision, the benchmark source,
how the code package was built, the generated inputs, the deployed functions, and the host that
drove the experiment.

Collection is passive and best-effort and never fails a run.
A value that could not be collected is `null`, and the reason is listed in an `unavailable` map.
A value that does not apply (e.g., the builder image on platforms without one) is `null` without a reason.

The schema is defined by the TypedDicts in `sebs/manifest.py`.
Digests are SHA-256, in the in-toto subject shape `{"name": ..., "digest": {"sha256": ...}}`.

## Example

Produced by a local run of `110.dynamic-html` with the `test` input size:

```json
{
  "benchmarks": [
    {
      "architecture": "x64",
      "inputs": [
        {
          "payload_sha256": "bc9ffbf6ebd87cc1284630800b797aa75e17f6b89ac5e896d288f2e6ee854f95",
          "size": "test"
        }
      ],
      "language": "python",
      "language_version": "3.11",
      "name": "110.dynamic-html",
      "provenance": {
        "artifact": {
          "digest": {
            "sha256": "ff5fc8d4bebbf16d2f8db2d27ee212add8457318bbc55aa2f1f2c944dd2de792"
          },
          "name": "package"
        },
        "builder_image": {
          "id": "sha256:5957f3bb3827fa4d0bda3243445e3c07632ed82860b8af2d9094c17a8b9c73e4",
          "name": "spcleth/serverless-benchmarks:build.local.python.3.11-1.2.1",
          "repo_digests": [
            "spcleth/serverless-benchmarks@sha256:5957f3bb3827fa4d0bda3243445e3c07632ed82860b8af2d9094c17a8b9c73e4"
          ]
        },
        "built": "2026-10-12T09:30:43.062804+00:00",
        "unavailable": {}
      },
      "source": {
        "digest": {
          "sha256": "a34ea0bc411e9838ac2a6734d987c908b1a9e360e48897a0322eb2e545580af5"
        },
        "name": "110.dynamic-html"
      },
      "system_variant": "package",
      "variant": "default"
    }
  ],
  "command": [
    "benchmark",
    "invoke",
    "110.dynamic-html",
    "test",
    "--config",
    "/tmp/sebs-local.json",
    "--deployment",
    "local",
    "--output-dir",
    "/tmp/sebs-demo",
    "--cache",
    "/tmp/sebs-demo-cache",
    "--repetitions",
    "3"
  ],
  "created": "2026-10-12T09:30:43.861250+00:00",
  "deployment": {
    "name": "local",
    "region": null
  },
  "experiment": {
    "architecture": "x64",
    "download_results": false,
    "experiments": {},
    "flags": {},
    "runtime": {
      "language": "python",
      "language-variant": "default",
      "version": "3.11"
    },
    "system_variant": "package",
    "update_code": false,
    "update_storage": false
  },
  "functions": [
    {
      "benchmark": "110.dynamic-html",
      "config": {
        "architecture": "x64",
        "memory": 128,
        "runtime": {
          "language": "python",
          "language-variant": "default",
          "version": "3.11"
        },
        "timeout": 10
      },
      "deployed_artifact_matches": null,
      "name": "sebd-110.dynamic-html-python-3.11",
      "provider": {
        "code_digest": null,
        "properties": {}
      }
    }
  ],
  "host": {
    "docker": "29.8.1",
    "machine": "x86_64",
    "platform": "Linux-7.2.9-x86_64-with-glibc2.44",
    "python": "3.14.7"
  },
  "schema_version": 1,
  "source": {
    "data_revision": "523644ddee690ea5bedc1201406744380dc47848",
    "diff_sha256": "4716d4da530a8c2032adc300d5d34c1c57e6ada03e51623ce4b1042b5e6cdf42",
    "dirty": true,
    "revision": "85dd6023f813da64625d5fba54e7559f4474b471"
  },
  "unavailable": {},
  "versions": {
    "previous_systems": "1.2.0",
    "sebs": "1.2.1",
    "systems": "1.2.1"
  }
}
```

## Fields

### Top level

| Field            | Description                                                                                                                  |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `schema_version` | Version of the manifest format. Incremented on incompatible changes.                                                         |
| `created`        | When the manifest was written (UTC, ISO 8601).                                                                               |
| `command`        | SeBS command-line arguments of the run.                                                                                      |
| `versions`       | SeBS versions, see [`versions`](#versions).                                                                                  |
| `source`         | State of the SeBS repository, see [`source`](#source).                                                                       |
| `host`           | Machine that drove the experiment, see [`host`](#host).                                                                      |
| `deployment`     | Target platform, see [`deployment`](#deployment).                                                                            |
| `experiment`     | Experiment configuration, see [`experiment`](#experiment).                                                                   |
| `benchmarks`     | One entry per benchmark used in the run, see [`benchmarks[]`](#benchmarks).                                                  |
| `functions`      | One entry per deployed function used in the run, see [`functions[]`](#functions).                                            |
| `unavailable`    | Run-time probes that failed: dotted path of the value mapped to `"ErrorType: message"`. Empty when everything was collected. |

### `versions`

| Field              | Description                                                                                                                                                                                                                |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sebs`             | Version of the SeBS Python package (`sebs/version.py`).                                                                                                                                                                    |
| `systems`          | `SeBS_version` from `configs/systems.json`; determines the tags of the Docker images SeBS uses (the `-1.2.1` suffix).                                                                                                      |
| `previous_systems` | `previous_major_version` from `configs/systems.json`; image tag SeBS falls back to when an image with the current tag is not available. Compare with the tag in `builder_image.name` to see whether the fallback was used. |

### `source`

State of the SeBS repository the run was started from.

| Field           | Description                                                                                                   |
| --------------- | ------------------------------------------------------------------------------------------------------------- |
| `revision`      | Git `HEAD` commit.                                                                                            |
| `dirty`         | Whether there are uncommitted changes, including untracked files.                                             |
| `diff_sha256`   | SHA-256 of `git diff HEAD`. Identifies uncommitted changes to tracked files; untracked files are not covered. |
| `data_revision` | Commit of the `benchmarks-data` submodule, which holds the benchmark input data.                              |

### `host`

| Field      | Description                                          |
| ---------- | ---------------------------------------------------- |
| `platform` | Operating system, kernel, and C library of the host. |
| `machine`  | CPU architecture of the host.                        |
| `python`   | Python version running SeBS.                         |
| `docker`   | Version of the Docker daemon.                        |

### `deployment`

| Field    | Description                                               |
| -------- | --------------------------------------------------------- |
| `name`   | Platform: `aws`, `azure`, `gcp`, `openwhisk`, or `local`. |
| `region` | Cloud region; `null` on platforms without regions.        |

### `experiment`

The `experiments` section of the SeBS configuration.

| Field              | Description                                                                                                         |
| ------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `update_code`      | Whether a rebuild and redeployment of the code was forced.                                                          |
| `update_storage`   | Whether a re-upload of the benchmark input data was forced.                                                         |
| `download_results` | Whether results are downloaded from cloud storage after the run.                                                    |
| `runtime`          | Language, language version, and language variant.                                                                   |
| `flags`            | Free-form feature flags.                                                                                            |
| `architecture`     | Target CPU architecture: `x64` or `arm64`.                                                                          |
| `system_variant`   | Deployment type: `package` (code package) or `container`.                                                           |
| `experiments`      | Settings of the experiment that ran, keyed by its name, e.g., `{"perf-cost": {...}}`. Empty for `benchmark invoke`. |

### `benchmarks[]`

| Field                          | Description                                                                                                                 |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| `name`                         | Benchmark name.                                                                                                             |
| `language`, `language_version` | Language and version of the benchmark implementation.                                                                       |
| `architecture`                 | Target CPU architecture.                                                                                                    |
| `variant`                      | Benchmark implementation variant: `default`, or the name of a variant directory with overlay files or a patch.              |
| `system_variant`               | Deployment type: `package` or `container`.                                                                                  |
| `source`                       | Digest of the benchmark source, see [`source` of a benchmark](#source-of-a-benchmark).                                      |
| `provenance`                   | How the code package was built, see [`provenance`](#provenance). `null` for packages cached before provenance was recorded. |
| `inputs`                       | One entry per prepared input size, see [`inputs[]`](#inputs).                                                               |

#### `source` of a benchmark

SHA-256 over the relative paths and contents of all files that define the code package:
the benchmark's files for the language, the variant overlay or patch, the platform wrappers,
and the wrappers shared by all platforms (`benchmarks/wrappers/common`).
The same hash is the cache key: any change to these files triggers a rebuild.

#### `provenance`

Recorded when the code package is built and stored in the cache next to it.
Runs that reuse a cached package report the provenance of the original build.

| Field           | Description                                                                                                                                                                      |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `built`         | When the package was built (UTC), not when the run happened.                                                                                                                     |
| `artifact`      | What was deployed and its SHA-256: the zip file (e.g., AWS), the package directory hashed over relative paths and contents (local), or the image ID (container deployments).     |
| `builder_image` | Docker image in which dependencies were installed, see [`builder_image`](#builder_image). `null` if the platform has no builder image.                                           |
| `unavailable`   | Build-time probes that failed, in the same format as the top-level `unavailable`.                                                                                                |

#### `builder_image`

SeBS installs dependencies (`pip install`, `npm install`) in a container started from this image,
built on top of the platform's runtime image, so that native extensions match the target
operating system and CPU architecture.

| Field          | Description                                                                                          |
| -------------- | ---------------------------------------------------------------------------------------------------- |
| `name`         | Repository and tag. The tag encodes platform, language, language version, and SeBS image version.    |
| `id`           | Local image ID.                                                                                      |
| `repo_digests` | Registry digests. `docker pull <repo>@sha256:...` fetches exactly this image, even if the tag moved. |

#### `inputs[]`

| Field            | Description                                                                                                                                        |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `size`           | Input size passed to the benchmark's input generator: `test`, `small`, or `large`.                                                                 |
| `payload_sha256` | SHA-256 of the JSON payload sent to the function. The payload contains bucket names, so it can differ between storage instances for the same data. |

### `functions[]`

| Field                       | Description                                                                                                                                                                                                                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `name`                      | Function name on the platform.                                                                                                                                                                                                                                                       |
| `benchmark`                 | Benchmark the function runs.                                                                                                                                                                                                                                                         |
| `config`                    | Function configuration: memory (MB), timeout (s), runtime, architecture. Reflects the configuration at the end of the run.                                                                                                                                                           |
| `provider` | The platform's view of the deployed function, read with read-only API calls: `code_digest` of the deployed code package and the platform-reported `properties`. On AWS: runtime, architectures, memory, timeout, package type, code size, last modification, version, handler, layers (as `name:version`), and the digest of zip packages. Empty on platforms without such an API. |
| `deployed_artifact_matches` | Whether the code digest reported by the platform equals `provenance.artifact`. `false` indicates a stale deployment. `null` when the platform does not report a digest (e.g., local, container deployments).                                                                         |
