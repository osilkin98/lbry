import sqlite3
import os


def do_migration(conf):
    db_path = os.path.join(conf.data_dir, 'lbrynet.sqlite')
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    current_columns = []
    for col_info in cursor.execute("pragma table_info('file');").fetchall():
        current_columns.append(col_info[1])

    if 'added_at' in current_columns:
        connection.close()
        print('already migrated')
        return

    # follow 12 step schema change procedure
    cursor.execute("pragma foreign_keys=off")

    # we don't have any indexes, views or triggers, so step 3 is skipped.
    cursor.execute("""
        DROP TABLE IF EXISTS NEW_FILE;
        CREATE TABLE IF NOT EXISTS NEW_FILE (
            stream_hash         TEXT PRIMARY KEY NOT NULL REFERENCES stream,
            file_name           TEXT,
            download_directory  TEXT,
            blob_data_rate      REAL NOT NULL,
            status              TEXT NOT NULL,
            saved_file          INTEGER NOT NULL,
            content_fee         TEXT,
            added_at            INTEGER NOT NULL
        );
        

    """)

    # step 5: transfer content from old to new
    cursor.execute("""
        INSERT INTO NEW_FILE 
        SELECT file.*, STRFTIME('%s', 'now') 
        FROM file
    """)

    # step 6: drop old table
    cursor.execute("DROP TABLE main.file")

    # step 7: rename new table to old table
    cursor.execute("ALTER TABLE NEW_FILE RENAME TO file")

    # step 8: we aren't using indexes, views or triggers so skip
    # step 9: no views so skip
    # step 10: foreign key check
    cursor.execute("pragma foreign_key_check;")

    # step 11: commit transaction
    connection.commit()

    # step 12: re-enable foreign keys
    connection.execute("pragma foreign_keys=on;")

    # done :)
    connection.close()
