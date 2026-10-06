# Evolve review

Separate session. Read-only. Do not edit, commit, push, or apply. Last line is exactly `VERDICT: PASS` or `VERDICT: FAIL`.

- The diff has no secret, key, `.env`, or PEM.
- The diff does not add an owner allowlist entry or change the model provider.
- The change fixes the backlog class, not a one-off symptom.
- `shibaclaw evolve check` is the merge gate. `NOT_RUN` does not replace ruff, pytest, or green pull-request CI.
- The branch is `evolve/*`, not the default branch. The default branch was not pushed.

Any miss → `VERDICT: FAIL` and one line why.
