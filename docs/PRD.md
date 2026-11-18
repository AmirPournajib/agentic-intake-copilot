# Product brief: Agentic Intake Copilot

A one-page PRD (Product Requirements Document) for the reference build in this repo.

## Problem

Clinic front desks read every intake form and message by hand. Forms arrive half filled, the useful details sit in a free-text message, and an urgent case can wait in the same queue as a routine checkup.

## Users

| User | Job to be done |
|---|---|
| Front desk | Book the right visit fast, without retyping details |
| Clinician | Read a two-line summary before the visit |
| Patient | Get a slot without a phone call, and a call back fast when it matters |

## What the copilot does

1. **Extract** missing fields from the free-text message.
2. **Validate** the form with plain rules (required fields, phone, date of birth, consent).
3. **Triage** with tools: red-flag check, department routing, next open slots.
4. **Summarize** for the clinician.
5. **Gate**: send the case to a person when it is urgent, has form issues, or the model is not confident.

## Guardrails (non-negotiable)

- Red flags are detected by code, not by the model, so a prompt or a model change cannot hide them.
- Every urgent case goes to a person. The system never auto-books an urgent case.
- The model can only return symptom names from the knowledge base. Anything else is dropped.
- Form values entered by the patient always win over values the model extracts.
- Every step is written to a trace, so any decision can be explained.

## Success metrics

| Metric | Target | Why |
|---|---|---|
| Urgent recall | 100% | Missing an urgent case is the worst failure. CI (Continuous Integration) fails below this. |
| Priority accuracy | 90% or more | Right queue, right time |
| Routing accuracy | 90% or more | Right department on the first try |
| Human review rate | Track, then lower | Shows how much work the copilot really takes off the desk |
| Time to first contact for urgent cases | Under 15 minutes | Measured in a pilot, not in this repo |

## Out of scope for this build

- Diagnosis or medical advice
- Real patient data (all cases here are synthetic)
- EHR (Electronic Health Record) integration

## Rollout plan

1. Shadow mode: the copilot runs next to the front desk, people decide, compare results.
2. Assist mode: the copilot pre-fills and suggests, people confirm.
3. Partial automation: routine, complete, high-confidence cases auto-book. Everything else stays with a person.

Move to the next stage only when the eval set and the shadow-mode numbers both meet the targets above.
