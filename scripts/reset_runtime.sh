#!/usr/bin/env bash
set -euo pipefail

rm -f runtime/state.json runtime/trust_material.json runtime/operator_config.json
echo "runtime reset"
