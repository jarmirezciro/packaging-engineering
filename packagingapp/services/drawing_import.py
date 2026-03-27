import zipfile
from django.core.files.base import ContentFile
from packagingapp.models import PackagingMaterial

ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")

def normalize_part_number(value: str) -> str:
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s

def import_drawings_zip(zip_file, catalogue):
    imported = 0
    not_matched = 0
    skipped = 0

    with zipfile.ZipFile(zip_file) as z:
        for filename in z.namelist():
            if filename.endswith("/"):
                continue

            lower = filename.lower()
            if not lower.endswith(ALLOWED_EXTENSIONS):
                skipped += 1
                continue

            base = filename.split("/")[-1]
            part_number_from_file = normalize_part_number(base.rsplit(".", 1)[0])

            material = PackagingMaterial.objects.filter(
                catalogue=catalogue,
                part_number=part_number_from_file
            ).first()

            if material is None:
                material = PackagingMaterial.objects.filter(
                    catalogue=catalogue,
                    part_number=part_number_from_file + ".0"
                ).first()

            if material is None:
                not_matched += 1
                continue

            content = ContentFile(z.read(filename))
            material.drawing.save(base, content, save=True)
            imported += 1

    #  MUST return 3 values
    return imported, not_matched, skipped
