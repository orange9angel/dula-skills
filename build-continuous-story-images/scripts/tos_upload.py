#!/usr/bin/env python3
"""Upload a local file  to Volcano TOS and return a pre-signed GET URL.

Exists because OmniHuman (CVSubmitTask) requires public URLs for image/audio
(server-side fetch; base64 and data: URIs are rejected with 50215/50220).

Auth: same IAM sub-user pair as OmniHuman (env VOLC_ACCESSKEY/VOLC_SECRETKEY,
dula-story/.env.cv) — sub-user needs TOSFullAccess in addition to CVFullAccess.
Bucket is created on first use (private) and URLs are pre-signed GETs
(default 2h, matching OmniHuman's fetch window).

Usage:
  tos_upload.py --file assets/audio/004_Cat.wav
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BUCKET = "dula-e04-omnihuman-assets"
REGION = "cn-beijing"
ENDPOINT = f"tos-{REGION}.volces.com"
AK_ENV = "VOLC_ACCESSKEY"
SK_ENV = "VOLC_SECRETKEY"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--key", default=None, help="object key (default: filename)")
    parser.add_argument("--expires", type=int, default=7200)
    args = parser.parse_args()

    ak = os.environ.get(AK_ENV, "")
    sk = os.environ.get(SK_ENV, "")
    if not ak or not sk:
        print(f"ERROR: {AK_ENV}/{SK_ENV} not set", file=sys.stderr)
        return 2
    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: no such file: {path}", file=sys.stderr)
        return 2

    try:
        import tos
    except ImportError:
        print("ERROR: tos SDK missing; pip install tos in the project venv", file=sys.stderr)
        return 2

    client = tos.TosClientV2(ak, sk, ENDPOINT, REGION)
    try:
        client.head_bucket(BUCKET)
    except tos.exceptions.TosServerError as exc:
        if getattr(exc, "status_code", None) == 404:
            client.create_bucket(BUCKET)
            print(f"created bucket {BUCKET}")
        else:
            raise
    key = args.key or path.name
    client.put_object_from_file(BUCKET, key, str(path))
    url = client.pre_signed_url(tos.HttpMethodType.Http_Method_Get, BUCKET, key,
                                expires=args.expires).signed_url
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
