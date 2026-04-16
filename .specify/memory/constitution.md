<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- Template Principle 1 -> I. Document-Driven Planning
- Template Principle 2 -> II. Spec and Plan Before Build
- Template Principle 3 -> III. End-to-End Traceability
- Template Principle 4 -> IV. Pilot Execution Control
- Template Principle 5 -> V. Evidence-Based Delivery
Added sections:
- Required Artifacts
- Workflow and Quality Gates
Removed sections:
- None
Templates requiring updates:
- ✅ updated .specify/templates/plan-template.md
- ✅ updated .specify/templates/spec-template.md
- ✅ updated .specify/templates/tasks-template.md
- ✅ updated README.md
- ⚠ pending .specify/templates/commands/*.md (directory not present in this repo)
Follow-up TODOs:
- None
-->
# TCI Constitution

## Core Principles

### I. Document-Driven Planning
Every change MUST begin by translating planning input into concrete design
artifacts. Raw requests, meeting notes, and planning documents are not
implementation-ready on their own; they MUST be refined into explicit scope,
user flows, requirements, assumptions, and acceptance criteria before coding.
This rule exists so TCI can treat planning as a durable design input rather
than an informal prompt.

### II. Spec and Plan Before Build
Specification and implementation planning MUST be fixed before implementation
starts. A feature MUST have an approved `spec.md` and `plan.md`, and any task
generation MUST remain consistent with those artifacts. If implementation
reveals a material gap, the team MUST amend the spec or plan first and only
then resume coding. This rule is non-negotiable because TCI optimizes for
design clarity over premature execution.

### III. End-to-End Traceability
Every material change MUST be traceable from source planning input through
specification, plan, task breakdown, and implementation evidence. Specs and
plans MUST reference upstream inputs, tasks MUST reference the user story or
requirement they satisfy, and delivery evidence MUST allow reviewers to
reconstruct why a change exists. This rule exists to preserve auditability,
review quality, and historical learning.

### IV. Pilot Execution Control
During the initial pilot, the implement stage MUST NOT auto-run. Entering
implementation requires an explicit human approval after reviewing the spec,
plan, and task set. Any workflow, script, or automation that would implicitly
trigger `/speckit.implement` or an equivalent execution phase is out of policy
for the pilot. This rule exists to keep governance tight while the workflow is
still being validated.

### V. Evidence-Based Delivery
Completion claims MUST be backed by explicit evidence. Plans MUST define how
success will be verified, tasks MUST identify validation activity, and delivery
records MUST capture the checks that confirm the documented scope was met.
Teams MAY deliver incrementally, but they MUST not treat undocumented or
unverified work as complete. This rule exists so TCI can compare intent against
outcome at every stage.

## Required Artifacts

Each feature or process change MUST maintain the following minimum artifacts:

- A planning input reference that identifies the originating request, brief, or
  source document.
- A `spec.md` that captures user journeys, requirements, edge cases, success
  criteria, and assumptions.
- A `plan.md` that captures the technical context, constitution checks,
  structure decisions, and validation approach.
- A `tasks.md` that maps work items to specific user stories or requirements and
  preserves file-level traceability.
- Delivery evidence, such as test results, review notes, demos, or linked diff
  history, sufficient to verify that the planned work was actually completed.

If one of these artifacts is intentionally deferred, the deferral MUST be
documented with rationale and explicit approval in the relevant upstream
artifact.

## Workflow and Quality Gates

TCI work MUST pass the following gates in order:

1. Planning input is captured and linked.
2. Specification is drafted, reviewed, and fixed for the current scope.
3. Implementation plan is drafted and passes the constitution check.
4. Tasks are generated from the fixed spec and plan.
5. Implementation starts only after explicit human approval.
6. Delivery is closed only after evidence is attached to the completed scope.

The following operational rules also apply:

- A plan or task list MUST NOT introduce scope that is absent from the approved
  specification without first amending that specification.
- If a requirement changes mid-stream, the updated trace MUST show the prior
  state, the new state, and the reason for the amendment.
- Pilot-phase automation MAY assist with drafting, analysis, and task
  generation, but it MUST NOT bypass the manual approval gate for
  implementation.

## Governance

This constitution supersedes local workflow habits when they conflict. All plan
reviews, task reviews, and implementation approvals MUST check compliance with
these principles.

Amendments require:

- A documented rationale describing what changed and why.
- Updates to any affected templates, guidance files, or workflow documents in
  the same change where practical.
- A semantic version update for the constitution itself.

Versioning policy:

- MAJOR: Removes or materially redefines a governance principle or gate.
- MINOR: Adds a new principle, section, or mandatory workflow constraint.
- PATCH: Clarifies wording or improves guidance without changing governance
  meaning.

Compliance review expectations:

- Every new `plan.md` MUST record how it satisfies the constitution check.
- Every generated `tasks.md` MUST preserve traceability to the approved scope.
- Any proposal to enable automatic implementation in the pilot MUST be treated
  as a constitution amendment, not a local exception.

**Version**: 1.0.0 | **Ratified**: 2026-04-16 | **Last Amended**: 2026-04-16
