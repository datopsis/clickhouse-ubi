#!/usr/bin/env bash
# Resolve both target architectures using a native UBI resolver; no emulation.
set -Eeuo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
runtime=${CONTAINER_RUNTIME:-podman}
output=${1:-${root}/artifacts/rpm-lock.json}
if [[ $# -gt 1 || ${output} == --help ]]; then
    echo 'Usage: CONTAINER_RUNTIME=podman|docker scripts/update-rpm-lock.sh [output.json]'
    exit 1
fi
case "${runtime}" in podman|docker) ;; *) echo 'Use podman or docker' >&2; exit 1 ;; esac
case "$(uname -m)" in
    x86_64) resolver_architecture=amd64 ;;
    aarch64|arm64) resolver_architecture=arm64 ;;
    *) echo 'Unsupported resolver host architecture' >&2; exit 1 ;;
esac
minimal_image=$(PYTHONPATH="${root}/scripts/lib" python3 -c \
    'import sys; from rpm_lock import base_images; print(base_images(sys.argv[1])["builder"])' "${root}")
workdir=$(mktemp -d)
image="localhost/clickhouse-rpm-resolver:$(basename "${workdir}" | tr '[:upper:]' '[:lower:]')"
container=''
cleanup() {
    if [[ -n ${container} ]]; then "${runtime}" rm --force "${container}" >/dev/null; fi
    "${runtime}" rmi "${image}" >/dev/null 2>&1 || true
    rm -rf -- "${workdir}"
}
trap cleanup EXIT
cp "${root}/Containerfile" "${workdir}/Containerfile.input"
cp "${root}"/scripts/lib/{rpm_lock,resolve_rpm_lock,ubi_repos}.py "${workdir}/"
cat > "${workdir}/Containerfile" <<EOF
# Always execute the resolver natively, including when resolving foreign RPMs.
FROM --platform=linux/${resolver_architecture} ${minimal_image}
RUN microdnf install -y dnf && microdnf clean all
COPY rpm_lock.py resolve_rpm_lock.py ubi_repos.py /resolver/
COPY Containerfile.input /inputs/Containerfile
RUN python3 /resolver/resolve_rpm_lock.py --root /inputs --output /rpm-lock.json
EOF
options=()
if [[ ${runtime} == podman ]]; then options+=(--format docker); fi
"${runtime}" build --no-cache "${options[@]}" --file "${workdir}/Containerfile" --tag "${image}" "${workdir}"
container=$("${runtime}" create "${image}" /bin/true)
"${runtime}" cp "${container}:/rpm-lock.json" "${workdir}/rpm-lock.json"
# Validate before replacing the destination; a failed resolve leaves it intact.
python3 "${root}/.github/scripts/check_artifact_lock.py" --lock "${workdir}/rpm-lock.json"
mkdir -p -- "$(dirname -- "${output}")"
cp "${workdir}/rpm-lock.json" "${output}"
echo "Proposed lock: ${output} (review before committing)"
