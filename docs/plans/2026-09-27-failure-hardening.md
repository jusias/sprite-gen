# Sprite workflow failure hardening

## Scope

- Preserve documented top-level `chroma` extraction settings when `prepare` rebuilds a request.
- Keep correction-loop tests on the active sprite-gen interpreter instead of a global `python3` executable.
- Reject directory inputs to asset tools with a domain-specific message that points run users to `manifest.json` plus `--state`.
- Retain the cross-direction content-scale gate and correction hint added during the Swordsman rerun.

## Out of scope

- `extract --force` remains unsupported because extraction already publishes atomically and replaces its targeted state output.
- PowerShell callers must quote comma-separated option values. Shell tokenization is not reinterpreted inside the Python CLI.
- Generation-quality warnings remain visible; successful extraction does not suppress source pitch or cap diagnostics.

## Checklist

- [x] Add regression tests before each behavior change.
- [x] Implement the smallest SOT change in `prepare` and the shared asset loader.
- [x] Run focused tests for prepare, asset loading, correction loop, and scale inspection.
- [x] Run `git diff --check` and record any unrelated pre-existing failure separately.
