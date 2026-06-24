import zipfile

from django.core.files.base import ContentFile

from packagingapp.models import PackagingMaterial
from packagingapp.services.drawing_import import normalize_part_number

ALLOWED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def import_material_images_zip(zip_file, catalogue):
    """Import packaging material pictures from a ZIP file.

    A file is matched when its filename without extension equals the
    PackagingMaterial.part_number in the selected catalogue. Folder names in
    the ZIP are ignored for matching.
    """
    imported = 0
    not_matched = 0
    skipped = 0

    with zipfile.ZipFile(zip_file) as z:
        for filename in z.namelist():
            if filename.endswith("/"):
                continue

            lower = filename.lower()
            if not lower.endswith(ALLOWED_IMAGE_EXTENSIONS):
                skipped += 1
                continue

            base = filename.split("/")[-1]
            part_number_from_file = normalize_part_number(base.rsplit(".", 1)[0])

            material = PackagingMaterial.objects.filter(
                catalogue=catalogue,
                part_number=part_number_from_file,
            ).first()

            if material is None:
                material = PackagingMaterial.objects.filter(
                    catalogue=catalogue,
                    part_number=part_number_from_file + ".0",
                ).first()

            if material is None:
                not_matched += 1
                continue

            content = ContentFile(z.read(filename))
            material.picture.save(base, content, save=True)
            imported += 1

    return imported, not_matched, skipped
