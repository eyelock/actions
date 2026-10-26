# SkillSpector with a gate that fails on any un-baselined finding.
#
# Pinned twice: the tag names the release a person reviewed, and the commit
# is what is installed, so a moved tag upstream cannot change what gates a
# merge. Bump both together (the upstream workflow does this).
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS builder
ARG SKILLSPECTOR_VERSION=v2.13.1
ARG SKILLSPECTOR_COMMIT=f3b25697d76256998ca9d42c198d256258d4c035
RUN apt-get update \
    && apt-get install --no-install-recommends -y git \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/skillspector \
    && /opt/skillspector/bin/pip install --no-cache-dir \
       "skillspector @ git+https://github.com/NVIDIA/SkillSpector.git@${SKILLSPECTOR_COMMIT}"

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
ARG SKILLSPECTOR_VERSION=v2.13.1
ARG SKILLSPECTOR_COMMIT=f3b25697d76256998ca9d42c198d256258d4c035
LABEL org.opencontainers.image.source="https://github.com/eyelock/actions" \
      org.opencontainers.image.description="NVIDIA SkillSpector with a gate that fails on any un-baselined finding" \
      org.opencontainers.image.licenses="MIT" \
      io.github.eyelock.skillspector.version="${SKILLSPECTOR_VERSION}" \
      io.github.eyelock.skillspector.commit="${SKILLSPECTOR_COMMIT}"

# git: SkillSpector can scan a repository URL.
RUN apt-get update \
    && apt-get install --no-install-recommends -y git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/skillspector /opt/skillspector
COPY gate.py /opt/skillspector-gate/gate.py
COPY entrypoint.sh /usr/local/bin/entrypoint

ENV PATH="/opt/skillspector/bin:$PATH" \
    SKILLSPECTOR_VERSION="${SKILLSPECTOR_VERSION}"
WORKDIR /scan
ENTRYPOINT ["entrypoint"]
CMD ["gate", "."]
