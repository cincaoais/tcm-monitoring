"""One-off: drop the placeholder `tcm log` rows (identical values copy-pasted from an
example command). They pair with watch data and pollute `tcm converge` with a
time-confounded correlation. Delete this file once it has been run."""
import sqlite3

CUTOFF = "2026-08-01"   # rows on/after this date are removed

conn = sqlite3.connect("tcm.db")
rows = conn.execute(
    "SELECT date, sleep_quality, energy, stress, note FROM context "
    "WHERE date >= ? ORDER BY date", (CUTOFF,)).fetchall()

if not rows:
    print(f"Nothing to delete on/after {CUTOFF}.")
else:
    print(f"Deleting {len(rows)} self-rating row(s) on/after {CUTOFF}:")
    for d, sq, e, st, note in rows:
        print(f"  {d}  sleep={sq} energy={e} stress={st}  note={note!r}")
    conn.execute("DELETE FROM context WHERE date >= ?", (CUTOFF,))
    conn.commit()
    print(f"\nDeleted. {conn.execute('SELECT COUNT(*) FROM context').fetchone()[0]} row(s) remain.")
conn.close()
