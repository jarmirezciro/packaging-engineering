import zipfile

from packagingapp.models import PackagingMaterial
from packagingapp.services.catalogue_media import (
    prepare_catalogue_image,
    read_zip_image,
    safe_zip_image_infos,
)
from packagingapp.services.drawing_import import normalize_part_number


def import_material_images_zip(zip_file, catalogue, *, acting_user=None):
    """Import packaging material pictures from a ZIP file.

    A file is matched when its filename without extension equals the
    PackagingMaterial.part_number in the selected catalogue. Folder names in
    the ZIP are ignored for matching.
    """
    imported = 0
    not_matched = 0
    skipped = 0

    quota_user = catalogue.owner or acting_user
    with zipfile.ZipFile(zip_file) as z:
        image_infos, pre_skipped = safe_zip_image_infos(z)
        skipped += pre_skipped
        for info in image_infos:
            base = info.filename.replace("\\", "/").split("/")[-1]
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

            content = read_zip_image(z, info)
            optimized = prepare_catalogue_image(
                content,
                quota_user,
                replacing=material.picture,
            )
            material.picture.save(optimized.name, optimized, save=True)
            imported += 1

    return imported, not_matched, skipped
