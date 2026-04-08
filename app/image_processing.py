import io
from dataclasses import dataclass

from PIL import Image


@dataclass
class ImageVariants:
    original_width: int
    original_height: int
    display: bytes   # JPEG, 1200px longest side
    thumb: bytes     # JPEG, 400px longest side


def process_image(data: bytes) -> ImageVariants:
    img = Image.open(io.BytesIO(data))
    if img.mode != "RGB":
        img = img.convert("RGB")

    original_width, original_height = img.size

    display_img = _resize(img, 1200)
    thumb_img = _resize(img, 400)

    return ImageVariants(
        original_width=original_width,
        original_height=original_height,
        display=_to_jpeg(display_img),
        thumb=_to_jpeg(thumb_img),
    )


def _resize(img: Image.Image, max_size: int) -> Image.Image:
    longest = max(img.width, img.height)
    if longest <= max_size:
        return img
    ratio = max_size / longest
    new_size = (round(img.width * ratio), round(img.height * ratio))
    return img.resize(new_size, Image.LANCZOS)


def _to_jpeg(img: Image.Image, quality: int = 85) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()
