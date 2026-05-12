"""
storage.py — Unified file storage abstraction for DLP Advisor.

In production (DigitalOcean App Platform):
    Files are stored in DigitalOcean Spaces (S3-compatible object storage).
    The public URL is returned directly so Babylon.js can load the GLB.

In development (local):
    Files are stored on disk under instance/uploads/upload_data/.
    The file is served via the serve_model Flask route.

Configuration (Environment Variables):
    DO_SPACES_KEY        — Spaces Access Key ID
    DO_SPACES_SECRET     — Spaces Secret Access Key
    DO_SPACES_REGION     — e.g. "sgp1" or "nyc3"
    DO_SPACES_BUCKET     — Your Space name, e.g. "dlp-advisor-uploads"
    DO_SPACES_ENDPOINT   — e.g. "https://sgp1.digitaloceanspaces.com"
"""

import os
import boto3
from botocore.exceptions import ClientError
from flask import current_app


def _get_spaces_client():
    """Return a configured boto3 S3 client for DO Spaces, or None if not configured."""
    key    = os.environ.get("DO_SPACES_KEY", "").strip()
    secret = os.environ.get("DO_SPACES_SECRET", "").strip()
    region = os.environ.get("DO_SPACES_REGION", "sgp1").strip()
    endpoint = os.environ.get(
        "DO_SPACES_ENDPOINT",
        f"https://{region}.digitaloceanspaces.com"
    ).strip()

    if not key or not secret:
        return None

    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
    )


def is_spaces_configured() -> bool:
    """Return True if DO Spaces credentials are present in the environment."""
    return bool(
        os.environ.get("DO_SPACES_KEY", "").strip()
        and os.environ.get("DO_SPACES_SECRET", "").strip()
        and os.environ.get("DO_SPACES_BUCKET", "").strip()
    )


def upload_glb(local_path: str, filename: str) -> str:
    """
    Upload a GLB file to storage.

    Returns:
        - In production: the public HTTPS URL of the uploaded object.
        - In development: just the filename (served via serve_model route).
    """
    if is_spaces_configured():
        client = _get_spaces_client()
        bucket = os.environ.get("DO_SPACES_BUCKET")
        object_key = f"uploads/{filename}"

        try:
            client.upload_file(
                local_path,
                bucket,
                object_key,
                ExtraArgs={
                    "ContentType": "model/gltf-binary",
                    "ACL": "public-read",
                },
            )
            region   = os.environ.get("DO_SPACES_REGION", "sgp1")
            endpoint = os.environ.get(
                "DO_SPACES_ENDPOINT",
                f"https://{region}.digitaloceanspaces.com"
            )
            public_url = f"{endpoint}/{bucket}/{object_key}"
            current_app.logger.info("GLB uploaded to Spaces: %s", public_url)
            return public_url
        except ClientError as e:
            current_app.logger.error("DO Spaces upload failed: %s", e)
            raise

    # Local dev fallback — the filename is what gets stored in scan.model_path
    current_app.logger.info("Spaces not configured — GLB saved locally: %s", filename)
    return filename


def get_glb_url(model_path: str, scan_id: int) -> str | None:
    """
    Resolve the URL to serve a GLB file.

    Args:
        model_path: Value stored in scan.model_path (either a filename or a full URL).
        scan_id:    The scan's database ID (used for local serve route).

    Returns:
        A URL string the browser can use to fetch the GLB, or None if no model.
    """
    if not model_path:
        return None

    # If it's already a full URL (Spaces), return as-is
    if model_path.startswith("http://") or model_path.startswith("https://"):
        return model_path

    # Local development — use the Flask serve_model route
    from flask import url_for
    return url_for("module2.serve_model", scan_id=scan_id)
