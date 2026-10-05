#!/bin/bash
# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.

DIR=$1
VERBOSE=$2
TARGET_ARCHITECTURE=$3

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

set -euo pipefail

# Static ffmpeg build (https://github.com/wader/static-ffmpeg), pinned by digest
# of the multi-arch index so that every deployment gets the exact same binary.
FFMPEG_IMAGE="mwader/static-ffmpeg:7.0.2@sha256:d9b22f65c2049d73bf8ae556bb4c5c7d45e9fb85939d87951ed98f22b0f19105"

# SeBS calls the x86_64 architecture "x64", Docker calls it "amd64".
DOCKER_ARCH="${TARGET_ARCHITECTURE}"
if [[ "${DOCKER_ARCH}" == "x64" ]]; then
    DOCKER_ARCH="amd64"
fi

docker build --quiet --platform "linux/${DOCKER_ARCH}" \
    --output "type=local,dest=${DIR}/ffmpeg" - <<EOF
FROM scratch
COPY --from=${FFMPEG_IMAGE} /ffmpeg /ffmpeg
EOF

# Sanity check - avoid issues where extraction silently fails.
if [ ! -x "${DIR}/ffmpeg/ffmpeg" ]; then
    echo "ERROR: ffmpeg binary missing after packaging" >&2
    exit 1
fi

# copy watermark
cp -r "${SCRIPT_DIR}/resources" "${DIR}"
