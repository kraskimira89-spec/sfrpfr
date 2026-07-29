# Импорт существующих ресурсов в state

Перед импортом сверьте `cloud_id` / `folder_id` в `terraform.tfvars`.
После **каждого** импорта: `terraform plan` — без destructive changes.

## Шаблоны (подставьте реальные ID из консоли)

```bash
terraform import yandex_vpc_network.staging <NETWORK_ID>
terraform import yandex_vpc_subnet.staging <SUBNET_ID>
terraform import yandex_vpc_security_group.staging <SG_ID>
terraform import yandex_vpc_address.staging <ADDRESS_ID>
terraform import yandex_compute_disk.boot <BOOT_DISK_ID>
terraform import yandex_compute_disk.data <DATA_DISK_ID>
terraform import yandex_compute_instance.supabase <INSTANCE_ID>
terraform import yandex_storage_bucket.backup <BUCKET_NAME>
terraform import yandex_kms_symmetric_key.staging <KEY_ID>
terraform import yandex_iam_service_account.vm <SA_VM_ID>
terraform import yandex_iam_service_account.backup_writer <SA_BACKUP_ID>
terraform import yandex_lockbox_secret.supabase <SECRET_ID>
terraform import yandex_lockbox_secret.database <SECRET_ID>
```

## Не импортировать

- VPS `91.229.11.147` (вне Yandex Cloud)
- DNS `proverkastaza.ru` без отдельного cutover
