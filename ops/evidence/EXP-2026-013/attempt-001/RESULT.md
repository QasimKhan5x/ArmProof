# EXP-2026-013 Attempt 1: Rejected Before Profiling

The guest exited with status 1 while preparing matched model overlays. A cold
import exposed a circular package dependency between the reference model,
evidence adapter and quality modules. No Arm Performix run was created, so this
archive supplies no profiler evidence and cannot satisfy the preregistered
experiment.

The package boundary was corrected by moving artifact fingerprinting into the
dependency-free `armproof.artifacts` module. A fresh-interpreter regression test
now exercises the same import path before cloud execution.

- Failed archive SHA-256: `89e31dbfb3177df88ef769f5d20419aa45071d7e2a4b349fcaff144130eb1ad0`
- Failed project bundle SHA-256: `dc363738d5881e0e61fac3d946cc51534f313e51d7c7d0866547dcef3654e80b`
- Session cost: `$0.0393`
- AWS cleanup: complete; instance terminated; post-run inventory empty
