# SurgeDesk Demo: Three-Minute Recording

## Recording Check

Open `http://127.0.0.1:8765/surgedesk/#triage` after resetting the gateway. The
source chip beside **Route an incoming request** must say **Connected Graviton
gateway**. The header must end with **baseline route selected**, and the
**Serving this request** strip must say **Standard service · KleidiAI off**. Do
not record if any source label says **Local integration fixture**.

Start with the standard lane active and no release audit in this gateway
session. Keep the browser at normal zoom. Use these two messages:

1. `My card was stolen while I am travelling`
2. `My card is about to expire. How do I get a replacement?`

Rehearse the complete connected flow three times before recording. Target
`2:55` and never exceed the three-minute limit.

## Recording Flow

### 0:00-0:30 — Route A Live Inference Request

**Do:** Enter the stolen-card message and click **Compare current route with Arm
candidate**. When both receipts appear, scroll to the routing suggestion and
click **Route ticket**.

**Say:**

> SurgeDesk helps a support operator route banking messages. The standard Phi-4
> service handles this stolen-card request while the Arm candidate receives the
> same message as a shadow request. The two receipts show what each service did,
> and I confirm the displayed support queue. This request checks the connected
> path; the longer tests make the release decision.

### 0:30-0:55 — Recompute The Release

**Do:** Click **Check the Arm optimization**, then click **Recompute release
decision**. Wait for the completed receipt before speaking.

**Say:**

> One request cannot approve a deployment. ArmProof is the reusable optimization
> release gate behind this workflow. It has just rebuilt the longer Graviton
> results from raw capacity requests, model outputs, Arm profiles, and runtime
> tests, then issued this session's release receipt.

### 0:55-1:35 — Show The Three Changes

**Do:** Click **Review the three measured changes** and keep the three stage
cards in view.

**Say:**

> We made three measured changes. First, moving Phi-4 from BF16 to INT4 cut its
> model files 36 percent and peak memory 43 percent. Second, with the model,
> server, workload, threads, and ten-second p95 rule fixed, the standard service
> failed every long window at 0.28 requests per second; KleidiAI passed every
> window at 0.56. That establishes at least twice the capacity. Third, we kept
> KleidiAI active and tuned ONNX Runtime scheduling, transparent huge pages, and
> a configured mimalloc preload. The full recipe passed all five windows at 0.62
> requests per second, or 2,232 messages per hour. The simpler memory recipe
> failed all five.

### 1:35-1:55 — Switch The Gateway

**Do:** Scroll to the end of the measured result and click **Continue to traffic
decision**. Pause on the optimization summary, click **Switch connected gateway
to optimized service**, review the confirmation, then click **Confirm gateway
switch**.

**Say:**

> Performix found no KleidiAI samples in the control and 67 percent in the
> candidate, including I8MM. The gateway rechecks the running model, runtime,
> Arm cores, and release settings, then switches because they still match.

### 1:55-2:25 — Route A New Request

**Do:** Click **Send a request through the optimized service**, enter the
expiring-card message, run it, and click **Route ticket**.

**Say:**

> Now I am sending a different message after the switch. Its receipt identifies
> the optimized I8MM service and the release that authorized it. SurgeDesk still
> leaves the final decision with me, so I confirm the queue shown on screen.

### 2:25-2:55 — Show The Bound Cutover Receipt

**Do:** End on the cutover summary. Leave the technical receipt closed so the
before, after, and release columns remain visible.

**Say:**

> The receipt records the original matched request, the selected gateway route,
> the release check, and this new request. That connects a real support action to
> the measured Arm optimization and the exact service now handling requests.
> ArmProof packages the same release check as a CLI and GitHub Action, so another
> Arm HTTP service can block a release when its measured speed, quality, Arm
> execution, or deployed runtime no longer matches.

Hold the final cutover summary briefly. A clean recording should finish around
`2:55`.

## Visible Checks

- The environment badge says `Connected Graviton gateway`, never `Local integration fixture`.
- The first routed ticket says `Standard service · KleidiAI off`.
- The audit ends on a compact receipt; the measured stages open only when requested.
- The summary shows Performix moving from `0%` to `67.35%` `kai_*` samples.
- The full runtime recipe shows `5/5` passes; the simplification shows `5/5` failures.
- The second ticket says `Optimized service · I8MM + tuned runtime`.
- The ending summary names the matched comparison, post-release request, and verified release receipt; the disclosure contains the exact bound digests.
