import base64
import binascii
import os
import uuid

from django.conf import settings


_ALLOWED_IMAGE_DATA_URLS = {
    "data:image/png;base64,": (".png", b"\x89PNG\r\n\x1a\n"),
    "data:image/jpeg;base64,": (".jpg", b"\xff\xd8"),
}
_MAX_DATA_URL_LENGTH = 8_000_000


def save_threejs_snapshot_from_request(
    request,
    *,
    relative_directory,
    field_name="threejs_snapshot",
):
    """Validate and persist a browser canvas snapshot under MEDIA_ROOT."""
    if request.method != "POST":
        return ""

    data_url = (request.POST.get(field_name) or "").strip()
    if not data_url or len(data_url) > _MAX_DATA_URL_LENGTH:
        return ""

    matched = None
    for prefix, (extension, magic) in _ALLOWED_IMAGE_DATA_URLS.items():
        if data_url.startswith(prefix):
            matched = (prefix, extension, magic)
            break
    if matched is None:
        return ""

    prefix, extension, magic = matched
    try:
        image_bytes = base64.b64decode(data_url[len(prefix):], validate=True)
    except (binascii.Error, ValueError):
        return ""

    if not image_bytes.startswith(magic):
        return ""

    file_name = f"threejs_snapshot_{uuid.uuid4().hex}{extension}"
    rel_path = os.path.join(relative_directory, file_name)
    abs_path = os.path.abspath(os.path.join(settings.MEDIA_ROOT, rel_path))
    media_root = os.path.abspath(settings.MEDIA_ROOT)

    try:
        if os.path.commonpath([media_root, abs_path]) != media_root:
            return ""
    except ValueError:
        return ""

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as image_file:
        image_file.write(image_bytes)

    return rel_path
