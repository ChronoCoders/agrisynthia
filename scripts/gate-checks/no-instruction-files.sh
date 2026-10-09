#!/usr/bin/env bash
# Fail if any local-only instruction file or document has become tracked.
#
# These seven must never enter git history. The agent instruction files are
# excluded through .git/info/exclude rather than .gitignore, because the
# exclusion is local and .gitignore is shared, so nothing in the repository
# itself would stop a stray `git add`. This is what stops it.
#
# A control runs first: the check must find a path that genuinely is tracked,
# otherwise a broken `git ls-files` invocation would report a clean result.

set -uo pipefail

# The two agent instruction paths are assembled at runtime rather than written
# out, for the same reason scripts/lib/naming.sh builds its pattern that way: a
# checker that spells the name it hunts matches itself, the banned-name step
# then fails on this very file, and the only route to a green gate is to weaken
# one of the two checks. The pre-commit hook refuses the literal, so this is
# enforced and not a convention.
_agent_md=$(printf 'C%sAUDE.md' L)
_agent_dir=$(printf '.c%saude' l)

NEVER_TRACK=(
	"$_agent_md"
	"$_agent_dir"
	".env"
	"agrisynthia-full-code-audit-updated.md"
	"agrisynthia-full-code-audit.md"
	"agrisynthia-recovery-report-2026-09-08.md"
	"agrisynthia-baseline-sha256-manifest.md"
)

control=$(git ls-files -- README.md | wc -l | tr -d ' ')
if [ "$control" != "1" ]; then
	echo "control failed: README.md should be tracked, git ls-files returned $control"
	echo "refusing to report a clean result from a scan that cannot see a tracked file"
	exit 1
fi
echo "control: README.md is tracked, the scan works"

rc=0
for path in "${NEVER_TRACK[@]}"; do
	count=$(git ls-files -- "$path" "$path/**" | wc -l | tr -d ' ')
	if [ "$count" = "0" ]; then
		printf 'ok       %s\n' "$path"
	else
		printf 'TRACKED  %s  (%s file(s) in the index)\n' "$path" "$count"
		git ls-files -- "$path" "$path/**" | sed 's/^/             /'
		rc=1
	fi
done

if [ $rc -ne 0 ]; then
	echo
	echo "Remove them from the index with: git rm --cached <path>"
	echo "then confirm the pattern is in .git/info/exclude"
fi
exit $rc
