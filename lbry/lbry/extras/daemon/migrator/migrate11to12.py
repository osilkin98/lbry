import sqlite3
import os


def do_migration(conf):
    db_path = os.path.join(conf.data_dir, 'lbrynet.sqlite')
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.executescript('alter table file add column added_at integer')
    cursor.execute("UPDATE file SET added_at = strftime('%s', 'now')")
    connection.commit()
    connection.close()
