"""Hold the warning until the COOL Graviton machine finishes the check."""

import json
import os
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

from services.api.live_feed import alert_from_views, ready_views

_REVIEW = Path("data/local/review.json")
_AMI = "ami-0f7cc6a2059ad561f"
_INSTANCE_TYPE = "c8g.2xlarge"
_SUBNET = "subnet-0dad398b62e3baa26"
_SECURITY_GROUP = "sg-0e22f85936d967776"
_KEY = "firecouncil-cheap"
_PROFILE = "firecouncil-cheap"


def warning_ready(smoke_marked: bool, state: str) -> bool:
    """A camera mark is the trigger. The warning opens after Graviton finishes."""
    if not smoke_marked:
        return True
    return state == "final"


def hold_warning() -> bool:
    """True while a marked camera is still waiting on the Graviton decision."""
    state = review_state()
    if state == "off":
        return False
    text = alert_from_views(ready_views()) or ""
    return not warning_ready(text.startswith("Smoke marked"), state)


def review_state() -> str:
    """off until a Graviton check is actually running. A missing file does not hide the warning."""
    if not _REVIEW.is_file():
        return "off"
    try:
        return str(json.loads(_REVIEW.read_text()).get("state") or "off")
    except json.JSONDecodeError:
        return "off"


def hold_cameras() -> bool:
    text = alert_from_views(ready_views()) or ""
    return text.startswith("Smoke marked")


def mark_final(instance_id: str | None = None) -> None:
    body = {"state": "final"}
    if instance_id:
        body["instance_id"] = instance_id
    _REVIEW.parent.mkdir(parents=True, exist_ok=True)
    _REVIEW.write_text(json.dumps(body))


def ensure_graviton() -> None:
    """Start one COOL Graviton machine. Does nothing unless GRAVITON_LAUNCH=1."""
    if os.environ.get("GRAVITON_LAUNCH") != "1":
        return
    if review_state() == "final":
        return
    current = _read()
    if current.get("state") in {"starting", "running", "final"} and current.get("instance_id"):
        return
    _write({"state": "starting"})
    try:
        instance_id = _find_or_start()
    except (ClientError, BotoCoreError):
        _write({"state": "off", "error": "unavailable"})
        return
    _write({"state": "running", "instance_id": instance_id})


def _find_or_start() -> str:
    import boto3

    ec2 = boto3.client("ec2", region_name=os.environ.get("AWS_REGION", "us-east-2"))
    found = ec2.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": ["firecouncil-cool"]},
            {"Name": "image-id", "Values": [_AMI]},
            {"Name": "instance-state-name", "Values": ["pending", "running", "stopped"]},
        ]
    )
    stopped = None
    for reservation in found["Reservations"]:
        for instance in reservation["Instances"]:
            if instance["State"]["Name"] in {"pending", "running"}:
                return instance["InstanceId"]
            stopped = instance["InstanceId"]
    if stopped:
        ec2.start_instances(InstanceIds=[stopped])
        return stopped
    started = ec2.run_instances(
        ImageId=_AMI,
        InstanceType=_INSTANCE_TYPE,
        KeyName=_KEY,
        SecurityGroupIds=[_SECURITY_GROUP],
        SubnetId=_SUBNET,
        MinCount=1,
        MaxCount=1,
        IamInstanceProfile={"Name": _PROFILE},
        MetadataOptions={"HttpTokens": "required", "HttpEndpoint": "enabled", "HttpPutResponseHopLimit": 2},
        BlockDeviceMappings=[
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {
                    "VolumeSize": 50,
                    "VolumeType": "gp3",
                    "DeleteOnTermination": True,
                    "Encrypted": True,
                },
            },
            {"DeviceName": "/dev/sdb", "NoDevice": ""},
            {"DeviceName": "/dev/sdc", "NoDevice": ""},
        ],
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": "firecouncil-cool"},
                    {"Key": "Project", "Value": "FireCouncil"},
                ],
            }
        ],
    )
    return started["Instances"][0]["InstanceId"]


def _read() -> dict:
    if not _REVIEW.is_file():
        return {}
    try:
        return json.loads(_REVIEW.read_text())
    except json.JSONDecodeError:
        return {}


def _write(body: dict) -> None:
    _REVIEW.parent.mkdir(parents=True, exist_ok=True)
    _REVIEW.write_text(json.dumps(body))
