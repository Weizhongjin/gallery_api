import io
import pytest
from PIL import Image
from app.image_processing import process_image, ImageVariants


def make_jpeg(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height), color=(255, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_process_image_returns_variants():
    data = make_jpeg(3000, 4000)
    result = process_image(data)
    assert isinstance(result, ImageVariants)


def test_display_longest_side_is_1200():
    data = make_jpeg(3000, 4000)
    result = process_image(data)
    img = Image.open(io.BytesIO(result.display))
    assert max(img.width, img.height) == 1200


def test_thumb_longest_side_is_400():
    data = make_jpeg(3000, 4000)
    result = process_image(data)
    img = Image.open(io.BytesIO(result.thumb))
    assert max(img.width, img.height) == 400


def test_small_image_not_upscaled():
    data = make_jpeg(200, 300)
    result = process_image(data)
    display_img = Image.open(io.BytesIO(result.display))
    # display stays at original size (200x300), not upscaled to 1200
    assert display_img.width == 200
    assert display_img.height == 300


def test_original_dimensions_captured():
    data = make_jpeg(3000, 4000)
    result = process_image(data)
    assert result.original_width == 3000
    assert result.original_height == 4000


def test_rgba_converted_to_rgb():
    img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    result = process_image(data)
    out = Image.open(io.BytesIO(result.display))
    assert out.mode == "RGB"


def test_exif_orientation_is_applied_before_resize():
    img = Image.new("RGB", (100, 60), color=(20, 30, 40))
    exif = img.getexif()
    # EXIF Orientation=6 means rotate 90° clockwise for correct display.
    exif[274] = 6
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)

    result = process_image(buf.getvalue())
    display_img = Image.open(io.BytesIO(result.display))

    # After orientation normalization, portrait should be preserved.
    assert display_img.width == 60
    assert display_img.height == 100
