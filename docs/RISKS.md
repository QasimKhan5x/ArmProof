# Risk Register

| ID | Risk | Consequence | Control |
|---|---|---|---|
| R-01 | Direct KleidiAI speedup does not survive concurrent serving | Cloud story fails | Run fixed-SLO gate before UI critical path |
| R-02 | Product becomes a dashboard around one experiment | Low reuse and implementation score | Fail-closed runner, schemas and CI decision are core |
| R-03 | Whole-stack gains are attributed to KleidiAI | Misleading Arm claim | Separate causal scopes in schema and UI |
| R-04 | `kai_*` evidence is missing or too coarse | Arm execution unproven | Required unknown fails; never infer exact microkernel |
| R-05 | Quality sample is too small | Deployment language is not credible | Freeze 500 minimum, 1,000 preferred public examples |
| R-06 | Report and CLI disagree | Trust failure | Both consume one signed-off decision artifact |
| R-07 | Accepted configuration differs from deployment | Reproduction failure | Generate deployment directly from treatment identity |
| R-08 | Profiler changes performance | Invalid benchmark | Profile separately; measure normal collector overhead |
| R-09 | GitHub Action requires unavailable infrastructure | Poor DX | Document self-hosted runner and preserve local CLI path |
| R-10 | Runtime/model breadth expands scope | Incomplete product | One excellent adapter; versioned extension boundary only |
| R-11 | AWS resources or spend escape | Financial/security incident | Approval, least privilege, TTL, tags and cleanup |
| R-12 | External model/data cannot be redistributed | Broken public quickstart | Store manifests/checksums and scripted downloads |
| R-13 | "Proof" implies formal or official certification | Overclaim | Explicit claim boundary in UI and docs |
| R-14 | Superseded context resurfaces | Agent implementation drift | Context validator rejects retired terms in active docs |

## Stop Conditions

Stop and return to the owner when:

- the capacity gate fails;
- a required claim cannot be tied to raw evidence;
- the matched Arm control cannot remain identical;
- public licensing prevents a reproducible reference;
- the cloud cost ceiling must change; or
- a proposed feature changes the approved product objective.
