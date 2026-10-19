#!/bin/bash
set -e
if [ -f /nvm/nvm.sh ]; then
  . /nvm/nvm.sh
fi
#
cd /mnt/function

# package-lock.json is the benchmark's lockfile for this deployment:
# npm ci installs exactly the locked versions and verifies their integrity hashes.
# Optional platform-specific packages, e.g., prebuilt binaries of sharp,
# are selected for the target architecture through --cpu and --os.
if [ "${TARGET_ARCHITECTURE}" == "arm64" ]; then
        npm ci --omit=dev --cpu=arm64 --os=linux
elif [ "${TARGET_ARCHITECTURE}" = "x64" ]; then
        npm ci --omit=dev --cpu=x64 --os=linux
else
        echo "Unsupported architecture: $TARGET_ARCHITECTURE"
        exit 1
fi
