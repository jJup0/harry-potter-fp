# Screenplays Merged - Best Available Source Per Film

Symlinks to the best available screenplay text for each film.

| Film | Source | Why |
|------|--------|-----|
| 1_philosophers_stone.txt | v1 (fandom wiki) | Fan transcript with character names + action descriptions |
| 2_chamber_of_secrets.txt | v2 (Aitor's PDF) | Full screenplay from Aitor's PDF, clean extraction |
| 3_prisoner_of_azkaban.txt | v3 (Script Slug) | Steve Kloves Full Tan Draft (Feb 2003). v1 had no character attribution, v2 was garbled |
| 4_goblet_of_fire.txt | v1 (fandom wiki) | Fan transcript with character names + actions. v2 was truncated, v3 has OCR artifacts |
| 5_order_of_the_phoenix.txt | v1 (fandom wiki) | Fan transcript with character names + actions. v2 had issues, v3 has control chars |
| 6_half_blood_prince.txt | v2 (Aitor's PDF) | Full screenplay from Aitor's PDF, clean extraction |
| 7_deathly_hallows_p1.txt | v2 (Aitor's PDF) | Full screenplay from Aitor's PDF, clean extraction |
| 8_deathly_hallows_p2.txt | v2 (Aitor's PDF) | Full screenplay from Aitor's PDF, clean extraction |

## Source Directories

- `screenplays/` (v1) - Fan-curated transcripts from fandom wiki. Format: `[action descriptions]` + `Character: Dialogue`
- `screenplays_v2/` (v2) - Text extracted from Aitor's screenplay PDFs. Format: proper screenplay (INT/EXT, character names, dialogue)
- `screenplays_v3/` (v3) - PDFs from Script Slug (scriptslug.com), text extracted via PyMuPDF. Format: proper screenplay but some have OCR issues

## Notes

- HP3 is the only film where v3 is the best option (v1 lacked character names, v2 was unusable)
- v1 fan transcripts are preferred for HP1/4/5 because they have clean character attribution and action context despite not being "official" screenplays
- v2 is preferred for HP2/6/7/8 because Aitor's PDFs extracted cleanly for those films
