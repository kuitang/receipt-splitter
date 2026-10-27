"""Check the built production artifact, including codecs hidden from pip audits."""
import io
import hashlib
import json
from importlib.metadata import version
import importlib.util
import platform
from pathlib import Path
import re
import ssl
import xml.parsers.expat

import certifi
from cryptography import x509
from cryptography.hazmat.backends.openssl.backend import backend
from packaging.version import Version
from PIL import Image, features
import pillow_heif

assert Version(platform.python_version()) >= Version("3.13.18")
assert importlib.util.find_spec("pip") is None, "Build-only pip must not ship"
assert Version(version("pillow-heif")) >= Version("1.8.1")
assert Version(version("certifi")) >= Version("2026.10.23")
info = pillow_heif.libheif_info()
assert Version(info["libheif"]) >= Version("1.23.7"), info
assert Version(re.search(r"version ([0-9.]+)", info["decoders"]["libde265"]).group(1)) >= Version("1.1.3"), info
pillow_heif.register_heif_opener()
encoded = io.BytesIO()
Image.new("RGB", (16, 24), (240, 240, 240)).save(encoded, format="HEIF")
encoded.seek(0)
with Image.open(encoded) as decoded:
    decoded.load()
    assert decoded.size == (16, 24)
    jpeg = io.BytesIO()
    decoded.convert("RGB").save(jpeg, format="JPEG")
    jpeg.seek(0)
    assert Image.open(jpeg).size == (16, 24)
for label, path in [("certifi", certifi.where()), ("system", "/etc/ssl/certs/ca-certificates.crt")]:
    certificates = x509.load_pem_x509_certificates(Path(path).read_bytes())
    names = [c.subject.rfc4514_string() for c in certificates]
    assert not any("emsigneccrootcag3" in re.sub("[^a-z0-9]", "", name.lower()) for name in names)
    print(label, len(certificates), "certificates; compromised emSign ECC Root CA - G3 absent")
print("Python", platform.python_version(), "system TLS", ssl.OPENSSL_VERSION, "Expat", xml.parsers.expat.EXPAT_VERSION)
print("Cryptography TLS", backend.openssl_version_text())
print("Native HEIF", info)
print("Pillow", version("Pillow"), {f: features.version(f) for f in ["jpg", "webp", "libtiff", "zlib", "jpg_2000"]})
print("Permitted HEIC encode/decode/JPEG conversion passed; runtime pip absent")

manifest = json.loads(Path("/opt/heif/share/native-sources.json").read_text())
assert manifest["versions"] == {"libheif": "1.23.7", "libde265": "1.1.3", "x265": "4.3"}
print("Native source provenance", manifest)
for library in sorted(Path("/opt/heif/lib").glob("*.so*")):
    if library.is_file() and not library.is_symlink():
        print("Native SHA256", library.name, hashlib.sha256(library.read_bytes()).hexdigest())
