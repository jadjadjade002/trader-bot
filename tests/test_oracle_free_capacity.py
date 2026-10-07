import importlib.util
import unittest
from unittest.mock import Mock, patch
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

spec = importlib.util.spec_from_file_location("watch", Path(__file__).parents[1] / "scripts/oracle_free_capacity.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class BudgetTests(unittest.TestCase):
    def instance(self, shape, state="STOPPED", ocpus=1, memory=6):
        return NS(shape=shape, lifecycle_state=state, shape_config=NS(ocpus=ocpus, memory_in_gbs=memory))

    def volume(self, size, state="AVAILABLE"):
        return NS(size_in_gbs=size, lifecycle_state=state)

    def test_stopped_a1_still_counts_toward_free_limit(self):
        with self.assertRaises(ValueError):
            watch.guard_budget([self.instance(watch.A1, ocpus=2, memory=12)], [], watch.A1)

    def test_unattached_disk_counts_toward_storage(self):
        with self.assertRaises(ValueError):
            watch.guard_budget([], [self.volume(151)], watch.A1)

    def test_exact_storage_and_a1_limits_allowed(self):
        watch.guard_budget([self.instance(watch.A1)], [self.volume(150)], watch.A1)

    def test_terminated_resources_do_not_count(self):
        watch.guard_budget([self.instance(watch.A1, "TERMINATED", 80, 512)],
                           [self.volume(1000, "TERMINATED")], watch.A1)

    def test_micro_limit(self):
        with self.assertRaises(ValueError):
            watch.guard_budget([self.instance(watch.MICRO), self.instance(watch.MICRO)], [], watch.MICRO)

    def test_paid_shape_rejected_even_with_empty_account(self):
        with self.assertRaises(ValueError):
            watch.guard_budget([], [], "VM.Standard.E5.Flex")

    def test_missing_size_fails_closed(self):
        with self.assertRaises(TypeError):
            watch.guard_budget([], [self.volume(None)], watch.A1)

    def test_custom_image_cannot_be_used(self):
        custom = NS(compartment_id="user", operating_system="Oracle Linux",
                    operating_system_version="9", lifecycle_state="AVAILABLE",
                    time_created=datetime.now(timezone.utc))
        with self.assertRaises(ValueError):
            watch.select_image([custom])


class ExistingInstanceTests(unittest.TestCase):
    def fake_sdk(self, instances):
        compute = Mock()
        compute.list_instances.return_value = NS(data=instances)
        block = Mock()
        block.list_volumes.return_value = NS(data=[])
        block.list_boot_volumes.return_value = NS(data=[])
        identity = Mock()
        identity.list_region_subscriptions.return_value = NS(data=[NS(region_name=watch.REGION, is_home_region=True)])
        identity.list_compartments.return_value = NS(data=[])
        identity.list_availability_domains.return_value = NS(data=[NS(name='prefix:AP-SINGAPORE-1-AD-1')])
        sdk = NS(config=NS(validate_config=Mock()), retry=NS(NoneRetryStrategy=lambda: None),
                 identity=NS(IdentityClient=lambda *a, **k: identity),
                 core=NS(ComputeClient=lambda *a, **k: compute,
                         VirtualNetworkClient=lambda *a, **k: Mock(),
                         BlockstorageClient=lambda *a, **k: block),
                 pagination=NS(list_call_get_all_results=lambda f, *a, **k: f(*a, **k)))
        return sdk, compute

    def env(self):
        return {'SMTP_USER':'test@example.com','SMTP_PASSWORD':'dummy','NOTIFY_TO':'test@example.com',
                'OCI_SSH_PUBLIC_KEY':'ssh-rsa dummy', 'OCI_API_PRIVATE_KEY':'dummy',
                'OCI_CONFIG_JSON':json.dumps({'region':watch.REGION,'tenancy':'tenancy'})}

    def instance(self, managed=True, state='PROVISIONING', sent=False):
        tags = {'managed-by':watch.OWNER_TAG} if managed else {}
        if sent:
            tags['success-email'] = 'sent'
        return NS(id='instance', display_name=watch.NAME, lifecycle_state=state,
                  freeform_tags=tags, shape=watch.A1)

    def test_existing_provisioning_instance_prevents_second_launch(self):
        sdk, compute = self.fake_sdk([self.instance()])
        with patch.dict('sys.modules', {'oci':sdk}), patch.dict(watch.os.environ,self.env(),clear=True):
            watch.main()
        compute.launch_instance.assert_not_called()

    def test_matching_unowned_instance_fails_closed(self):
        sdk, compute = self.fake_sdk([self.instance(managed=False)])
        with patch.dict('sys.modules', {'oci':sdk}), patch.dict(watch.os.environ,self.env(),clear=True):
            with self.assertRaises(ValueError):
                watch.main()
        compute.launch_instance.assert_not_called()

    def test_already_notified_instance_disables_without_duplicate_email(self):
        sdk, compute = self.fake_sdk([self.instance(state='RUNNING',sent=True)])
        with patch.dict('sys.modules', {'oci':sdk}), patch.dict(watch.os.environ,self.env(),clear=True), \
             patch.object(watch,'disable_workflow') as disable, patch.object(watch,'send_success') as mail:
            watch.main()
        disable.assert_called_once()
        mail.assert_not_called()
        compute.launch_instance.assert_not_called()


if __name__ == "__main__":
    unittest.main()
