import io

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, ImageSequence


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


def _square_crop_box(width, height):
    """Center-crop box (left, top, right, bottom) for a square of side min(w, h)."""
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return (left, top, left + side, top + side)


def process_avatar(uploaded_file, allow_animation=False):
    """Validate and normalise an uploaded avatar into a square WebP ContentFile.

    By default (``allow_animation=False``) the result is always a single-frame
    WebP resized to ``AVATAR_SIZE_PX``.

    When ``allow_animation=True`` and the source is an animated GIF (more than
    one frame), the result is an *animated* WebP: every frame is center-cropped
    and downscaled to ``AVATAR_SIZE_PX`` (never upscaled beyond it), preserving
    loop and per-frame duration.

    Raises ValueError on invalid (non-image, corrupt or oversized) input.
    """
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > settings.AVATAR_MAX_BYTES:
        raise ValueError("Avatar file is too large.")

    header = uploaded_file.read(12)
    uploaded_file.seek(0)
    if _detect_image_type(header) is None:
        raise ValueError("Not a supported image (JPEG/PNG/GIF/WebP).")

    target = settings.AVATAR_SIZE_PX

    _prev_max = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = settings.CHAT_IMAGE_MAX_PIXELS
    try:
        img = Image.open(uploaded_file)

        is_animated = (
            allow_animation
            and getattr(img, "is_animated", False)
            and getattr(img, "n_frames", 1) > 1
        )

        buf = io.BytesIO()
        if is_animated:
            frames = []
            durations = []
            for frame in ImageSequence.Iterator(img):
                fr = frame.convert("RGB")
                fr = fr.crop(_square_crop_box(*fr.size))
                fr = fr.resize((target, target), Image.LANCZOS)
                frames.append(fr)
                durations.append(frame.info.get("duration", 100))

            first, rest = frames[0], frames[1:]
            first.save(
                buf,
                format="WEBP",
                quality=82,
                method=4,
                save_all=True,
                append_images=rest,
                loop=img.info.get("loop", 0),
                duration=durations,
            )
        else:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img = img.crop(_square_crop_box(*img.size))
            img = img.resize((target, target), Image.LANCZOS)
            img.save(buf, format="WEBP", quality=82, method=4)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not process avatar image.") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = _prev_max

    return ContentFile(buf.getvalue(), name="avatar.webp")
