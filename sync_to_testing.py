import subprocess
import os
import shutil

# Source and destination base directories (swapped)
src_base = r"C:\Users\jenki\Documents\Github\Otaku"
dst_base = r"C:\Users\jenki\Documents\Github\Otaku-Testing\plugin.video.otaku.testing"

# Files to exclude
exclude_files = {"addon.xml", "changelog.txt", "news.txt", "sync_to_testing.py"}

def get_changed_files():
    try:
        result = subprocess.check_output(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            text=True,
            cwd=src_base
        ).strip().splitlines()
        return result
    except subprocess.CalledProcessError as e:
        print("Error: Could not get changed files from git.")
        print(e)
        return []

def copy_files(files):
    for rel_path in files:
        filename = os.path.basename(rel_path).lower()
        if filename in exclude_files:
            print(f"Skipping excluded file: {rel_path}")
            continue

        # Normalize and drop "plugin.video.otaku/"
        parts = rel_path.split("/")
        if parts[0] == "plugin.video.otaku":
            rel_path_fixed = os.path.join(*parts[1:])
        else:
            rel_path_fixed = os.path.join(*parts)

        src = os.path.join(src_base, rel_path)
        dst = os.path.join(dst_base, rel_path_fixed)

        if not os.path.exists(src):
            print(f"Source missing (skipped): {src}")
            continue

        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print(f"Copied {src} -> {dst}")

if __name__ == "__main__":
    changed_files = get_changed_files()
    if not changed_files:
        print("No changed files found in the last commit.")
    else:
        print("Files changed in last commit:")
        for f in changed_files:
            print(" -", f)
        print("\nCopying files...\n")
        copy_files(changed_files)
        print("\n✅ Done!")
