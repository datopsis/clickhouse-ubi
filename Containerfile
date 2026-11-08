# syntax=docker/dockerfile:1.7

ARG UBI_MINIMAL_IMAGE="registry.access.redhat.com/ubi9/ubi-minimal:9.8@sha256:4b79c93106c14ad1c234907f83441ff0e4f8d24e78426a36e159098e9f7e6fa5"
ARG UBI_MICRO_IMAGE="registry.access.redhat.com/ubi9/ubi-micro:9.8@sha256:6d9eff186ce3ccf399c1835265e7fd3f83bd112cc3422da2d39fd44e234aab59"

FROM ${UBI_MINIMAL_IMAGE} AS builder

ARG CLICKHOUSE_VERSION="26.8.2.7"
ARG CLICKHOUSE_CHANNEL="stable"
ARG TARGETARCH

WORKDIR /tmp/clickhouse

# Build a small runtime overlay for UBI Micro and verify every ClickHouse archive
# against the SHA-512 file published beside it by ClickHouse. The TGZs preserve
# release-archive UID/GID 1000; installed programs are normalized to root while
# only explicitly writable runtime paths are assigned to 101:0.
# hadolint ignore=DL3041
RUN microdnf install -y dnf gzip tar \
    && mkdir -p /runtime \
    && dnf install -y \
        --installroot=/runtime \
        --releasever=9 \
        --setopt=install_weak_deps=0 \
        --setopt=keepcache=0 \
        bash ca-certificates coreutils-single gzip tzdata \
    && dnf clean all \
    && microdnf clean all \
    && arch="${TARGETARCH:-}" \
    && if [ -z "${arch}" ]; then \
         case "$(uname -m)" in \
           x86_64) arch=amd64 ;; \
           aarch64) arch=arm64 ;; \
           *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;; \
         esac; \
       fi \
    && case "${arch}" in amd64|arm64) ;; *) echo "Unsupported TARGETARCH: ${arch}" >&2; exit 1 ;; esac \
    && for package in clickhouse-common-static clickhouse-server clickhouse-client; do \
         archive="${package}-${CLICKHOUSE_VERSION}-${arch}.tgz"; \
         curl --fail --location --proto '=https' --tlsv1.2 \
           --retry 5 --retry-delay 2 --retry-all-errors \
           --output "${archive}" \
           "https://packages.clickhouse.com/tgz/${CLICKHOUSE_CHANNEL}/${archive}"; \
         curl --fail --location --proto '=https' --tlsv1.2 \
           --retry 5 --retry-delay 2 --retry-all-errors \
           --output "${archive}.sha512" \
           "https://packages.clickhouse.com/tgz/${CLICKHOUSE_CHANNEL}/${archive}.sha512"; \
         sha512sum --check "${archive}.sha512"; \
         tar --extract --gzip --file "${archive}" --strip-components=1 --directory /runtime; \
       done \
    && rm -rf /runtime/install /runtime/var/cache/dnf /runtime/var/log/* \
    && chown -R 0:0 /runtime/usr \
    && printf 'clickhouse:x:101:0:ClickHouse server:/var/lib/clickhouse:/sbin/nologin\n' >> /runtime/etc/passwd \
    && mkdir -p \
         /runtime/docker-entrypoint-initdb.d \
         /runtime/etc/clickhouse-server/config.d \
         /runtime/etc/clickhouse-server/users.d \
         /runtime/var/lib/clickhouse \
         /runtime/var/log/clickhouse-server \
    && chown -R 101:0 \
         /runtime/docker-entrypoint-initdb.d \
         /runtime/etc/clickhouse-server \
         /runtime/var/lib/clickhouse \
         /runtime/var/log/clickhouse-server \
    && chmod -R g=u \
         /runtime/docker-entrypoint-initdb.d \
         /runtime/etc/clickhouse-server \
         /runtime/var/lib/clickhouse \
         /runtime/var/log/clickhouse-server

FROM ${UBI_MICRO_IMAGE}

ARG CLICKHOUSE_VERSION="26.8.2.7"

LABEL org.opencontainers.image.title="ClickHouse Server on Red Hat UBI 9" \
      org.opencontainers.image.description="A minimal, non-root ClickHouse Server image built on Red Hat UBI 9 Micro" \
      org.opencontainers.image.source="https://github.com/datopsis/clickhouse-ubi" \
      org.opencontainers.image.documentation="https://github.com/datopsis/clickhouse-ubi#readme" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="Datopsis" \
      org.opencontainers.image.version="${CLICKHOUSE_VERSION}"

COPY --from=builder /runtime/usr/ /usr/
COPY --from=builder /runtime/etc/ /etc/
COPY --from=builder /runtime/var/ /var/
COPY --from=builder /runtime/docker-entrypoint-initdb.d/ /docker-entrypoint-initdb.d/
COPY --chown=0:0 --chmod=0755 container/entrypoint.sh /usr/local/bin/clickhouse-entrypoint
COPY --chown=0:0 --chmod=0444 container/health-client.xml /usr/local/share/clickhouse-health-client.xml
COPY --chown=0:0 --chmod=0644 container/config.d/container.xml /etc/clickhouse-server/config.d/container.xml

ENV LANG="C.UTF-8" \
    TZ="UTC" \
    CLICKHOUSE_CONFIG="/etc/clickhouse-server/config.xml"

USER 101:0
WORKDIR /var/lib/clickhouse

EXPOSE 8123 9000 9009
VOLUME ["/var/lib/clickhouse"]

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD ["/usr/local/bin/clickhouse-entrypoint", "healthcheck"]

ENTRYPOINT ["/usr/local/bin/clickhouse-entrypoint"]
CMD []
