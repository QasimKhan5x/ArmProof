"""Failure-safe AWS lifecycle for an immutable ArmProof experiment bundle."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import tarfile
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .aws import AwsExperimentPlan, assert_approved


@dataclass(frozen=True)
class AwsRunResult:
    instance_id: str | None
    bucket: str
    result_key: str
    evidence_path: str | None
    terminated: bool
    cleanup_complete: bool


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def terminate_and_wait(
    ec2: Any,
    instance_id: str,
    *,
    poll_seconds: int = 5,
    timeout_seconds: int = 600,
) -> None:
    ec2.terminate_instances(InstanceIds=[instance_id])
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        reservations = response.get("Reservations", [])
        if not reservations or not reservations[0].get("Instances"):
            return
        state = reservations[0]["Instances"][0]["State"]["Name"]
        if state == "terminated":
            return
        if state == "stopped":
            ec2.terminate_instances(InstanceIds=[instance_id])
        time.sleep(poll_seconds)
    raise TimeoutError(f"instance {instance_id} did not terminate within {timeout_seconds} seconds")


def make_project_bundle(project: Path, destination: Path) -> str:
    excluded_parts = {
        ".git", ".venv", "build", "models", "node_modules", "test-results",
        "__pycache__", ".pytest_cache",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w:gz") as archive:
        for path in sorted(project.rglob("*")):
            relative = path.relative_to(project)
            if path.resolve() == destination.resolve():
                continue
            if any(part in excluded_parts for part in relative.parts):
                continue
            if relative.parts[:2] == ("ops", "evidence"):
                continue
            if path.name == ".env" or path.name.startswith(".env."):
                continue
            if path.suffix.lower() in {".pem", ".key", ".p12"}:
                continue
            if path.is_file():
                archive.add(path, arcname=str(relative), recursive=False)
    return file_sha256(destination)


def render_user_data(
    template: str,
    *,
    project_url: str,
    project_sha256: str,
    result_url: str,
    experiment_token: str,
    extra_exports: dict[str, str] | None = None,
) -> str:
    exports = {
        "PROJECT_BUNDLE_URL": project_url,
        "PROJECT_BUNDLE_SHA256": project_sha256,
        "RESULT_UPLOAD_URL": result_url,
        "EXPERIMENT_APPROVAL_TOKEN": experiment_token,
    }
    exports.update(extra_exports or {})
    prefix = "#!/usr/bin/env bash\n"
    for key, value in exports.items():
        if "\n" in value or "'" in value:
            raise ValueError(f"unsafe user-data value for {key}")
        prefix += f"export {key}='{value}'\n"
    rendered = prefix + template.removeprefix("#!/usr/bin/env bash\n")
    if len(rendered.encode()) > 16 * 1024:
        raise ValueError("EC2 user data exceeds the 16 KiB limit")
    return rendered


def inventory_resources(session: Any, region: str, project: str = "ArmProof") -> dict[str, Any]:
    ec2 = session.client("ec2", region_name=region)
    s3 = session.client("s3", region_name=region)
    filters = [{"Name": "tag:Project", "Values": [project]}]
    reservations = ec2.describe_instances(Filters=filters).get("Reservations", [])
    instances = [
        item
        for reservation in reservations
        for item in reservation.get("Instances", [])
        if item.get("State", {}).get("Name") != "terminated"
    ]
    volumes = ec2.describe_volumes(Filters=filters).get("Volumes", [])
    snapshots = ec2.describe_snapshots(OwnerIds=["self"], Filters=filters).get("Snapshots", [])
    addresses = [
        item
        for item in ec2.describe_addresses(Filters=filters).get("Addresses", [])
    ]
    buckets = []
    for item in s3.list_buckets().get("Buckets", []):
        name = item["Name"]
        try:
            tags = s3.get_bucket_tagging(Bucket=name).get("TagSet", [])
        except Exception:
            continue
        if any(tag.get("Key") == "Project" and tag.get("Value") == project for tag in tags):
            buckets.append(name)
    return {
        "instances": [item["InstanceId"] for item in instances],
        "volumes": [item["VolumeId"] for item in volumes],
        "snapshots": [item["SnapshotId"] for item in snapshots],
        "addresses": [item.get("AllocationId", item.get("PublicIp")) for item in addresses],
        "buckets": sorted(buckets),
    }


def execute_aws_run(
    *,
    session: Any,
    plan: AwsExperimentPlan,
    approval_token: str,
    experiment_token: str,
    project: Path,
    output_dir: Path,
    guest_template: Path,
    immutable_assets: dict[str, Path] | None = None,
    poll_seconds: int = 30,
) -> AwsRunResult:
    assert_approved(plan, approval_token)
    identity = session.client("sts").get_caller_identity()
    arn = str(identity.get("Arn", ""))
    if not arn or arn.endswith(":root"):
        raise PermissionError("paid execution requires an IAM user or assumed role")

    output_dir.mkdir(parents=True, exist_ok=True)
    before = inventory_resources(session, plan.region)
    (output_dir / "inventory-before.json").write_text(
        json.dumps(before, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if any(before.values()):
        raise RuntimeError(f"unexpected pre-existing ArmProof resources: {before}")

    s3 = session.client("s3", region_name=plan.region)
    ec2 = session.client("ec2", region_name=plan.region)
    ssm = session.client("ssm", region_name=plan.region)
    suffix = uuid.uuid4().hex[:10]
    bucket = f"armproof-{identity['Account']}-{suffix}".lower()
    project_key = f"{plan.experiment_id}/project.tar.gz"
    result_key = f"{plan.experiment_id}/evidence.tar.gz"
    bundle = output_dir / "project.tar.gz"
    bundle_sha = make_project_bundle(project, bundle)
    instance_id: str | None = None
    terminated = False
    evidence_path: Path | None = None
    bucket_created = False
    run_error: BaseException | None = None
    cleanup_errors: list[str] = []
    started_at = datetime.now(UTC)

    try:
        create_bucket: dict[str, Any] = {"Bucket": bucket}
        if plan.region != "us-east-1":
            create_bucket["CreateBucketConfiguration"] = {"LocationConstraint": plan.region}
        s3.create_bucket(**create_bucket)
        bucket_created = True
        s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True,
            "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
        })
        s3.put_bucket_encryption(Bucket=bucket, ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        })
        s3.put_bucket_tagging(Bucket=bucket, Tagging={
            "TagSet": [{"Key": key, "Value": value} for key, value in plan.tags.items()]
        })
        s3.upload_file(str(bundle), bucket, project_key)
        asset_exports: dict[str, str] = {}
        for name, path in sorted((immutable_assets or {}).items()):
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
                raise ValueError(f"invalid immutable asset name: {name}")
            asset_key = f"{plan.experiment_id}/assets/{path.name}"
            s3.upload_file(str(path), bucket, asset_key)
            asset_exports[f"{name}_URL"] = s3.generate_presigned_url(
                "get_object", Params={"Bucket": bucket, "Key": asset_key},
                ExpiresIn=plan.maximum_runtime_minutes * 60 + 1800,
            )
            asset_exports[f"{name}_SHA256"] = file_sha256(path)
        project_url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": project_key},
            ExpiresIn=plan.maximum_runtime_minutes * 60 + 1800,
        )
        result_url = s3.generate_presigned_url(
            "put_object", Params={"Bucket": bucket, "Key": result_key},
            ExpiresIn=plan.maximum_runtime_minutes * 60 + 1800, HttpMethod="PUT",
        )
        user_data = render_user_data(
            guest_template.read_text(encoding="utf-8"),
            project_url=project_url, project_sha256=bundle_sha,
            result_url=result_url, experiment_token=experiment_token,
            extra_exports=asset_exports,
        )
        ami = ssm.get_parameter(Name=(
            "/aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id"
        ))["Parameter"]["Value"]
        response = ec2.run_instances(
            ImageId=ami, InstanceType=plan.instance_type, MinCount=1, MaxCount=1,
            InstanceInitiatedShutdownBehavior="terminate",
            UserData=base64.b64encode(user_data.encode()).decode(),
            MetadataOptions={"HttpTokens": "required", "HttpEndpoint": "enabled"},
            BlockDeviceMappings=[{"DeviceName": "/dev/sda1", "Ebs": {
                "VolumeSize": plan.volume_gib, "VolumeType": "gp3",
                "DeleteOnTermination": True, "Encrypted": True,
            }}],
            TagSpecifications=[{"ResourceType": kind, "Tags": [
                {"Key": key, "Value": value} for key, value in plan.tags.items()
            ]} for kind in ("instance", "volume")],
        )
        instance_id = response["Instances"][0]["InstanceId"]
        deadline = time.monotonic() + plan.maximum_runtime_minutes * 60
        while time.monotonic() < deadline:
            try:
                s3.head_object(Bucket=bucket, Key=result_key)
                evidence_path = output_dir / "evidence.tar.gz"
                s3.download_file(bucket, result_key, str(evidence_path))
                break
            except s3.exceptions.ClientError as exc:
                status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if status not in {403, 404}:
                    raise
            time.sleep(poll_seconds)
        if evidence_path is None:
            raise TimeoutError("result object did not arrive before the immutable deadline")
    except BaseException as exc:
        run_error = exc
    finally:
        if instance_id:
            try:
                terminate_and_wait(ec2, instance_id, poll_seconds=min(poll_seconds, 5))
                terminated = True
            except BaseException as exc:
                cleanup_errors.append(f"instance termination: {exc!r}")
        if bucket_created:
            try:
                listed = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
                if listed:
                    s3.delete_objects(Bucket=bucket, Delete={
                        "Objects": [{"Key": item["Key"]} for item in listed]
                    })
                s3.delete_bucket(Bucket=bucket)
            except BaseException as exc:
                cleanup_errors.append(f"bucket cleanup: {exc!r}")

    try:
        after = inventory_resources(session, plan.region)
    except BaseException as exc:
        after = {"inventory_error": repr(exc)}
        cleanup_errors.append(f"post-run inventory: {exc!r}")
    (output_dir / "inventory-after.json").write_text(
        json.dumps(after, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    cleanup_complete = terminated and not cleanup_errors and not any(after.values())
    if instance_id is None:
        cleanup_complete = not cleanup_errors and not any(after.values())
    elapsed_hours = max(0.0, (datetime.now(UTC) - started_at).total_seconds() / 3600)
    estimated_session_cost = min(
        plan.maximum_compute_cost_usd + plan.maximum_storage_cost_usd,
        elapsed_hours * (plan.maximum_compute_cost_usd / (plan.maximum_runtime_minutes / 60))
        + plan.maximum_storage_cost_usd,
    )
    ledger = {
        "experiment_id": plan.experiment_id,
        "instance_id": instance_id,
        "instance_type": plan.instance_type,
        "region": plan.region,
        "prior_spend_usd": plan.prior_spend_usd,
        "maximum_projected_total_usd": plan.maximum_projected_total_usd,
        "estimated_session_cost_usd": round(estimated_session_cost, 4),
        "estimated_cumulative_cost_usd": round(plan.prior_spend_usd + estimated_session_cost, 4),
        "maximum_runtime_minutes": plan.maximum_runtime_minutes,
        "terminated": terminated,
        "cleanup_complete": cleanup_complete,
        "cleanup_errors": cleanup_errors,
        "error": repr(run_error) if run_error else None,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    (output_dir / "spend-ledger.json").write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if run_error is not None:
        raise run_error
    if not cleanup_complete:
        raise RuntimeError(f"AWS cleanup incomplete: {cleanup_errors or after}")
    return AwsRunResult(instance_id, bucket, result_key, str(evidence_path), terminated, True)
