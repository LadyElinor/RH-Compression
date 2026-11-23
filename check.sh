#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

version=$(lake env lean --version)
echo "$version"
[[ "$version" == *"version 4.36.0,"*"611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"* ]]
sed 's/simpa \[cpt\]/simpa [GlobalTheory.PlaceInt.cpt]/' reproduction/Before.lean |
    diff -u - reproduction/After.lean
lake build +Contributions:olean

diagnostics=$(mktemp)
trap 'rm -f "$diagnostics"' EXIT
if lake env lean reproduction/Before.lean > "$diagnostics" 2>&1; then
    echo "The unqualified proof unexpectedly compiled." >&2
    exit 1
fi
cat "$diagnostics"
grep -Eq '^reproduction/Before\.lean:[0-9]+:[0-9]+: error: Invalid simp theorem: Expected a proposition' "$diagnostics"
grep -Fq '↥(Sp A)' "$diagnostics"

lake build +After:olean
lake env leanchecker --verbose Contributions
lake env leanchecker --verbose After
printf '%s\n' 'import After' '#print axioms GlobalTheory.SplitKernel.regression_constantCoeff_mem' |
    lake env lean --stdin > "$diagnostics"
cat "$diagnostics"
grep -Fxq "'GlobalTheory.SplitKernel.regression_constantCoeff_mem' depends on axioms: [propext, Classical.choice, Quot.sound]" "$diagnostics"
echo 'PASS: reproduced the collision, compiled the repair, and replayed the reduced theorem.'
