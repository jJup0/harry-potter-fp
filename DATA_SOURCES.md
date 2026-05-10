# Data Sources Quality Assessment

## Books (v1)

All 7 books as plain text files from GitHub. Clean, complete, no issues.

| Book | File | Size | Status |
|------|------|------|--------|
| 1. Philosopher's Stone | `data/raw/books/1_philosophers_stone.txt` | 438KB | Good |
| 2. Chamber of Secrets | `data/raw/books/2_chamber_of_secrets.txt` | 510KB | Good |
| 3. Prisoner of Azkaban | `data/raw/books/3_prisoner_of_azkaban.txt` | 632KB | Good |
| 4. Goblet of Fire | `data/raw/books/4_goblet_of_fire.txt` | 1.1MB | Good |
| 5. Order of the Phoenix | `data/raw/books/5_order_of_the_phoenix.txt` | 1.5MB | Good |
| 6. Half-Blood Prince | `data/raw/books/6_half_blood_prince.txt` | 994KB | Good |
| 7. Deathly Hallows | `data/raw/books/7_deathly_hallows.txt` | 1.2MB | Good |

Known issue: Book 2 chapter detection only finds 10/18 chapters due to inconsistent heading formatting. Paragraphs are still captured regardless.

## Screenplays - v2 (Aitor's PDFs, preferred)

Extracted from actual screenplay PDFs provided by Aitor. These have proper INT/EXT scene markers, character names in caps, and stage directions.

| Film | File | Lines | Status |
|------|------|-------|--------|
| 1. Philosopher's Stone | `data/raw/screenplays_v2/1_philosophers_stone.txt` | 3,395 | Good |
| 2. Chamber of Secrets | `data/raw/screenplays_v2/2_chamber_of_secrets.txt` | 11,089 | Good |
| 3. Prisoner of Azkaban | `data/raw/screenplays_v2/3_prisoner_of_azkaban.txt` | 451 | BAD - web scrape junk, not a screenplay |
| 4. Goblet of Fire | `data/raw/screenplays_v2/4_goblet_of_fire.txt` | 1,349 | BAD - web scrape junk, not a screenplay |
| 5. Order of the Phoenix | `data/raw/screenplays_v2/5_order_of_the_phoenix.txt` | 9,715 | Good |
| 6. Half-Blood Prince | `data/raw/screenplays_v2/6_half_blood_prince.txt` | 7,178 | Good |
| 7. Deathly Hallows P1 | `data/raw/screenplays_v2/7_deathly_hallows_p1.txt` | 6,735 | Good |
| 8. Deathly Hallows P2 | `data/raw/screenplays_v2/8_deathly_hallows_p2.txt` | 6,836 | Good |

HP3 and HP4 v2 files are Wayback Machine scrapes of IMSDb, not Aitor's PDFs. They contain website navigation HTML, not screenplay text.

## Screenplays - v1 (Fandom Wiki transcripts, fallback)

Fan-transcribed dialogue from the Harry Potter Wiki. Format: `[stage direction]` + `Character: Dialogue`. No INT/EXT markers. Used as fallback where v2 is unusable.

| Film | File | Lines | Status |
|------|------|-------|--------|
| 1. Philosopher's Stone | `data/raw/screenplays/1_philosophers_stone.txt` | 1,543 | OK (used as fallback for v2 which is smaller) |
| 2. Chamber of Secrets | `data/raw/screenplays/2_chamber_of_secrets.txt` | 1,994 | OK |
| 3. Prisoner of Azkaban | `data/raw/screenplays/3_prisoner_of_azkaban.txt` | 6,389 | Best available for HP3 |
| 4. Goblet of Fire | `data/raw/screenplays/4_goblet_of_fire.txt` | 1,571 | Best available for HP4 |
| 5. Order of the Phoenix | `data/raw/screenplays/5_order_of_the_phoenix.txt` | 954 | OK |
| 6. Half-Blood Prince | `data/raw/screenplays/6_half_blood_prince.txt` | 1,367 | OK |
| 7. Deathly Hallows P1 | `data/raw/screenplays/7_deathly_hallows_p1.txt` | 1,259 | OK |
| 8. Deathly Hallows P2 | `data/raw/screenplays/8_deathly_hallows_p2.txt` | 901 | OK |

## Which screenplay source is used per film

The corpus builder uses v2 where available and falls back to v1:

| Film | Source used | Quality |
|------|-------------|---------|
| HP1 | v2 (PDF) | Good |
| HP2 | v2 (PDF) | Good |
| HP3 | v1 (wiki) | Mediocre - fan transcript, not official screenplay |
| HP4 | v1 (wiki) | Mediocre - fan transcript, not official screenplay |
| HP5 | v2 (PDF) | Good |
| HP6 | v2 (PDF) | Good |
| HP7.1 | v2 (PDF) | Good |
| HP7.2 | v2 (PDF) | Good |

## Metrics (Aitor's xlsx)

| Data | File | Status |
|------|------|--------|
| Screen time (minutes per character per film) | `data/metrics/screen_time.json` | Good - missing Harry/Ron/Hermione (estimated) |
| Book mentions (count per character per book) | `data/metrics/book_mentions.json` | Good |

## Impact on scoring accuracy

Characters primarily appearing in HP3/HP4 have thinner film corpus data. This affects:
- Remus Lupin (HP3 is his main film)
- Sirius Black (HP3 introduction)
- Peter Pettigrew (HP3 reveal)
- Buckbeak (HP3 only)
- Barty Crouch Sr/Jr (HP4)
- Cedric Diggory (HP4)
- Viktor Krum (HP4)
- Fleur Delacour (HP4)
- Mad-Eye Moody (HP4 introduction)

These characters still have book corpus data and some film data from other films, but their HP3/HP4 film scenes are from fan transcripts rather than official screenplays.
