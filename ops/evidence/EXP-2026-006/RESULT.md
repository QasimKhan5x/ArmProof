# EXP-2026-006 Result: Rejected

EXP-2026-006 exited with status 2 and is not accepted evidence. The fail-closed
analysis found zero valid traffic mixes.

The first clean 500-second confirmation passed at 0.22 requests/s for the
disabled control and 0.28 requests/s for the enabled treatment. Each subsequent
overload window left inference work running after client timeouts. That queued
work contaminated later windows: disabled pass confirmations fell as low as
1/110 accepted, and enabled pass p95 rose from 2.34 seconds to 42.08 seconds.

This is a lifecycle-isolation defect in the experiment harness. It does not
establish either a positive or negative sustained-capacity result. EXP-2026-007
corrects the defect by restarting and warming the measured service before every
window while retaining the original acceptance thresholds.

## Audit artifacts

- `evidence.tar.gz`: SHA-256 `3f8841fdb1e9747998676f50aae7d1fecd4a97cb3811754890b9e11eca4ea54b`
- `project.tar.gz`: SHA-256 `8850427bd356dae56b2709abcb41e860d484cd66203768f44eb921f2e4e80a51`
- Session cost: `$2.4516`
- Cumulative project cost: `$6.3205`
- AWS cleanup: complete; instance terminated
