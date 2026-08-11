#!/usr/bin/env bash
# Build the backend image and fail if secrets or local key material occur in any layer.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image_tag="${1:-policy-atlas-backend-layer-scan}"
scan_dir="$(mktemp -d)"
image_archive="${scan_dir}/image.tar"
forbidden_pattern='(^|/)\.env[^/]*($|/)|(^|/)\.dev-issuer($|/)|(^|/)[^/]*\.pem$|(^|/)jwks\.json$|(^|/)id_rsa$'
layer_count=0
failed=0

cleanup() {
    rm -rf "${scan_dir}"
}
trap cleanup EXIT

echo "Building backend image: ${image_tag}"
docker build --tag "${image_tag}" "${repo_root}/backend"

echo "Saving image for all-layer scan"
docker save --output "${image_archive}" "${image_tag}"

echo "Scanning every image layer for forbidden paths"
# Legacy docker save layout stores layers as */layer.tar; the containerd image
# store (Docker Desktop default) emits an OCI layout whose layers live under
# blobs/sha256/ as (possibly gzipped) tarballs alongside JSON manifests. Scan
# whichever entries are actually tar archives.
while IFS= read -r layer; do
    listing="$(tar -xOf "${image_archive}" "${layer}" | { gunzip 2>/dev/null || cat; } | tar -tf - 2>/dev/null || true)"
    [[ -z "${listing}" ]] && continue   # JSON manifest/config blob, not a layer
    layer_count=$((layer_count + 1))
    echo "Scanning layer: ${layer}"
    # certifi's bundled public CA bundle is required for HTTPS verification; it
    # is not application key material. Every other PEM path remains forbidden.
    # Public CA trust stores (certifi bundle, Debian's /etc/ssl + shared
    # ca-certificates) are certificates, not key material — everything else
    # matching the pattern stays forbidden.
    matches="$(printf '%s\n' "${listing}" | grep -E "${forbidden_pattern}" | grep -Ev '/certifi/cacert\.pem$|^(etc/ssl/|usr/lib/ssl/|usr/share/ca-certificates/)' || true)"
    if [[ -n "${matches}" ]]; then
        printf 'Forbidden paths in %s:\n%s\n' "${layer}" "${matches}" >&2
        failed=1
    fi
done < <(tar -tf "${image_archive}" | grep -E '(/layer\.tar$|^blobs/sha256/[0-9a-f]+$)')

if [[ "${layer_count}" -eq 0 ]]; then
    echo "ERROR: docker save archive did not contain any layer tarballs." >&2
    exit 1
fi

if [[ "${failed}" -ne 0 ]]; then
    echo "Layer scan: FAILED" >&2
    exit 1
fi

echo "Layer scan: clean (${layer_count} layers scanned)"
