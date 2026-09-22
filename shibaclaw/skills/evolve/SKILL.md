---
name: evolve
description: "Opt-in self-evolution. One backlog class per alarm, evolve/* branch, separate reviewer, pull request on the fork only. Use for /evolve, evolution, self-modify."
---

# Evolve

One alarm tick. Do not edit this skill to skip the gate. Do not commit the default branch. Do not change the model provider. Do not ask the owner between steps. Push the branch only to the fork remote and open the pull request on the fork. Never open a pull request against upstream.

State: `shibaclaw evolve` (`on|off|status|panic|gate|end|note-apply|check`).
Review checklist: the evolve `CHECKLIST.md` next to this file.

## 0. Gate

```bash
shibaclaw evolve gate
```

Non-zero → reply exactly `EVOLVE_SKIP` and stop.

## 1. Fuel

Read `memory/knowledge/patterns.md`, `memory/knowledge/improvement-backlog.md`, and the tail of `memory/DREAM_DIARY.md`.

The same failure twice, and the class is not in patterns yet → append the class and one Open backlog item. Then `shibaclaw evolve end`. Tell the owner one line. Stop.

An Open item exists → take the top one through review or FAIL.
Nothing open and no new class → do not stop. One world topic, section 5.

## 2. Branch

Dirty tree, or `checkout -b evolve/<slug>` failed → `shibaclaw evolve end` and stop.
`<slug>` is the class name: letters, digits, hyphen.

Touch only that class. Do not touch secrets, `.env`, credentials, or the owner allowlist.
A test must pass, or the commit message contains `NOT_RUN:` and why.
Commit on `evolve/<slug>` only. Do not push.

## 3. Reviewer

A different model on the same provider. Do not write config.

```bash
shibaclaw agent --session evolve:reviewer --model <reviewer-model> --no-markdown --logs "Read the evolve CHECKLIST.md. Read git diff <default>...HEAD. Read-only: do not edit, commit, push, or apply. Last line exactly VERDICT: PASS or VERDICT: FAIL."
```

No `VERDICT: PASS` line → record FAIL, leave the item Open, `shibaclaw evolve end`, one line to the owner. The next alarm may take the next item.

## 4. Check

```bash
shibaclaw evolve check --repo <git-repo>
```

Non-zero → `shibaclaw evolve end` and send the reason to the owner. Do not install. Do not restart the process from this turn.

This package does not restart itself. Installing the reviewed commit is the operator's deploy step. After that deploy, `shibaclaw evolve note-apply` counts it against the daily budget (3 applies, 45 minutes between them).

Success of this tick with no deploy → `shibaclaw evolve end`. Reply exactly `EVOLVE_QUIET` when a later deploy step will report. Otherwise one line to the owner.

## 5. World

No code class, or the apply budget is closed. One topic from `USER.md` and `memory/people/` (interests and friction, not raw chats). Do not open a private message archive. Do not message other chats.

Search, then fetch two or three pages. Append `memory/evolution/WORLD.md`: date, whose interest, topic, a few facts, links. Do not rewrite `USER.md` or friend profiles.

At most 16 topics a day, and not again within 30 minutes. Then `shibaclaw evolve end`. One line to the owner if something is new. Otherwise reply exactly `EVOLVE_SKIP`.
