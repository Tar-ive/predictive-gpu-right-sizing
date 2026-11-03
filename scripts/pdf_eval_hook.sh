#!/usr/bin/env bash
# Claude Code PostToolUse hook: after a Bash call that compiles LaTeX, run the PDF layout evals.
# Fails (decision: block) when any eval fails, so the layout problem is fed back before moving on.
cmd=$(jq -r '.tool_input.command // ""')
case "$cmd" in
  *tectonic*|*latexmk*|*pdflatex*|*xelatex*|*lualatex*) ;;
  *) exit 0 ;;
esac
case "$cmd" in *check_pdf.py*) exit 0 ;; esac   # the eval script already ran
root="$(cd "$(dirname "$0")/.." && pwd)"
out=$(cd "$root" && uv run -q --with pymupdf python -W ignore scripts/check_pdf.py --no-build 2>&1)
status=$?
if [ $status -ne 0 ]; then
  jq -n --arg r "PDF layout eval FAILED after compiling LaTeX. Fix before continuing, then view the screenshots in build/screens/.
$out" '{decision: "block", reason: $r}'
else
  jq -n --arg c "PDF layout eval passed. Check the figure pages by eye in build/screens/.
$out" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $c}}'
fi
exit 0
