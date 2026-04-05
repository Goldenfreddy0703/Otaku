#!/usr/bin/env python3
"""
String ID Renumbering Script for Kodi Addon
This script renumbers string IDs in strings.po and updates all references across the workspace.
Uses a temporary marker (+) to avoid conflicts during the renumbering process.
"""

import re
from pathlib import Path

# Configuration
STRINGS_PO_PATH = r"resources\language\resource.language.en_gb\strings.po"
WORKSPACE_ROOT = Path(__file__).parent
ID_MARKER = "+"  # Temporary marker to prevent ID conflicts during renumbering
START_ID = 30000  # Starting ID for renumbering

# File extensions to search for string ID references
SEARCH_EXTENSIONS = ['.py', '.xml', '.po']

# Files/directories to exclude from search
EXCLUDE_PATTERNS = ['__pycache__', '.git', 'renumber_string_ids.py']


def should_exclude(path):
    """Check if path should be excluded from processing."""
    path_str = str(path)
    return any(exclude in path_str for exclude in EXCLUDE_PATTERNS)


def extract_string_ids(strings_po_path):
    """Extract all string IDs from strings.po file in order."""
    string_ids = []

    with open(strings_po_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all msgctxt entries with IDs
    pattern = r'msgctxt\s+"#(\d+)"'
    matches = re.finditer(pattern, content)

    for match in matches:
        string_id = match.group(1)
        string_ids.append(string_id)

    return string_ids


def create_id_mapping(string_ids, start_id):
    """Create mapping from old IDs to new IDs."""
    mapping = {}
    new_id = start_id

    for old_id in string_ids:
        mapping[old_id] = str(new_id)
        new_id += 1

    return mapping


def find_all_files(workspace_root, extensions):
    """Find all files with specified extensions in workspace."""
    files = []

    for ext in extensions:
        for file_path in workspace_root.rglob(f'*{ext}'):
            if not should_exclude(file_path):
                files.append(file_path)

    return files


def apply_temporary_markers(files, id_mapping):
    """
    Step 1: For each ID, find and replace with marked version.
    Example: Find "30042" -> Replace with "3+0+1+4+2"
    """
    print(f"\n{'=' * 60}")
    print("STEP 1: Replacing old IDs with marked new IDs")
    print(f"{'=' * 60}")

    changes_made = {}

    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content
            file_changes = []

            # For each old ID, do a simple global find/replace
            for old_id, new_id in id_mapping.items():
                # Create marked ID with + between each digit
                marked_id = '+'.join(new_id)  # "30142" -> "3+0+1+4+2"

                # Count occurrences
                count = content.count(old_id)

                if count > 0:
                    # Global find and replace
                    content = content.replace(old_id, marked_id)
                    file_changes.append(f"  {old_id} -> {marked_id} ({count} times)")

            # Save if changed
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                changes_made[str(file_path)] = file_changes
                print(f"\n✓ Updated: {file_path.relative_to(WORKSPACE_ROOT)}")
                for change in file_changes[:5]:
                    print(change)
                if len(file_changes) > 5:
                    print(f"  ... and {len(file_changes) - 5} more changes")

        except Exception as e:
            print(f"\n✗ Error processing {file_path}: {e}")

    return changes_made


def remove_temporary_markers(files, id_mapping):
    """
    Step 2: For each new ID, remove the + signs.
    Example: Find "3+0+1+4+2" -> Replace with "30142"
    """
    print(f"\n{'=' * 60}")
    print("STEP 2: Removing + signs from new IDs")
    print(f"{'=' * 60}")

    changes_made = {}

    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content
            total_replacements = 0

            # For each new ID, find the marked version and replace with clean version
            for old_id, new_id in id_mapping.items():
                marked_id = '+'.join(new_id)  # "3+0+1+4+2"
                clean_id = new_id              # "30142"

                # Count occurrences
                count = content.count(marked_id)

                if count > 0:
                    # Global find and replace
                    content = content.replace(marked_id, clean_id)
                    total_replacements += count

            # Save if changed
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                changes_made[str(file_path)] = total_replacements
                print(f"✓ Cleaned {total_replacements} marked IDs in: {file_path.relative_to(WORKSPACE_ROOT)}")

        except Exception as e:
            print(f"✗ Error processing {file_path}: {e}")

    return changes_made


def main():
    """Main execution function."""
    print(f"\n{'#' * 60}")
    print("STRING ID RENUMBERING SCRIPT")
    print(f"{'#' * 60}")
    print(f"Workspace: {WORKSPACE_ROOT}")
    print(f"Starting ID: {START_ID}")
    print(f"Temporary marker: '{ID_MARKER}'")

    # Check if strings.po exists
    strings_po_full_path = WORKSPACE_ROOT / STRINGS_PO_PATH
    if not strings_po_full_path.exists():
        print(f"\n✗ ERROR: strings.po not found at {strings_po_full_path}")
        return

    # Extract current string IDs
    print(f"\nExtracting string IDs from {STRINGS_PO_PATH}...")
    string_ids = extract_string_ids(strings_po_full_path)
    print(f"✓ Found {len(string_ids)} string IDs")

    if not string_ids:
        print("✗ No string IDs found. Exiting.")
        return

    # Create ID mapping
    print(f"\nCreating ID mapping (starting from {START_ID})...")
    id_mapping = create_id_mapping(string_ids, START_ID)
    print(f"✓ Created mapping for {len(id_mapping)} IDs")
    print(f"  First ID: {string_ids[0]} -> {id_mapping[string_ids[0]]}")
    print(f"  Last ID:  {string_ids[-1]} -> {id_mapping[string_ids[-1]]}")

    # Find all files to process
    print("\nSearching for files to process...")
    files = find_all_files(WORKSPACE_ROOT, SEARCH_EXTENSIONS)
    print(f"✓ Found {len(files)} files to process")

    # Confirm before proceeding
    print(f"\n{'=' * 60}")
    print("READY TO START RENUMBERING")
    print(f"{'=' * 60}")
    print("This will:")
    print(f"  1. Replace {len(id_mapping)} IDs with + markers (e.g., 30042 -> 3+0+1+4+2)")
    print(f"  2. Update references in {len(files)} files")
    print("  3. Remove all + signs to finalize new IDs")
    print("\nPress Enter to continue, or Ctrl+C to cancel...")
    input()

    # Step 1: Replace old IDs with marked new IDs
    step1_changes = apply_temporary_markers(files, id_mapping)
    print(f"\n✓ Step 1 complete: Modified {len(step1_changes)} files")

    # Step 2: Remove + signs from marked IDs
    step2_changes = remove_temporary_markers(files, id_mapping)
    print(f"\n✓ Step 2 complete: Cleaned markers in {len(step2_changes)} files")

    # Summary
    print(f"\n{'#' * 60}")
    print("RENUMBERING COMPLETE!")
    print(f"{'#' * 60}")
    print(f"✓ Successfully renumbered {len(id_mapping)} string IDs")
    print(f"✓ Updated {len(step1_changes)} files")
    print(f"✓ ID range: {START_ID} - {int(START_ID) + len(id_mapping) - 1}")
    print("\nPlease review the changes and test the addon.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Operation cancelled by user")
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
