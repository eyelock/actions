#!/bin/sh
# `gate [ROOT] [options]` runs the gate; anything else goes to skillspector,
# so the image also works as a plain scanner: `docker run IMAGE scan ./skill`.
set -eu

case "${1:-}" in
  gate)
    shift
    exec python /opt/skillspector-gate/gate.py "$@"
    ;;
  *)
    exec skillspector "$@"
    ;;
esac
