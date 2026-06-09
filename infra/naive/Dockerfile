# Self-built naive client: no official image exists, so we carry a pinned,
# checksum-verified upstream release. glibc base — the Cronet binary won't run on musl.
FROM debian:bookworm-slim AS build
ARG NAIVE_VERSION=v148.0.7778.96-5
ARG NAIVE_ASSET=naiveproxy-v148.0.7778.96-5-linux-x64.tar.xz
ARG NAIVE_SHA256=ca6958dcbbfb7b1b38c55a213dab6927ce3c1417d969b815657513b81fc7352d
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates wget xz-utils \
 && wget -O /tmp/naive.tar.xz \
      "https://github.com/klzgrad/naiveproxy/releases/download/${NAIVE_VERSION}/${NAIVE_ASSET}" \
 && echo "${NAIVE_SHA256}  /tmp/naive.tar.xz" | sha256sum -c - \
 && mkdir -p /tmp/naive \
 && tar -xJf /tmp/naive.tar.xz -C /tmp/naive --strip-components=1 \
 && install -m 0755 /tmp/naive/naive /usr/local/bin/naive

FROM debian:bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/naive /usr/local/bin/naive
ENTRYPOINT ["naive"]
CMD ["/etc/naive/config.json"]
