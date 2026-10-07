"""One Always Free launch attempt per run. No browser or paid resource fallback."""
import json
import os
import smtplib
import sys
import uuid
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from urllib.request import Request, urlopen

REGION = "ap-singapore-1"
NAME = "always-free-capacity-watch"
OWNER_TAG = "oracle-capacity-watch"
A1 = "VM.Standard.A1.Flex"
MICRO = "VM.Standard.E2.1.Micro"


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing secret: {name}")
    return value


def guard_budget(instances, volumes, shape):
    """Include stopped instances and unattached disks; fail closed on unknown sizes."""
    if shape not in {A1, MICRO}:
        raise ValueError("Shape is not on the Always Free allowlist")
    live = [i for i in instances if i.lifecycle_state != "TERMINATED"]
    a1 = [i for i in live if i.shape == A1]
    ocpus = sum(float(i.shape_config.ocpus) for i in a1)
    memory = sum(float(i.shape_config.memory_in_gbs) for i in a1)
    micro = sum(i.shape == MICRO for i in live)
    if shape == A1 and (ocpus + 1 > 2 or memory + 6 > 12):
        raise ValueError("Would exceed Always Free A1 total 2 OCPU / 12 GB")
    if shape == MICRO and micro >= 2:
        raise ValueError("Would exceed two Always Free E2 Micro instances")
    disk_gb = sum(float(v.size_in_gbs) for v in volumes if v.lifecycle_state != "TERMINATED")
    if disk_gb + 50 > 200:
        raise ValueError("Would exceed 200 GB total Home-region boot + block storage")


def select_image(images):
    platform = [i for i in images if i.compartment_id is None
                and i.operating_system == "Oracle Linux"
                and i.operating_system_version == "9"
                and i.lifecycle_state == "AVAILABLE"]
    if not platform:
        raise ValueError("No official Oracle Linux 9 image compatible with this shape")
    return max(platform, key=lambda i: i.time_created)


