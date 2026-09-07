from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename
from PIL import Image, ImageOps, UnidentifiedImageError

from packagingapp.entitlements import catalogue_image_limit_bytes
from packagingapp.models import PackagingCatalogue, PackagingMaterial, Product, ProductCatalogue


MAX_RAW_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 2000
MAX_IMAGE_PIXELS = 40_000_000
MAX_ZIP_IMAGE_MEMBERS = 2000
MAX_ZIP_TOTAL_RAW_BYTES = 1024 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}


class CatalogueMediaError(ValueError):
    pass


def _field_size(field_file) -> int:
    name = getattr(field_file, "name", "")
    if not name:
        return 0
    try:
        return int(default_storage.size(name))
    except (FileNotFoundError, OSError, ValueError):
        return 0


def catalogue_image_usage_bytes(user) -> int:
    if not getattr(user, "is_authenticated", False):
        return 0

    names: set[str] = set()
    querysets_and_fields = (
        (PackagingCatalogue.objects.filter(owner=user, is_public=False).only("picture"), "picture"),
        (PackagingMaterial.objects.filter(catalogue__owner=user, catalogue__is_public=False).only("picture"), "picture"),
        (ProductCatalogue.objects.filter(owner=user, is_public=False).only("picture"), "picture"),
        (Product.objects.filter(catalogue__owner=user, catalogue__is_public=False).only("product_picture"), "product_picture"),
    )
    for queryset, field_name in querysets_and_fields:
        for obj in queryset.iterator():
            name = getattr(getattr(obj, field_name), "name", "")
            if name:
                names.add(name)

    total = 0
    for name in names:
        try:
            total += int(default_storage.size(name))
        except (FileNotFoundError, OSError, ValueError):
            continue
    return total


def format_bytes(value: int) -> str:
    value = max(int(value or 0), 0)
    if value >= 1024 * 1024 * 1024:
        return f"{value / (1024 * 1024 * 1024):.1f} GB"
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} bytes"


def catalogue_storage_summary(user) -> dict:
    used = catalogue_image_usage_bytes(user)
    limit = catalogue_image_limit_bytes(user)
    return {
        "used_bytes": used,
        "limit_bytes": limit,
        "used_display": format_bytes(used),
        "limit_display": "Unlimited" if limit is None else format_bytes(limit),
        "usage_display": (
            f"{format_bytes(used)} used (unlimited staff access)"
            if limit is None
            else f"{format_bytes(used)} of {format_bytes(limit)} used"
        ),
    }


def _raw_upload_bytes(upload) -> bytes:
    size = getattr(upload, "size", None)
    if size is not None and size > MAX_RAW_IMAGE_BYTES:
        raise CatalogueMediaError("Each image must be 5 MB or smaller before optimization.")
    try:
        upload.seek(0)
    except (AttributeError, OSError):
        pass
    data = upload.read(MAX_RAW_IMAGE_BYTES + 1)
    if len(data) > MAX_RAW_IMAGE_BYTES:
        raise CatalogueMediaError("Each image must be 5 MB or smaller before optimization.")
    if not data:
        raise CatalogueMediaError("The uploaded image is empty.")
    return data


def optimize_catalogue_image(upload) -> ContentFile:
    data = _raw_upload_bytes(upload)
    try:
        with Image.open(BytesIO(data)) as opened:
            if (opened.format or "").upper() not in ALLOWED_IMAGE_FORMATS:
                raise CatalogueMediaError("Use a PNG, JPEG, GIF, or WebP image.")
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                raise CatalogueMediaError("The image dimensions are too large to process safely.")
            opened.load()
            image = ImageOps.exif_transpose(opened)
            image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")

            output = BytesIO()
            save_options = {"format": "WEBP", "method": 6}
            if image.mode == "RGBA":
                save_options["lossless"] = True
            else:
                save_options["quality"] = 82
            image.save(output, **save_options)
    except CatalogueMediaError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise CatalogueMediaError("The uploaded file is not a valid supported image.") from exc

    original_name = get_valid_filename(getattr(upload, "name", "catalogue-image"))
    stem = original_name.rsplit(".", 1)[0] or "catalogue-image"
    return ContentFile(output.getvalue(), name=f"{stem}-{uuid4().hex[:10]}.webp")


def prepare_catalogue_image(upload, user, *, replacing=None) -> ContentFile:
    optimized = optimize_catalogue_image(upload)
    limit = catalogue_image_limit_bytes(user)
    if limit is None:
        return optimized
    if limit <= 0:
        raise CatalogueMediaError("Private catalogue image uploads are included in Plus and Premium.")

    used = catalogue_image_usage_bytes(user)
    replacing_size = _field_size(replacing)
    projected = max(used - replacing_size, 0) + optimized.size
    if projected > limit:
        raise CatalogueMediaError(
            f"This image would exceed your catalogue storage limit. "
            f"Current usage is {format_bytes(used)} of {format_bytes(limit)}."
        )
    return optimized


def safe_zip_image_infos(archive):
    file_infos = [info for info in archive.infolist() if not info.is_dir()]
    if len(file_infos) > MAX_ZIP_IMAGE_MEMBERS:
        raise CatalogueMediaError(f"ZIP files may contain at most {MAX_ZIP_IMAGE_MEMBERS} files.")

    image_infos = []
    total_raw = 0
    skipped = 0
    for info in file_infos:
        normalized_name = info.filename.replace("\\", "/")
        path = PurePosixPath(normalized_name)
        if path.is_absolute() or ".." in path.parts:
            skipped += 1
            continue
        if path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
            skipped += 1
            continue
        if info.file_size > MAX_RAW_IMAGE_BYTES:
            raise CatalogueMediaError(f"{path.name} is larger than the 5 MB per-image limit.")
        total_raw += info.file_size
        if total_raw > MAX_ZIP_TOTAL_RAW_BYTES:
            raise CatalogueMediaError("The ZIP contains too much uncompressed image data.")
        if info.compress_size and info.file_size / info.compress_size > 500:
            raise CatalogueMediaError(f"{path.name} has an unsafe compression ratio.")
        image_infos.append(info)
    return image_infos, skipped


def read_zip_image(archive, info) -> ContentFile:
    with archive.open(info) as member:
        data = member.read(MAX_RAW_IMAGE_BYTES + 1)
    if len(data) > MAX_RAW_IMAGE_BYTES:
        raise CatalogueMediaError(f"{PurePosixPath(info.filename).name} is larger than 5 MB.")
    return ContentFile(data, name=PurePosixPath(info.filename.replace("\\", "/")).name)
