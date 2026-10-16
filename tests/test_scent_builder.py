import os
from shibaclaw.agent.context import ScentBuilder


def test_scent_builder_image_encoding_cache(tmp_path):
    builder = ScentBuilder(tmp_path)

    # Create a dummy fake image
    fake_img = tmp_path / "test.png"
    fake_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20)

    # First encoding pass
    res1 = builder._build_user_content("hello", [str(fake_img)])
    assert isinstance(res1, list)
    assert res1[0]["type"] == "image_url"
    assert "data:image/png;base64," in res1[0]["image_url"]["url"]

    # Change file bytes but match st_mtime précisément (or very close with 0ns step)
    # Reading should be CACHED, returning the OLD cached value
    cached_b64 = res1[0]["image_url"]["url"]

    # Overwrite the image with different content but keep mtime to verify cache hit
    stat1 = fake_img.stat()
    fake_img.write_bytes(b"\x89PNG\r\n\x1a\n\x01\x01\x01\rIHDR" + b"different content")
    os.utime(fake_img, ns=(stat1.st_atime_ns, stat1.st_mtime_ns))

    res2 = builder._build_user_content("hello", [str(fake_img)])
    assert res2[0]["image_url"]["url"] == cached_b64

    # Now change modification time; should invalidate cache and compute a fresh value
    os.utime(fake_img, ns=(stat1.st_atime_ns, stat1.st_mtime_ns + 5_000_000_000))
    res3 = builder._build_user_content("hello", [str(fake_img)])
    assert res3[0]["image_url"]["url"] != cached_b64


def test_scent_builder_image_cache_eviction(tmp_path):
    builder = ScentBuilder(tmp_path)
    paths = []
    for i in range(35):
        img_path = tmp_path / f"test_{i}.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20)
        paths.append(str(img_path))

    builder._build_user_content("hello", paths)

    assert len(builder._image_cache) == 32
    assert str((tmp_path / "test_0.png").resolve()) not in builder._image_cache
    assert str((tmp_path / "test_2.png").resolve()) not in builder._image_cache
    assert str((tmp_path / "test_3.png").resolve()) in builder._image_cache
    assert str((tmp_path / "test_34.png").resolve()) in builder._image_cache


def test_static_prompt_loads_active_profile_memory(tmp_path):
    builder = ScentBuilder(tmp_path)
    builder.memory.memory_file.write_text("Private trading plans", encoding="utf-8")
    (tmp_path / "memory" / "DUNGEON.md").write_text("Dungeon campaign notes", encoding="utf-8")

    dungeon = builder.build_static_prompt(profile_id="dungeon")
    default = builder.build_static_prompt(profile_id="default")

    assert "Dungeon campaign notes" in dungeon
    assert "Private trading plans" not in dungeon
    assert "Private trading plans" in default
    assert "Dungeon campaign notes" not in default