def send_success(instance, public_ip):
    message = EmailMessage()
    message["From"] = require_env("SMTP_USER")
    message["To"] = require_env("NOTIFY_TO")
    message["Subject"] = "Oracle Always Free VM สร้างสำเร็จแล้ว"
    local_time = datetime.now(timezone(timedelta(hours=7))).isoformat()
    message.set_content(
        f"สร้าง Oracle Always Free VM สำเร็จ\nเวลา Asia/Bangkok: {local_time}\n"
        f"Region: {REGION}\nShape: {instance.shape}\nName: {instance.display_name}\n"
        f"Instance ID: {instance.id}\nPublic IP: {public_ip}\n"
        f"SSH: ssh opc@{public_ip}\nBoot disk: 50 GB\n"
        "ใช้ private SSH key เดิมบนเครื่องคุณ\n"
        "ถ้าเป็น A1: CPU เป็น ARM; MT5/Wine x86 ต้องวางแผนความเข้ากันได้ก่อน\n"
        "งานตรวจจะหยุดหลังส่งเมลสำเร็จ ไม่มีการเริ่มบอทเทรด\n"
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
        smtp.login(require_env("SMTP_USER"), require_env("SMTP_PASSWORD"))
        smtp.send_message(message)


def disable_workflow():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        return
    workflow = os.environ.get("ORACLE_WORKFLOW_FILE", "oracle-free-capacity.yml")
    request = Request(f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/disable",
                      method="PUT", headers={"Authorization": "Bearer " + require_env("GITHUB_TOKEN"),
                                             "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=20):
        pass
    print("Success: workflow disabled")


def main():
    import oci
    # Validate mail configuration before creating anything; do not transmit a test message.
    for name in ("SMTP_USER", "SMTP_PASSWORD", "NOTIFY_TO", "OCI_SSH_PUBLIC_KEY"):
        require_env(name)
    config = json.loads(require_env("OCI_CONFIG_JSON"))
    if config.get("region") != REGION:
        raise ValueError("Only the configured Singapore Home region is allowed")
    config["key_content"] = require_env("OCI_API_PRIVATE_KEY")
    config.pop("key_file", None)
    oci.config.validate_config(config)
    kwargs = {"retry_strategy": oci.retry.NoneRetryStrategy(), "timeout": (10, 30)}
    identity = oci.identity.IdentityClient(config, **kwargs)
    compute = oci.core.ComputeClient(config, **kwargs)
    network = oci.core.VirtualNetworkClient(config, **kwargs)
    block = oci.core.BlockstorageClient(config, **kwargs)
    tenancy = config["tenancy"]
    regions = identity.list_region_subscriptions(tenancy).data
    if not any(r.region_name == REGION and r.is_home_region for r in regions):
        raise ValueError("Singapore is not the tenancy Home region")
    # Scan every compartment, not just the launch compartment. API permissions must cover all.
    children = oci.pagination.list_call_get_all_results(
        identity.list_compartments, tenancy, compartment_id_in_subtree=True,
        access_level="ANY").data
    compartments = [tenancy] + [c.id for c in children if c.lifecycle_state == "ACTIVE"]
    instances, volumes = [], []
    ads = identity.list_availability_domains(tenancy).data
    ad = next((a.name for a in ads if a.name.endswith("AP-SINGAPORE-1-AD-1")), None)
    if not ad:
        raise ValueError("Expected Singapore AD-1 is unavailable")
    for compartment in compartments:
        instances += oci.pagination.list_call_get_all_results(compute.list_instances, compartment).data
        volumes += oci.pagination.list_call_get_all_results(block.list_volumes, compartment).data
        for domain in ads:
            volumes += oci.pagination.list_call_get_all_results(
                block.list_boot_volumes, availability_domain=domain.name,
                compartment_id=compartment).data
    matching = [i for i in instances if i.display_name == NAME and i.lifecycle_state != "TERMINATED"]
    if len(matching) > 1:
        raise ValueError("Multiple matching instances: stop for manual review")
    if matching:
        instance = matching[0]
        if instance.freeform_tags.get("managed-by") != OWNER_TAG:
            raise ValueError("Matching name belongs to another launch: stop for review")
        if instance.shape not in {A1, MICRO}:
            raise ValueError("Unexpected shape on existing watch instance")
        if instance.lifecycle_state != "RUNNING":
            print("Existing VM found; waiting for RUNNING. No new launch.")
            return
        if instance.freeform_tags.get("success-email") == "sent":
            disable_workflow()
            return
        attachments = oci.pagination.list_call_get_all_results(
            compute.list_vnic_attachments, tenancy, instance_id=instance.id).data
        ips = [network.get_vnic(v.vnic_id).data.public_ip for v in attachments
               if v.lifecycle_state == "ATTACHED"]
        public_ip = next((ip for ip in ips if ip), None)
        if not public_ip:
            raise ValueError("VM running but no public IP; no new launch")
        send_success(instance, public_ip)
        tags = dict(instance.freeform_tags, **{"success-email": "sent"})
        compute.update_instance(instance.id, oci.core.models.UpdateInstanceDetails(freeform_tags=tags))
        disable_workflow()
        print("VM ready; email sent. See private email for connection details.")
        return
    # Alternate A1 and E2 on half-hour slots. Never retry a launch inside one run.
    shape = A1 if int(datetime.now(timezone.utc).timestamp() // 1800) % 2 == 0 else MICRO
    guard_budget(instances, volumes, shape)
    images = oci.pagination.list_call_get_all_results(
        compute.list_images, tenancy, operating_system="Oracle Linux",
        operating_system_version="9", shape=shape).data
    image = select_image(images)
    subnets = oci.pagination.list_call_get_all_results(network.list_subnets, tenancy).data
    subnet = [s for s in subnets if s.display_name == "subnet-20260907-0112"
              and s.lifecycle_state == "AVAILABLE" and not s.prohibit_public_ip_on_vnic]
    if len(subnet) != 1:
        raise ValueError("Expected existing public subnet is not uniquely available")
    key = require_env("OCI_SSH_PUBLIC_KEY")
    if not key.startswith("ssh-rsa ") or "PRIVATE KEY" in key:
        raise ValueError("Invalid SSH PUBLIC key")
    launch = oci.core.models.LaunchInstanceDetails(
        availability_domain=ad, compartment_id=tenancy, display_name=NAME, shape=shape,
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=1, memory_in_gbs=6)
        if shape == A1 else None,
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            image_id=image.id, boot_volume_size_in_gbs=50, boot_volume_vpus_per_gb=10),
        create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=subnet[0].id, assign_public_ip=True),
        metadata={"ssh_authorized_keys": key},
        freeform_tags={"managed-by": OWNER_TAG},
        is_pv_encryption_in_transit_enabled=True)
    token = str(uuid.uuid5(uuid.NAMESPACE_URL, tenancy + NAME + shape))
    try:
        compute.launch_instance(launch, opc_retry_token=token)
    except oci.exceptions.ServiceError as error:
        if error.status == 500 and "out of" in error.message.lower() and "capacity" in error.message.lower():
            print(f"{shape}: Out of capacity. Next check in about 30 minutes.")
            return
        # Avoid dumping SDK errors that may include resource identifiers into public logs.
        raise RuntimeError(f"Oracle launch failed: HTTP {error.status}, {error.code}") from None
    print(f"{shape}: launch accepted. Next run will confirm RUNNING and send email.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Watch stopped for review: {type(error).__name__}", file=sys.stderr)
        # Config validation messages are safe; other SDK/network payloads stay out of public logs.
        if isinstance(error, (ValueError, RuntimeError)):
            print(str(error), file=sys.stderr)
        sys.exit(1)
