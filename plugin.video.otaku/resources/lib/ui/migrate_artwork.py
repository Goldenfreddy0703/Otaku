"""
Database migration utility to trim existing artwork entries.
This reduces database size and improves performance by applying new artwork limits
to legacy data that may contain 100+ images per anime.

Run this once after updating to the new artwork system to clean up existing data.
"""

import pickle
import random
from resources.lib.ui import database, control


def migrate_artwork_database():
    """
    Migrate existing artwork database entries to new optimized format.

    Changes applied:
    - Limits fanart arrays to artwork.fanart.count setting
    - Limits landscape/thumb arrays to 1 (users only need one thumbnail)
    - Converts clearart/clearlogo/banner/landscape arrays to single pre-selected strings
    - Removes banner/landscape/clearlogo if disabled in settings

    Returns:
        dict: Migration statistics (entries_processed, entries_updated, size_reduction_estimate)
    """
    # Read current artwork settings
    artwork_fanart_count = control.getInt('artwork.fanart.count')
    artwork_clearlogo_enabled = control.getBool('artwork.clearlogo')
    artwork_banner_enabled = control.getBool('artwork.banner')
    artwork_landscape_enabled = control.getBool('artwork.landscape')

    control.log("Starting artwork database migration...")
    control.log(f"Settings - Fanart limit: {artwork_fanart_count}")
    control.log(f"Settings - Clearlogo: {artwork_clearlogo_enabled}, Banner: {artwork_banner_enabled}, Landscape: {artwork_landscape_enabled}")

    stats = {
        'entries_processed': 0,
        'entries_updated': 0,
        'images_removed': 0,
        'errors': 0
    }

    # Get all show metadata entries
    try:
        with database.SQL(control.malSyncDB) as cursor:
            cursor.execute("SELECT mal_id, art, meta_ids FROM shows_meta")
            rows = cursor.fetchall()

            control.log(f"Found {len(rows)} metadata entries to process")

            for row in rows:
                stats['entries_processed'] += 1
                mal_id, art_blob, meta_ids_blob = row

                try:
                    # Unpickle existing art data
                    art = pickle.loads(art_blob)
                    meta_ids = pickle.loads(meta_ids_blob)

                    original_size = len(art_blob)
                    updated = False
                    images_before = 0
                    images_after = 0

                    # Count original images
                    for key in ['fanart', 'thumb', 'clearart', 'clearlogo', 'landscape', 'banner']:
                        if key in art and isinstance(art[key], list):
                            images_before += len(art[key])

                    # Apply fanart limit
                    if 'fanart' in art and isinstance(art['fanart'], list):
                        if len(art['fanart']) > artwork_fanart_count:
                            art['fanart'] = art['fanart'][:artwork_fanart_count]
                            updated = True

                    # Apply landscape/thumb limit (always 1 - users only need one thumbnail)
                    if 'thumb' in art and isinstance(art['thumb'], list):
                        if len(art['thumb']) > 1:
                            art['thumb'] = art['thumb'][:1]
                            updated = True

                    # Convert clearart to single string
                    if 'clearart' in art and isinstance(art['clearart'], list) and art['clearart']:
                        art['clearart'] = random.choice(art['clearart'])
                        updated = True

                    # Convert clearlogo to single string (or remove if disabled)
                    if 'clearlogo' in art:
                        if not artwork_clearlogo_enabled:
                            del art['clearlogo']
                            updated = True
                        elif isinstance(art['clearlogo'], list) and art['clearlogo']:
                            art['clearlogo'] = random.choice(art['clearlogo'])
                            updated = True

                    # Convert landscape to single string (or remove if disabled)
                    if 'landscape' in art:
                        if not artwork_landscape_enabled:
                            del art['landscape']
                            updated = True
                        elif isinstance(art['landscape'], list) and art['landscape']:
                            art['landscape'] = random.choice(art['landscape'])
                            updated = True

                    # Remove banner if disabled
                    if 'banner' in art and not artwork_banner_enabled:
                        if isinstance(art['banner'], list) and art['banner']:
                            art['banner'] = random.choice(art['banner'])
                            updated = True
                        elif not artwork_banner_enabled:
                            del art['banner']
                            updated = True

                    # Count final images
                    for key in ['fanart', 'thumb']:
                        if key in art and isinstance(art[key], list):
                            images_after += len(art[key])
                    images_after += sum(1 for key in ['clearart', 'clearlogo', 'landscape', 'banner']
                                       if key in art and isinstance(art[key], str))

                    # Update database if changes were made
                    if updated:
                        new_art_blob = pickle.dumps(art)
                        new_size = len(new_art_blob)

                        cursor.execute(
                            "UPDATE shows_meta SET art = ? WHERE mal_id = ?",
                            (new_art_blob, mal_id)
                        )

                        stats['entries_updated'] += 1
                        stats['images_removed'] += (images_before - images_after)

                        size_reduction = original_size - new_size
                        if stats['entries_updated'] % 10 == 0:
                            control.log(f"Processed {stats['entries_updated']} entries... "
                                        f"(MAL ID {mal_id}: {images_before} -> {images_after} images, "
                                        f"{size_reduction} bytes saved)")

                except Exception as e:
                    stats['errors'] += 1
                    control.log(f"Error processing MAL ID {mal_id}: {str(e)}")
                    continue

            # Commit changes
            cursor.connection.commit()

            # Log final statistics
            control.log("=" * 60)
            control.log("Artwork Database Migration Complete!")
            control.log(f"Entries processed: {stats['entries_processed']}")
            control.log(f"Entries updated: {stats['entries_updated']}")
            control.log(f"Images removed: {stats['images_removed']}")
            control.log(f"Errors: {stats['errors']}")
            control.log(f"Estimated database size reduction: ~{stats['images_removed'] * 50}KB")
            control.log("=" * 60)

            # Show notification to user
            if stats['entries_updated'] > 0:
                control.notify(
                    heading="Artwork Migration Complete",
                    message=f"Optimized {stats['entries_updated']} entries, removed {stats['images_removed']} images",
                    time=5000
                )

            return stats

    except Exception as e:
        control.log(f"Migration failed: {str(e)}")
        stats['errors'] += 1
        control.notify(
            heading="Artwork Migration Failed",
            message=str(e),
            time=5000
        )
        return stats


if __name__ == '__main__':
    # Can be run directly for testing or called from addon
    migrate_artwork_database()
