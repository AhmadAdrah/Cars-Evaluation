"""Validation and persistence for car listing images."""
import io

from django import forms
from django.db import transaction
from PIL import Image

from apps.cars.models import CarImage

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES_PER_REQUEST = 10
MAX_IMAGE_DIMENSION = 1280
JPEG_QUALITY = 85


class ImageValidationError(Exception):
    """Raised when uploaded files are not usable as car listing images."""


def validate_uploaded_images(files):
    """Ensure every uploaded file is a decodable image within limits.

    Uses Django's ImageField (Pillow-backed) so corrupt payloads and
    non-image extensions are rejected before anything touches storage.
    """
    if len(files) > MAX_IMAGES_PER_REQUEST:
        raise ImageValidationError(
            f'A maximum of {MAX_IMAGES_PER_REQUEST} images can be uploaded per request.'
        )

    field = forms.ImageField()
    for image_file in files:
        if getattr(image_file, 'size', 0) > MAX_IMAGE_BYTES:
            raise ImageValidationError(
                f'"{image_file.name}" exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MB per-image limit.'
            )
        try:
            field.clean(image_file)
        except forms.ValidationError:
            raise ImageValidationError(f'"{image_file.name}" is not a valid image file.')

    return files


def compress_image(image_file):
    """Re-encode a validated upload as a bounded-size JPEG.

    Images are stored as binary in the database and serialized inline as
    base64 data URIs, so originals are downscaled to MAX_IMAGE_DIMENSION
    and re-encoded to keep API payloads small.
    """
    image_file.seek(0)
    try:
        with Image.open(image_file) as img:
            img = img.convert('RGB')
            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=JPEG_QUALITY)
    except Exception:
        raise ImageValidationError(f'"{image_file.name}" could not be processed.')
    return buffer.getvalue(), 'image/jpeg'


def attach_car_images(car, files):
    """Persist validated files as compressed binary CarImage rows.

    The first image becomes primary only when the car has no images yet.
    """
    has_existing = car.images.exists()
    created = []
    with transaction.atomic():
        for index, image_file in enumerate(files):
            image_data, content_type = compress_image(image_file)
            created.append(CarImage.objects.create(
                car=car,
                image_data=image_data,
                content_type=content_type,
                is_primary=(index == 0 and not has_existing),
            ))
    return created
