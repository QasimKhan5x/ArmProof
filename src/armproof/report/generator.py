"""Generate an offline, evidence-linked ArmProof report."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any, Mapping


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _copy_input(source: Path, destination: Path) -> None:
    if source.resolve() != destination.resolve():
        shutil.copyfile(source, destination)


def _validated_summary_ratios(summary: Mapping[str, Any]) -> dict[str, float]:
    ratios: dict[str, float] = {}
    for name, row in summary["mixes"].items():
        try:
            baseline = float(row["ratio"]["baseline_median"])
            treatment = float(row["ratio"]["treatment_median"])
            ratio = float(row["ratio"]["ratio"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"capacity summary has invalid {name} ratio") from exc
        if not all(math.isfinite(value) and value > 0 for value in (baseline, treatment, ratio)):
            raise ValueError(f"capacity summary has non-positive or non-finite {name} ratio")
        if not math.isclose(ratio, treatment / baseline, rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError(f"capacity summary has inconsistent {name} ratio")
        ratios[name] = ratio
    if not ratios:
        raise ValueError("capacity summary contains no traffic mixes")
    return ratios


def _validate_comparison_summary(
    comparison: Mapping[str, Any] | None,
    summary: Mapping[str, Any],
    ratios: Mapping[str, float],
) -> None:
    if comparison is None:
        return
    metrics = comparison.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("comparison metrics must be an object")
    expected = {
        "minimum_capacity_ratio": min(ratios.values()),
        "throughput_ratio": min(ratios.values()),
        **{f"{name}_capacity_ratio": value for name, value in ratios.items()},
    }
    quality = summary.get("quality_comparison", {})
    if isinstance(quality, dict):
        expected.update({
            "accuracy_delta_pp": quality.get("accuracy_delta_pp"),
            "macro_f1_delta_pp": quality.get("macro_f1_delta_pp"),
            "schema_valid_rate": quality.get("schema_valid_rate"),
        })
    for metric, value in expected.items():
        if metric not in metrics or value is None:
            continue
        observed = metrics[metric]
        if not isinstance(observed, (int, float)) or not math.isclose(
            float(observed), float(value), rel_tol=1e-9, abs_tol=1e-9
        ):
            raise ValueError(f"comparison metric {metric} disagrees with capacity summary")


def generate_report(
    decision_path: Path,
    summary_path: Path,
    output: Path,
    *,
    comparison_path: Path | None = None,
    deployment_summary_path: Path | None = None,
    verification_path: Path | None = None,
) -> Path:
    decision = _object(decision_path)
    summary = _object(summary_path)
    if decision.get("schema_version") != "1.0.0" or not isinstance(decision.get("passed"), bool):
        raise ValueError("decision is not an ArmProof 1.0 artifact")
    if summary.get("schema_version") != "1.0.0" or not isinstance(summary.get("mixes"), dict):
        raise ValueError("summary is not an ArmProof capacity artifact")
    comparison = _object(comparison_path) if comparison_path else None
    ratios = _validated_summary_ratios(summary)
    _validate_comparison_summary(comparison, summary, ratios)
    deployment = _object(deployment_summary_path) if deployment_summary_path else None
    verification = _object(verification_path) if verification_path else None
    if verification is not None:
        primary = verification.get("checksums", {})
        reproduction = verification.get("reproduction_checksums")
        performix = verification.get("performix")
        if (
            verification.get("schema_version") != "1.0.0"
            or verification.get("comparison_source") != "derived_from_raw_evidence"
            or primary.get("passed") is not True
            or not isinstance(primary.get("checked"), int)
            or isinstance(primary.get("checked"), bool)
            or primary["checked"] < 1
            or (
                reproduction is not None
                and (
                    reproduction.get("passed") is not True
                    or not isinstance(reproduction.get("checked"), int)
                    or isinstance(reproduction.get("checked"), bool)
                    or reproduction["checked"] < 1
                )
            )
            or (
                performix is not None
                and (
                    performix.get("passed") is not True
                    or performix.get("internal_checksums", {}).get("passed") is not True
                    or performix.get("disabled", {}).get("kai_sample_share") != 0
                    or not isinstance(
                        performix.get("enabled", {}).get("kai_sample_share"),
                        (int, float),
                    )
                    or performix["enabled"]["kai_sample_share"] <= 0
                )
            )
        ):
            raise ValueError("verification receipt is not a passing raw-evidence receipt")
    if deployment is not None:
        required = {"disk_reduction_percent", "peak_pss_reduction_percent"}
        if deployment.get("schema_version") != "1.0.0" or not required.issubset(
            deployment.get("metrics", {})
        ):
            raise ValueError("deployment summary is not an ArmProof 1.0 artifact")
    payload = {
        "decision": decision,
        "summary": summary,
        "comparison": comparison,
        "deployment": deployment,
        "verification": verification,
        "history": deployment.get("history", []) if deployment else [],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).replace("</", "<\\/")
    output.mkdir(parents=True, exist_ok=True)
    (output / "data.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if comparison_path:
        _copy_input(comparison_path, output / "comparison.json")
    if deployment_summary_path:
        _copy_input(deployment_summary_path, output / "deployment-summary.json")
    if verification_path:
        _copy_input(verification_path, output / "verification.json")
    _copy_input(decision_path, output / "decision.json")
    _copy_input(summary_path, output / "summary.json")
    title = "Verified" if decision["passed"] else "Blocked"
    document = _HTML.replace("{{TITLE}}", title).replace("{{DATA}}", encoded)
    index = output / "index.html"
    index.write_text(document, encoding="utf-8")
    return index


_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>ArmProof - {{TITLE}}</title>
<style>
:root{color-scheme:light;--ink:#182027;--muted:#5d6972;--line:#d9dfe2;--paper:#f7f8f6;--white:#fff;--green:#13795b;--green-soft:#e7f3ed;--cyan:#087e8b;--amber:#a45b00;--amber-soft:#fff1d6;--red:#b42318;--red-soft:#feeceb;--black:#111820}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}button,a{font:inherit}button:focus-visible,a:focus-visible{outline:3px solid #56b4c2;outline-offset:2px}.shell{max-width:1180px;margin:auto;padding:0 28px 64px}.topbar{min-height:64px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}.brand{font-weight:750;font-size:19px;color:var(--black)}.brand span{color:var(--cyan)}.top-actions{display:flex;gap:8px}.button{border:1px solid var(--line);background:var(--white);color:var(--ink);padding:8px 12px;border-radius:5px;text-decoration:none;cursor:pointer}.button:hover{border-color:#9ba6ac}.hero{padding:52px 0 34px;display:grid;grid-template-columns:minmax(0,1.5fr) minmax(260px,.7fr);gap:48px;align-items:end}.eyebrow{font-size:12px;font-weight:750;text-transform:uppercase;color:var(--green);margin-bottom:9px}.hero h1{font-size:clamp(36px,5vw,68px);line-height:1.02;margin:0 0 16px;max-width:850px;letter-spacing:0}.hero p{font-size:18px;color:var(--muted);max-width:720px;margin:0}.decision{border-left:5px solid var(--green);padding:8px 0 8px 18px}.decision strong{display:block;font-size:28px}.decision span{color:var(--muted)}.tabs{display:flex;gap:24px;border-bottom:1px solid var(--line);margin-top:10px}.tab{border:0;border-bottom:3px solid transparent;background:transparent;padding:12px 0 10px;color:var(--muted);cursor:pointer}.tab[aria-selected=true]{border-color:var(--green);color:var(--ink);font-weight:700}.view{padding-top:30px}.view[hidden]{display:none}.metric-band{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);background:var(--white)}.metric{padding:22px;border-right:1px solid var(--line)}.metric:last-child{border-right:0}.metric b{font-size:30px;display:block;line-height:1.1}.metric span{font-size:13px;color:var(--muted)}.section{padding:38px 0;border-bottom:1px solid var(--line)}.section h2{font-size:22px;margin:0 0 6px}.section-lead{color:var(--muted);margin:0 0 24px}.mix-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.mix{background:var(--white);border:1px solid var(--line);border-radius:6px;padding:20px}.mix-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:16px}.mix h3{margin:0;text-transform:capitalize}.ratio{font-size:24px;font-weight:750;color:var(--green)}.bar-row{display:grid;grid-template-columns:72px 1fr 45px;gap:8px;align-items:center;margin:10px 0;font-size:12px}.track{height:12px;background:#e5e8e9}.bar{height:100%;background:#69767d}.bar.enabled{background:var(--green)}.claims{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.claim{display:grid;grid-template-columns:25px 1fr auto;align-items:center;gap:10px;background:var(--white);border:1px solid var(--line);padding:13px 15px;border-radius:5px}.check{width:20px;height:20px;border-radius:50%;display:grid;place-items:center;background:var(--green-soft);color:var(--green);font-weight:800}.check.fail{background:var(--red-soft);color:var(--red)}.check.unknown{background:var(--amber-soft);color:var(--amber)}.claim code{font-size:12px;color:var(--muted)}.scope{display:grid;grid-template-columns:1fr 42px 1fr 42px 1fr;align-items:center}.node{background:var(--white);border:1px solid var(--line);padding:18px;border-radius:5px;min-height:92px}.arrow{text-align:center;font-size:24px;color:var(--cyan)}.timeline{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:0;border:1px solid var(--line);background:var(--white)}.event{padding:18px;border-right:1px solid var(--line)}.event:last-child{border-right:0}.event b,.event span{display:block}.event span{font-size:12px;color:var(--muted)}.status{font-size:11px;font-weight:750;text-transform:uppercase}.status.passed{color:var(--green)}.status.failed{color:var(--red)}.status.inconclusive{color:var(--amber)}.provenance{width:100%;border-collapse:collapse;background:var(--white);border:1px solid var(--line)}.provenance th,.provenance td{text-align:left;padding:12px 14px;border-bottom:1px solid var(--line)}.provenance th{font-size:12px;color:var(--muted)}.provenance code{font-size:11px;overflow-wrap:anywhere}.callout{border-left:4px solid var(--amber);background:#fff7e8;padding:14px 18px;margin-top:20px}.callout.reproduction-note{border-color:var(--green);background:var(--green-soft)}.footer{padding-top:24px;color:var(--muted);font-size:12px;display:flex;justify-content:space-between}@media(max-width:800px){.shell{padding:0 16px 40px}.hero{grid-template-columns:1fr;gap:24px;padding-top:34px}.metric-band,.mix-grid,.timeline{grid-template-columns:1fr}.metric,.event{border-right:0;border-bottom:1px solid var(--line)}.claims{grid-template-columns:1fr}.scope{grid-template-columns:1fr}.arrow{transform:rotate(90deg)}.top-actions .button:not(:last-child){display:none}}
.metric-band{grid-template-columns:repeat(5,1fr)}
</style>
</head>
<body>
<main class="shell">
<nav class="topbar" aria-label="Report actions"><div class="brand">Arm<span>Proof</span></div><div class="top-actions"><a class="button" href="verification.json">Verification receipt</a><a class="button" href="summary.json" download>Download summary</a><a class="button" href="decision.json">Decision JSON</a></div></nav>
<header class="hero"><div><div class="eyebrow">Graviton4 release evidence</div><h1 id="report-headline">Arm-native capacity, proven before merge.</h1><p id="report-lead">A fail-closed release decision for Phi-4 Mini INT4 on ONNX Runtime GenAI, with KleidiAI isolated by a matched control.</p></div><div class="decision"><strong id="decision-title">Verified</strong><span id="decision-subtitle">All required claims passed</span></div></header>
<div class="tabs" role="tablist"><button class="tab" role="tab" aria-selected="true" aria-controls="overview" id="overview-tab">Overview</button><button class="tab" role="tab" aria-selected="false" aria-controls="evidence" id="evidence-tab">Evidence &amp; provenance</button></div>
<section class="view" id="overview" role="tabpanel" aria-labelledby="overview-tab">
  <div class="metric-band"><div class="metric"><b id="min-ratio">--</b><span>minimum fixed-SLO capacity gain</span></div><div class="metric"><b id="arm-cycle-share">--</b><span>cycles in KleidiAI matmul callchain</span></div><div class="metric"><b id="disk-reduction">n/a</b><span>smaller deployment artifact</span></div><div class="metric"><b id="pss-reduction">n/a</b><span>lower peak proportional set size</span></div><div class="metric"><b id="schema-rate">--</b><span>normalized schema validity</span></div></div>
  <div class="section"><h2>Sustainable serving capacity</h2><p class="section-lead">Highest confirmed accepted request rate under the same 10-second p95 SLO. Five pass and five fail boundary confirmations per treatment and mix.</p><div class="mix-grid" id="mixes"></div><div class="callout reproduction-note" id="reproduction-note" hidden></div></div>
  <div class="section" id="deployment-section"><h2>Deployment transformation</h2><p class="section-lead">The reference migration also cuts storage and process memory. These figures compare the complete BF16 and INT4 deployments; they are not attributed to KleidiAI alone.</p><div class="scope"><div class="node"><b>PyTorch BF16</b><br><span>Reference model and runtime deployment</span></div><div class="arrow">&rarr;</div><div class="node"><b>ONNX Runtime GenAI INT4</b><br><span id="deployment-detail"></span></div><div class="arrow">&rarr;</div><div class="node"><b>KleidiAI execution</b><br><span>Matched on/off control proves the Arm-specific capacity gain</span></div></div></div>
  <div class="section"><h2>Merge contract</h2><p class="section-lead">Every required claim is evaluated by the policy engine. Missing evidence becomes unknown and blocks the release.</p><div class="claims" id="claims"></div></div>
  <div class="section"><h2>Causal scope</h2><p class="section-lead">Whole-stack compression gains and Arm-kernel gains are kept separate.</p><div class="scope"><div class="node"><b>Same INT4 artifact</b><br><span>Phi-4 Mini, identical model hash and workload</span></div><div class="arrow">&rarr;</div><div class="node"><b>One control changes</b><br><span><code>mlas.disable_kleidiai</code> switches from 1 to 0</span></div><div class="arrow">&rarr;</div><div class="node"><b>Executed Arm path</b><br><span><code>kai_*</code> callchains only in the enabled profile</span></div></div></div>
</section>
<section class="view" id="evidence" role="tabpanel" aria-labelledby="evidence-tab" hidden>
  <div class="section" id="history-section"><h2>Evidence history</h2><p class="section-lead">Negative and inconclusive experiments remain visible; later runs do not rewrite them.</p><div class="timeline" id="history"></div></div>
  <div class="section"><h2>Authoritative evidence path</h2><p class="section-lead" id="verification-detail">No verification receipt supplied.</p><div class="scope"><div class="node"><b>Verify</b><br><span>SHA-256 ledgers and workload manifest</span></div><div class="arrow">&rarr;</div><div class="node"><b>Derive and bind</b><br><span>Raw metrics plus contract identities</span></div><div class="arrow">&rarr;</div><div class="node"><b>Decide</b><br><span>Fail-closed policy evaluation</span></div></div></div>
  <div class="section" id="performix-section" hidden><h2>Matched Arm Performix attribution</h2><p class="section-lead" id="performix-detail"></p><div class="scope"><div class="node"><b>Control</b><br><span id="performix-disabled"></span></div><div class="arrow">&rarr;</div><div class="node"><b>Treatment</b><br><span id="performix-enabled"></span></div><div class="arrow">&rarr;</div><div class="node"><b>Cross-check</b><br><span id="performix-crosscheck"></span></div></div></div>
  <div class="section"><h2>Artifact identity</h2><table class="provenance"><thead><tr><th>Identity</th><th>SHA-256</th></tr></thead><tbody id="provenance"></tbody></table><div class="callout"><b>Not Arm certification.</b> ArmProof verifies a declared contract from supplied evidence. It does not claim official Arm approval or independently attest the evidence producer.</div></div>
</section>
<footer class="footer"><span>Offline report generated by ArmProof</span><span id="report-context"></span></footer>
</main>
<script id="report-data" type="application/json">{{DATA}}</script>
<script>
const data=JSON.parse(document.getElementById('report-data').textContent);const decision=data.decision,summary=data.summary,comparison=data.comparison,deployment=data.deployment,verification=data.verification;const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const title=document.getElementById('decision-title');title.textContent=decision.passed?'Verified':'Blocked';title.parentElement.style.borderColor=decision.passed?'var(--green)':'var(--red)';document.getElementById('decision-subtitle').textContent=decision.passed?'All required claims passed':'Required claims did not pass';
if(!decision.passed){document.getElementById('report-headline').textContent='Optimization evidence blocked before merge.';document.getElementById('report-lead').textContent='The declared Arm optimization contract did not pass. Review the failed or unknown claims before deploying this treatment.';}
const mixes=document.getElementById('mixes');let ratios=[];for(const [name,row] of Object.entries(summary.mixes)){const base=row.ratio.baseline_median,opt=row.ratio.treatment_median,ratio=row.ratio.ratio;ratios.push(ratio);const max=Math.max(base,opt);const el=document.createElement('article');el.className='mix';el.innerHTML=`<div class="mix-head"><h3>${esc(name)}</h3><span class="ratio">${ratio.toFixed(1)}x</span></div><div class="bar-row"><span>Baseline</span><div class="track"><div class="bar" style="width:${base/max*100}%"></div></div><b>${base.toFixed(2)}</b></div><div class="bar-row"><span>Treatment</span><div class="track"><div class="bar enabled" style="width:${opt/max*100}%"></div></div><b>${opt.toFixed(2)}</b></div>`;mixes.appendChild(el)}if(ratios.length)document.getElementById('min-ratio').textContent=Math.min(...ratios).toFixed(1)+'x';if(summary.quality_comparison)document.getElementById('schema-rate').textContent=(summary.quality_comparison.schema_valid_rate*100).toFixed(0)+'%';
if(comparison&&Number.isFinite(comparison.metrics.enabled_kai_cycle_callchain_share))document.getElementById('arm-cycle-share').textContent=(comparison.metrics.enabled_kai_cycle_callchain_share*100).toFixed(2)+'%';
if(deployment){const disk=deployment.metrics.disk_reduction_percent,pss=deployment.metrics.peak_pss_reduction_percent;document.getElementById('disk-reduction').textContent=disk.toFixed(1)+'%';document.getElementById('pss-reduction').textContent=pss.toFixed(1)+'%';document.getElementById('deployment-detail').textContent=`${disk.toFixed(1)}% less disk and ${pss.toFixed(1)}% lower peak PSS`;if(deployment.reproduction){const note=document.getElementById('reproduction-note');note.textContent=`A fresh-instance confirmation matched all ${deployment.reproduction.mixes_reproduced} tested capacity ratios with ${(deployment.reproduction.maximum_relative_difference*100).toFixed(0)}% relative difference.`;note.hidden=false;}}else{document.getElementById('deployment-section').hidden=true;}
const claims=document.getElementById('claims');for(const row of decision.claims){const el=document.createElement('div');el.className='claim';const symbol=row.status==='pass'?'✓':'!';el.innerHTML=`<span class="check ${esc(row.status)}">${symbol}</span><div><b>${esc(row.claim_id.replaceAll('-',' '))}</b><br><code>${esc(row.reason_code)}</code></div><code>${row.observed===null?'unknown':Number(row.observed).toFixed(2)} / ${Number(row.threshold)}</code>`;claims.appendChild(el)}
const history=document.getElementById('history');for(const row of data.history){const el=document.createElement('div');el.className='event';const status=document.createElement('span');status.className='status';if(['passed','failed','inconclusive'].includes(row.status))status.classList.add(row.status);status.textContent=row.status;const id=document.createElement('b');id.textContent=row.id;const note=document.createElement('span');note.textContent=row.note;el.append(status,id,note);history.appendChild(el)}
if(!data.history.length)document.getElementById('history-section').hidden=true;const experiment=summary.experiment_id||(comparison&&comparison.comparison_id)||'ArmProof comparison';const instance=comparison&&comparison.treatment.controls.instance||'Arm target';document.getElementById('report-context').textContent=`${experiment} / ${instance}`;
if(verification){const profile=verification.performix;const checked=verification.checksums.checked+(verification.reproduction_checksums?verification.reproduction_checksums.checked:0)+(profile?profile.internal_checksums.checked:0);const scope=profile?'capacity, reproduction and native Arm Performix bundles':verification.reproduction_checksums?'primary and fresh-instance confirmation bundles':'the evidence bundle';document.getElementById('verification-detail').textContent=`${checked} files verified across ${scope}. The comparison and decision were derived from bound evidence, not accepted as input.`;if(profile){document.getElementById('performix-section').hidden=false;document.getElementById('performix-detail').textContent=`Arm Performix ${profile.enabled.engine_version} measured matched Code Hotspots runs on ${profile.enabled.cpu_names.join(', ')}.`;document.getElementById('performix-disabled').textContent=`${(profile.disabled.kai_sample_share*100).toFixed(0)}% measured kai_* function samples`;document.getElementById('performix-enabled').textContent=`${(profile.enabled.kai_sample_share*100).toFixed(2)}% measured kai_* function samples`;document.getElementById('performix-crosscheck').textContent=`${(profile.absolute_share_difference*100).toFixed(2)} pp from Linux perf attribution`;}}
const prov=document.getElementById('provenance');if(comparison){for(const [name,value] of [['Model artifact',comparison.baseline.artifact_sha256],['Runtime lock',comparison.baseline.runtime_sha256],['Workload',comparison.baseline.workload_sha256],['Environment',comparison.baseline.environment_sha256]]){const tr=document.createElement('tr');const a=document.createElement('td');a.textContent=name;const b=document.createElement('td');const code=document.createElement('code');code.textContent=value;b.appendChild(code);tr.append(a,b);prov.appendChild(tr)}}
for(const tab of document.querySelectorAll('.tab'))tab.addEventListener('click',()=>{for(const item of document.querySelectorAll('.tab'))item.setAttribute('aria-selected',String(item===tab));for(const panel of document.querySelectorAll('.view'))panel.hidden=panel.id!==tab.getAttribute('aria-controls')});
</script>
</body></html>'''
