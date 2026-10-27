"""Record the verified codec sources and reject host-specific compiler flags."""
import ast
import json
from pathlib import Path

values = {}
for node in ast.parse(Path("/tmp/build_native_heif.py").read_text()).body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {"SOURCES", "RECIPE_SHA256", "RECIPE_URL"}:
                values[target.id] = ast.literal_eval(node.value)
flags = [*Path("/tmp/ph_build_stuff").rglob("flags.make"), *Path("/tmp/ph_build_stuff").rglob("CMakeCache.txt")]
assert flags, "Native compiler configuration must be recorded"
for path in flags:
    contents = path.read_text()
    assert "-march=native" not in contents and "-mtune=native" not in contents, path
values["versions"] = {"libheif": "1.23.7", "libde265": "1.1.3", "x265": "4.3"}
values["portable_compiler_configuration_files_checked"] = len(flags)
Path("/opt/heif/share/native-sources.json").write_text(json.dumps(values, indent=2) + "\n")
print("Pinned native sources recorded; no build-host-specific march/mtune flags")
