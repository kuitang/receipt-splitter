"""Build HEIF codecs from checksum-pinned upstream sources, with no unchecked downloads.

Uses pillow-heif v1.8.1's upstream build options (including 8/10/12-bit HEVC)
with the security-fixed libheif release. Runtime contains only the built codecs.
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import tarfile
from urllib.request import urlopen

RECIPE_URL = "https://raw.githubusercontent.com/bigcat88/pillow_heif/0ed53791bef34eeda0182b7a26476f99445922de/libheif/build_libs.py"
RECIPE_SHA256 = "ae73745b83b9f3da0e65223e940de55df1c3b3f5add3de397e29fe0ef8857588"
SOURCES = {
    "https://github.com/Multicorewareinc/x265/releases/download/4.3/x265_4.3.tar.gz": "83c53e4c8bbb8f1e33ed59e10a7d621d1d7801ca853910c3eb41f038b8ffb121",
    "https://github.com/strukturag/libde265/releases/download/v1.1.3/libde265-1.1.3.tar.gz": "554228bd17788c99a7e63b37ab5634722190e6e2bf60c1dcb01cef328e133905",
    "https://github.com/strukturag/libheif/releases/download/v1.23.7/libheif-1.23.7.tar.gz": "f7483e818503ea6224c8863e4a56ac02c7089021a98472c811c12aa19faf2475",
}


def fetch_verified(url, digest, destination):
    with urlopen(url, timeout=90) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError(f"Source checksum mismatch: {url}")
    destination.write_bytes(data)
    print("Verified native source", url, digest, flush=True)


def extract_verified(url, out_path, strip=True):
    # Reject any additional upstream download (including fallback tool installers).
    digest = SOURCES[url]
    destination = Path(out_path)
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "source.tar.gz"
    fetch_verified(url, digest, archive)
    unpacked = destination / "_verified_source"
    unpacked.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(unpacked, filter="data")
    archive.unlink()
    if strip:
        folders = list(unpacked.iterdir())
        if len(folders) != 1 or not folders[0].is_dir():
            raise RuntimeError("Unexpected source archive layout")
        top = folders[0]
        for item in top.iterdir():
            shutil.move(str(item), destination / item.name)
        top.rmdir()
        unpacked.rmdir()
    else:
        for item in unpacked.iterdir():
            shutil.move(str(item), destination / item.name)
        unpacked.rmdir()
    licenses = Path(os.environ["INSTALL_DIR_LIBS"]) / "share/licenses" / destination.name
    licenses.mkdir(parents=True, exist_ok=True)
    for pattern in ["COPYING*", "LICENSE*", "source/COPYING*"]:
        for license_file in destination.glob(pattern):
            if license_file.is_file():
                shutil.copy2(license_file, licenses / license_file.name)


recipe_path = Path("/tmp/pillow_heif_native_recipe.py")
fetch_verified(RECIPE_URL, RECIPE_SHA256, recipe_path)
spec = importlib.util.spec_from_file_location("heif_native_recipe", recipe_path)
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)
recipe.LIBHEIF_URL = next(url for url in SOURCES if "libheif-1.23.7" in url)
recipe.download_extract_to = extract_verified
recipe.build_libs()
