#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
lake env bash <<'CHECK'
set -euo pipefail
version=$(lean --version)
echo "$version"
[[ "$version" == *"version 4.36.0,"*"611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"* ]]
case_dir=hermitian-rewrite
sed 's/GlobalTheory.SW.Base.herm_one/GlobalTheory.GenusSelfDual.herm_one/' "$case_dir/CastBefore.lean" |
    diff -u - "$case_dir/CastAfter.lean"

scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
export LEAN_PATH="$scratch:$LEAN_PATH"
lean --root="$case_dir" -o "$scratch/HermForms.olean" "$case_dir/HermForms.lean"
if lean --root="$case_dir" "$case_dir/CastBefore.lean" > "$scratch/before.log" 2>&1; then
    echo "The expanded rewrite unexpectedly compiled." >&2
    exit 1
fi
cat "$scratch/before.log"
grep -Fq 'CastBefore.lean:11:24: error: invalid `▸` notation' "$scratch/before.log"
grep -Fxq '  IsIntegral ℤ (∑ i, x i * cc (y i))' "$scratch/before.log"
grep -Fxq '  ↑a = stdForm x y' "$scratch/before.log"

lean --root="$case_dir" -o "$scratch/CastAfter.olean" "$case_dir/CastAfter.lean"
leanchecker --verbose HermForms
leanchecker --verbose CastAfter
printf '%s\n' 'import CastAfter' '#print axioms witness_iff_integral' |
    lean --stdin > "$scratch/axioms.log"
cat "$scratch/axioms.log"
grep -Fxq "'witness_iff_integral' depends on axioms: [propext, Classical.choice, Quot.sound]" "$scratch/axioms.log"
echo 'PASS: reproduced the cast failure and kernel-replayed the repaired integrality step.'
CHECK
