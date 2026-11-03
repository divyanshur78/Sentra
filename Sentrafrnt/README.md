# Sentra – Governed ExpenseClaim Agent (Frontend Demo)

## Run locally

```cmd
npm install
npm run dev
```

Open the local URL printed by Vite.

## Demo portals

- **Employee:** overview and personal expense-claim list.
- **Manager:** approval queue. Approve/reject actions open a required-reason dialog; the reason is retained on the claim in the current browser session.
- **Judge / Evaluator:** evaluation matrix with pass (tick) and fail (cross) controls. Each decision opens a required-justification dialog; saved reasons appear in the matrix.
- **Judge / Evaluator:** red-team lab and audit trail.

The login is a **demo role selector**, not production authentication. Data is held in frontend state and resets on refresh. The app is not yet connected to the team backend, identity provider, database, policy gateway, or immutable audit service. The judge matrix is a configurable demo rubric and must be aligned with the actual hackathon scoring criteria before presentation.
