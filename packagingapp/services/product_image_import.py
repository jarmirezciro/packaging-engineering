import zipfile

from packagingapp.services.catalogue_media import (
    prepare_catalogue_image,
    read_zip_image,
    safe_zip_image_infos,
)


def import_product_images_zip(zip_file, catalogue, *, acting_user=None):
    quota_user = catalogue.owner or acting_user
    imported = 0
    skipped = 0

    with zipfile.ZipFile(zip_file) as archive:
        image_infos, pre_skipped = safe_zip_image_infos(archive)
        skipped += pre_skipped
        by_basename = {
            info.filename.replace("\\", "/").split("/")[-1].lower(): info
            for info in image_infos
        }

        for product in catalogue.products.all():
            if product.product_picture:
                continue

            candidates = []
            if product.product_id:
                candidates.extend(f"{product.product_id}{ext}" for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"))
            if product.product_name:
                name = str(product.product_name).strip()
                candidates.extend(f"{name}{ext}" for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"))

            info = next((by_basename.get(candidate.lower()) for candidate in candidates if by_basename.get(candidate.lower())), None)
            if info is None:
                continue

            content = read_zip_image(archive, info)
            optimized = prepare_catalogue_image(content, quota_user)
            product.product_picture.save(optimized.name, optimized, save=True)
            imported += 1

    return imported, skipped
