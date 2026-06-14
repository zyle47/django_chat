import io

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def _detect_image_type(header):
    if header[:3] == b"\xff\xd8\xff":
        return "jpg"
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if header[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def process_avatar(uploaded_file):
    """Validate and normalise an uploaded avatar into a square WebP ContentFile.

    Raises ValueError on invalid (non-image, corrupt or oversized) input.
    """
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > settings.AVATAR_MAX_BYTES:
        raise ValueError("Avatar file is too large.")

    header = uploaded_file.read(12)
    uploaded_file.seek(0)
    if _detect_image_type(header) is None:
        raise ValueError("Not a supported image (JPEG/PNG/GIF/WebP).")

    _prev_max = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = settings.CHAT_IMAGE_MAX_PIXELS
    try:
        img = Image.open(uploaded_file)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")

        # Center-crop to a square before resizing.
        width, height = img.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        img = img.crop((left, top, left + side, top + side))

        target = settings.AVATAR_SIZE_PX
        img = img.resize((target, target), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=82, method=4)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not process avatar image.") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = _prev_max

    return ContentFile(buf.getvalue(), name="avatar.webp")
