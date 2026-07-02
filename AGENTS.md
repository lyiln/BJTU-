# Project Agent Hooks

This file is the project-level coordination hook for AI coding agents working in this repository.

## Pre-Task Hook

Before starting any substantive task in this repository:

1. Read `docs/architecture/current-state.md`.
2. Use it to understand the current app shape, recent fixes, known risks, and open questions.
3. If the document is missing, stale, or conflicts with source code, treat source code as authoritative and note the mismatch before proceeding.

For tiny requests that only ask for repository metadata, such as `git status` or the current commit, reading the document is optional.

## Post-Task Hook

After completing any task that changes code, tests, user-facing behavior, API shape, data flow, database logic, dependencies, commands, or operational assumptions:

1. Update `docs/architecture/current-state.md` in the same turn.
2. Record the new confirmed state with file-level evidence.
3. Add or update risks and open questions when the task reveals them.
4. Do not claim runtime facts that were not verified.

If the task only changes documentation, update the current-state document when the documentation changes what future agents need to know.

## Current Project Notes

- The app is a local BJTU room finder with a FastAPI backend and static frontend.
- The source-of-truth handoff document is `docs/architecture/current-state.md`.
- After backend Python changes, the running `bjtu-rooms` service must be restarted because the default CLI starts uvicorn with `reload=False`.
