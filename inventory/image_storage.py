import io
import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image

try:
    import vercel_blob
except ImportError:  # pragma: no cover - only missing in unusual envs
    vercel_blob = None


class ImageValidationError(ValidationError):
    pass


def validate_uploaded_image(uploaded_file):
    """
    Validate file extension and size. Raises ImageValidationError with a
    user-friendly message on failure.
    """
    if uploaded_file is None:
        return

    ext = os.path.splitext(uploaded_file.name)[1].lower().lstrip(".")
    if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        raise ImageValidationError(
            "Unsupported image type. Please upload a JPG, JPEG, PNG, or WEBP file."
        )

    if uploaded_file.size > settings.MAX_IMAGE_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_IMAGE_UPLOAD_SIZE_BYTES / (1024 * 1024)
        raise ImageValidationError(f"Image is too large. Maximum allowed size is {max_mb:.0f}MB.")

    try:
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        img.verify()
    except Exception:
        raise ImageValidationError("The uploaded file is not a valid image.")
    finally:
        uploaded_file.seek(0)


def _resize_if_needed(uploaded_file):
    """
    Resize the image so its longest side is at most MAX_IMAGE_DIMENSION,
    and re-encode it to keep upload size reasonable. Returns (bytes, content_type).
    """
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    img_format = (img.format or "JPEG").upper()

    # Normalize mode for JPEG output (no alpha channel support).
    if img_format == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    max_dim = settings.MAX_IMAGE_DIMENSION
    width, height = img.size
    if max(width, height) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    buffer = io.BytesIO()
    save_kwargs = {}
    if img_format in ("JPEG", "JPG"):
        save_kwargs = {"quality": 85, "optimize": True}
        img_format = "JPEG"
    elif img_format == "PNG":
        save_kwargs = {"optimize": True}
    elif img_format == "WEBP":
        save_kwargs = {"quality": 85}

    img.save(buffer, format=img_format, **save_kwargs)
    buffer.seek(0)

    content_type_map = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
    return buffer.read(), content_type_map.get(img_format, "image/jpeg")


def upload_product_image(uploaded_file):
    """
    Validate, resize, and upload an image to Vercel Blob.
    Returns (url, pathname) on success.
    Raises ImageValidationError on validation failure, or RuntimeError if
    the upload to Vercel Blob fails.
    """
    validate_uploaded_image(uploaded_file)
    data, content_type = _resize_if_needed(uploaded_file)

    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(
        content_type, "jpg"
    )
    pathname = f"products/{uuid.uuid4().hex}.{ext}"

    if vercel_blob is None or not settings.BLOB_READ_WRITE_TOKEN:
        raise RuntimeError(
            "Vercel Blob is not configured. Set the BLOB_READ_WRITE_TOKEN environment variable."
        )

    try:
        result = vercel_blob.put(
            pathname,
            data,
            options={
                "contentType": content_type,
                "token": settings.BLOB_READ_WRITE_TOKEN,
                "addRandomSuffix": "false",
            },
        )
    except Exception as exc:  # pragma: no cover - network/service errors
        raise RuntimeError(f"Failed to upload image: {exc}")

    url = result.get("url") if isinstance(result, dict) else None
    if not url:
        raise RuntimeError("Vercel Blob did not return an image URL.")

    return url, pathname


def delete_product_image(pathname):
    """
    Best-effort delete of a blob by pathname. Never raises — image cleanup
    failures should not block product edits/deletes.
    """
    if not pathname or vercel_blob is None or not settings.BLOB_READ_WRITE_TOKEN:
        return
    try:
        vercel_blob.delete(pathname, options={"token": settings.BLOB_READ_WRITE_TOKEN})
    except Exception:
        # Orphaned blobs are acceptable; failing the request is not.
        pass
