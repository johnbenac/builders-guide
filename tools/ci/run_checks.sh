#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Runs the delivery checks the pull-request workflow runs, without any workflow system: on your own machine, or on any other
# automation. Usage (from the top folder of the repository):
#
#   tools/ci/run_checks.sh                         check every folder under deliveries/
#   tools/ci/run_checks.sh my-slug other-slug      check these deliveries
#   tools/ci/run_checks.sh --base origin/main      check the deliveries changed since origin/main (what the workflow does)
#   options: --out DIR (default ci-reports; JSON reports and summary.md are written there)
#
# Exit status: 0 no REQUIRED finding, 1 at least one REQUIRED finding or an error. Needs: pip install -r tools/requirements-ci.txt
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python3}" "$here/run_checks.py" "$@"
