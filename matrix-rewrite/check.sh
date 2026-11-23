#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
lake env bash <<'CHECK'
set -euo pipefail

version=$(lean --version)
echo "$version"
[[ "$version" == *"version 4.36.0,"*"611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"* ]]
sed 's/rw \[Matrix.dotProduct_mulVec, /rw [/' matrix-rewrite/GramAfter.lean |
    diff -u matrix-rewrite/GramBefore.lean -

scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
export LEAN_PATH="$scratch:$LEAN_PATH"
if lean --root=matrix-rewrite matrix-rewrite/GramBefore.lean > "$scratch/before.log" 2>&1; then
    echo "The original rewrites unexpectedly compiled." >&2
    exit 1
fi
cat "$scratch/before.log"
grep -Fq 'GramBefore.lean:9:6: error: Tactic `rewrite` failed' "$scratch/before.log"
grep -Fq 'GramBefore.lean:13:6: error: Tactic `rewrite` failed' "$scratch/before.log"
grep -Fxq '  c ᵥ* A' "$scratch/before.log"
grep -Fxq '  ?v ᵥ* ?M ᵥ* ?N' "$scratch/before.log"

lean --root=matrix-rewrite -o "$scratch/GramAfter.olean" matrix-rewrite/GramAfter.lean
leanchecker --verbose GramAfter
printf '%s\n' 'import GramAfter' '#print axioms GramRepair.kernel_pairing' '#print axioms GramRepair.inverse_pairing' |
    lean --stdin > "$scratch/axioms.log"
cat "$scratch/axioms.log"
for theorem in kernel_pairing inverse_pairing; do
    grep -Fxq "'GramRepair.$theorem' depends on axioms: [propext, Classical.choice, Quot.sound]" "$scratch/axioms.log"
done
echo 'PASS: both original rewrites failed and both repaired proofs passed kernel replay.'
CHECK
