# SkillSpector with a gate that fails on any un-baselined finding.
#
# Pinned twice: the tag names the release a person reviewed, and the commit
# is what is installed, so a moved tag upstream cannot change what gates a
# merge. Bump both together (the upstream workflow does this).
FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 AS builder
ARG SKILLSPECTOR_VERSION=v2.13.0
ARG SKILLSPECTOR_COMMIT=091a509b3d6ba8ff5be528966e1f43c2e68cf214
RUN apt-get update \
    && apt-get install --no-install-recommends -y git \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/skillspector \
    && /opt/skillspector/bin/pip install --no-cache-dir \
       "skillspector @ git+https://github.com/NVIDIA/SkillSpector.git@${SKILLSPECTOR_COMMIT}"

FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70
ARG SKILLSPECTOR_VERSION=v2.13.0
ARG SKILLSPECTOR_COMMIT=091a509b3d6ba8ff5be528966e1f43c2e68cf214
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
