import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

APK_NAME_REGEX = re.compile(r"tachiyomi-([^.]+)\.(.+)-v(.+)\.apk")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("apk_dir", type=Path)
    parser.add_argument("--pkg-name")
    parser.add_argument("--app-label")
    parser.add_argument("--nsfw", type=int)
    parser.add_argument("--lang")
    parser.add_argument("--version-code", type=int)
    parser.add_argument("--version-name")
    return parser.parse_args()

def extract_icon(zf, dst):
    candidates = []
    for name in zf.namelist():
        if "ic_launcher" in name.lower() and name.endswith(".png"):
            parts = name.split("/")
            score = 0
            for part in parts:
                if "mipmap" in part:
                    qualifiers = part.split("-")
                    for q in qualifiers:
                        if q == "xxxhdpi": score = 5
                        elif q == "xxhdpi" and score < 4: score = 4
                        elif q == "xhdpi" and score < 3: score = 3
                        elif q == "hdpi" and score < 2: score = 2
                        elif q == "mdpi" and score < 1: score = 1
            candidates.append((score, name))
    if not candidates:
        return None
    _, best = max(candidates, key=lambda x: x[0])
    with zf.open(best) as src, open(dst, "wb") as f:
        f.write(src.read())
    return best

def extract_via_aapt(apk):
    badging = subprocess.check_output(
        ["aapt", "dump", "--include-meta-data", "badging", str(apk)]
    ).decode()
    pkg = re.search(r"package: name='([^']+)'", badging).group(1)
    code = int(re.search(r"versionCode='([^']+)'", badging).group(1))
    ver = re.search(r"versionName='([^']+)'", badging).group(1)
    nsfw = int(re.search(r"'tachiyomi.extension.nsfw' value='([^']+)'", badging).group(1))
    label = re.search(r"^application-label:'([^']+)'", badging, re.MULTILINE).group(1)
    icon = re.search(r"^application-icon-320:'([^']+)'", badging, re.MULTILINE).group(1)
    lang = re.search(r"tachiyomi-([^.]+)", apk.name).group(1)
    return pkg, code, ver, nsfw, label, icon, lang

def main():
    args = parse_args()
    repo_dir = Path("repo")
    repo_apk_dir = repo_dir / "apk"
    repo_icon_dir = repo_dir / "icon"
    repo_apk_dir.mkdir(parents=True, exist_ok=True)
    repo_icon_dir.mkdir(parents=True, exist_ok=True)

    index_data = []

    for apk in sorted(args.apk_dir.rglob("*.apk")):
        apk_name = apk.name
        shutil.copy2(apk, repo_apk_dir / apk_name)

        ded_args = args.pkg_name and args.app_label and args.nsfw is not None and args.lang and args.version_code and args.version_name

        if ded_args:
            pkg = args.pkg_name
            code = args.version_code
            ver = args.version_name
            nsfw = args.nsfw
            label = args.app_label
            lang = args.lang
            with ZipFile(apk) as z:
                extract_icon(z, repo_icon_dir / f"{pkg}.png")
        else:
            try:
                pkg, code, ver, nsfw, label, icon_path, lang = extract_via_aapt(apk)
                with ZipFile(apk) as z, z.open(icon_path) as src, \
                     open(repo_icon_dir / f"{pkg}.png", "wb") as f:
                    f.write(src.read())
            except FileNotFoundError:
                print("ERROR: aapt not found and no metadata args provided", file=sys.stderr)
                sys.exit(1)

        index_data.append({
            "name": label,
            "pkg": pkg,
            "apk": apk_name,
            "lang": lang,
            "code": code,
            "version": ver,
            "nsfw": nsfw,
            "sources": [],
        })

    (repo_dir / "index.min.json").write_text(
        json.dumps(index_data, ensure_ascii=False, separators=(",", ":"))
    )

if __name__ == "__main__":
    main()
