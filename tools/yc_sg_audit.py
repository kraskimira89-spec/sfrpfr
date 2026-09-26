"""Read-only аудит Yandex Cloud: доступные облака/каталоги, ВМ и security groups.

Ключ SA: secrets/yc-sa-terraform.json. Ничего не изменяет.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import jwt
import requests

ROOT = Path(__file__).resolve().parents[1]
KEY_PATH = ROOT / "secrets" / "yc-sa-terraform.json"
FOLDERS = ["b1grtprgfugidt9u073i", "b1g0mhpm9tr4lrurk1bu"]


def iam_token() -> str:
    key = json.loads(KEY_PATH.read_text(encoding="utf-8"))
    now = int(time.time())
    payload = {
        "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
        "iss": key["service_account_id"],
        "iat": now,
        "exp": now + 3600,
    }
    encoded = jwt.encode(payload, key["private_key"], algorithm="PS256", headers={"kid": key["id"]})
    r = requests.post(
        "https://iam.api.cloud.yandex.net/iam/v1/tokens", json={"jwt": encoded}, timeout=20
    )
    r.raise_for_status()
    return r.json()["iamToken"]


def get(url: str, token: str, **params: str) -> tuple[int, dict]:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


def main() -> int:
    token = iam_token()
    code, clouds = get(
        "https://resource-manager.api.cloud.yandex.net/resource-manager/v1/clouds", token
    )
    print(f"clouds [{code}]:", [(c["id"], c.get("name")) for c in clouds.get("clouds", [])])
    for cloud in clouds.get("clouds", []):
        code, folders = get(
            "https://resource-manager.api.cloud.yandex.net/resource-manager/v1/folders",
            token,
            cloudId=cloud["id"],
        )
        print(
            f"  folders of {cloud['id']} [{code}]:",
            [(f["id"], f.get("name")) for f in folders.get("folders", [])],
        )

    for folder in FOLDERS:
        print(f"\n=== folder {folder}")
        code, vms = get(
            "https://compute.api.cloud.yandex.net/compute/v1/instances", token, folderId=folder
        )
        if code != 200:
            print(f"  instances: HTTP {code} {vms.get('message', '')[:120]}")
        for vm in vms.get("instances", []):
            ips = [
                i.get("primaryV4Address", {}).get("oneToOneNat", {}).get("address")
                for i in vm.get("networkInterfaces", [])
            ]
            sgs = [
                s for i in vm.get("networkInterfaces", []) for s in i.get("securityGroupIds", [])
            ]
            print(f"  VM {vm['name']} {vm['id']} {vm['status']} ip={ips} sg={sgs}")
        code, sgs = get(
            "https://vpc.api.cloud.yandex.net/vpc/v1/securityGroups", token, folderId=folder
        )
        if code != 200:
            print(f"  securityGroups: HTTP {code} {sgs.get('message', '')[:120]}")
        for sg in sgs.get("securityGroups", []):
            print(f"  SG {sg['name']} {sg['id']} {sg.get('status')}")
            for rule in sg.get("rules", []):
                cidrs = rule.get("cidrBlocks", {}).get("v4CidrBlocks", [])
                ports = rule.get("ports", {})
                port = f"{ports.get('fromPort', '')}-{ports.get('toPort', '')}" if ports else "any"
                target = cidrs or rule.get("predefinedTarget", "")
                print(
                    f"    {rule['direction']:<7} {rule.get('protocolName', ''):<4} {port:<11} "
                    f"{target} | {rule.get('description', '')} [{rule['id']}]"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
