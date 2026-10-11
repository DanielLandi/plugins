# Genre recipes

Starting points for a spec's `suno:` block; tune per song. Every song is an original: follow `originals.md`.
Each recipe: model · vocal · weirdness · style_influence · variety, then styles, exclude, a structure and the idiom
(what the lyrics sound like in that genre).

## synthwave-80s
- `v6` · vocal unset · weirdness 40 · style_influence 70 · variety normal
- styles: `1980s synthwave, retro analog synths, gated reverb drums, driving bassline, warm male vocal, cinematic night drive`
- exclude: `acoustic guitar, trap hi-hats, autotune, modern EDM drop`
- structure: Intro (synth arpeggio) · Verse · Pre-Chorus · Chorus · Verse · Pre-Chorus · Chorus · [Instrumental Break] synth solo · Final Chorus · Outro
- idiom: cities at night, roads, screens and signals, a wry or wistful hook; images that animate well.

## doo-wop-50s
- `v6` · vocal `male` · weirdness 30 · style_influence 75 · variety normal
- styles: `1950s doo-wop, male vocal group, close harmony, bass vocal, falsetto lead, upright bass`
- exclude: `female vocals, synthesizer, distorted guitar, modern drums`
- structure: [Intro] backing syllables + title · Verse · Chorus · Verse · Chorus · [Bridge] bass-voice "bom bom" · Chorus · [Outro] title tag
- idiom: backing "doo-wop / shoo-bop / ooh-wah" in parentheses; innocent romance, jukebox, small-town square.

## pop-80s
- `v6` · vocal unset · weirdness 40 · style_influence 65 · variety normal
- styles: `1980s synth-pop, gated reverb drums, bright analog synths, punchy bass, big catchy chorus`
- exclude: `acoustic folk, trap, autotune, modern EDM drop`
- structure: Intro · Verse · Pre-Chorus · Chorus · Verse · Pre-Chorus · Chorus · [Instrumental Break] saxophone solo · Chorus · Outro
- idiom: big-hearted, cinematic ("lights across the city"), title hook repeated in the chorus.

## acoustic-ballad
- `v6` · vocal `female` · weirdness 25 · style_influence 70 · variety normal
- styles: `warm acoustic ballad, orchestral strings, acoustic guitar, glockenspiel, sincere female vocal, small-town nostalgia`
- exclude: `electronic, heavy drums, rap, distorted guitar`
- structure: Verse · Chorus · Verse · Chorus · [Bridge] lift · Final Chorus · Outro
- idiom: coming home, a window light left on; earnest, never ironic.

## piano-jazz
- `v6` · vocal unset · weirdness 35 · style_influence 70 · variety normal
- styles: `intimate jazz, solo piano, upright bass, brushed snare, smoky lounge, soft crooner vocal`
- exclude: `synthesizer, electric guitar, loud drums, pop production`
- structure: Intro (piano alone) · Verse · Chorus · [Instrumental Break] piano solo with walking bass · Verse · Chorus · Outro (ritardando)
- idiom: late evening, a fireplace, wry warmth.

## soft-rock-70s
- `v6` · vocal `male` · weirdness 35 · style_influence 65 · variety normal
- styles: `1970s soft rock, Fender Rhodes, warm electric guitar, stacked harmonies, mellow drums`
- exclude: `synthesizer pads, heavy distortion, rap, modern pop`
- structure: Intro guitar lick · Verse · Chorus · Verse · Chorus · [Instrumental Break] guitar solo · Chorus · Outro
- idiom: driving with the radio on, old friends, long roads.

## melodic-alt-rock
- `v6` · vocal `male` · weirdness 40 · style_influence 70 · variety normal
- styles: `melodic alternative rock, cinematic piano and strings, restrained electric guitars, soaring clean male vocal, anthemic`
- exclude: `heavy riffs, drop-tuned guitars, chugging breakdown, growling, screaming, blast beats`
- structure: [Piano Intro] · Verse · Pre-Chorus · Chorus · Verse · Pre-Chorus · Chorus · [Bridge] · Final Chorus · Outro
- idiom: storms, cold, light breaking through.
- lesson: heavy-metal styles (drop-tuned guitars, heavy riffs) come out guitar-heavy; the intensity should come from
  the soaring chorus, not the guitars.

## hip-hop-2020s
- `v6` · vocal unset · weirdness 40 · style_influence 70 · variety normal
- styles: `2020s hip-hop, boom bap drums, soulful sung hook, warm Rhodes, vinyl crackle`
- exclude: `explicit lyrics, profanity, aggressive trap, heavy autotune, country`
- structure: Intro · Verse 1 · Chorus · Verse 2 · Chorus · Verse 3 · Chorus · Outro (a posse cut: one MC per verse)
- idiom: warm and nostalgic; the neighbourhood, the people who raised you; each verse its own angle; no brand-name flexing.

## rock-opera
- `v6` · vocal unset (male/female duet in styles) · weirdness 45 · style_influence 70 · variety normal
- styles: `theatrical 1970s rock opera, bombastic power ballad, dramatic grand piano, wall of sound, male and female duet, gospel choir`
- exclude: `heavy metal, growling, rap, lo-fi, explicit lyrics`
- structure: [Piano Intro] · [Spoken Word] · Verse (male) · Pre-Chorus · Chorus · Verse (female) · Pre-Chorus · Chorus (duet) · [Bridge] call-and-response · [Instrumental Break] guitar solo · Final Chorus with choir and key change · Outro. Runs long (5–6 min) by design.
- idiom: over-the-top romantic vows, weather as melodrama, a long parenthetical title, a wink of humour.

## Brazilian styles (sung in Brazilian Portuguese; section tags stay English)
Common rules: put `Brazilian Portuguese vocals` in styles and `English lyrics` in exclude.

### bossa-nova
- `v6` · vocal `female` · weirdness 30 · style_influence 75 · variety normal
- styles: `bossa nova, Brazilian Portuguese vocals, nylon-string guitar, upright bass, soft brushed drums, gentle flute`
- exclude: `English lyrics, heavy drums, electric guitar, synthesizer, rap`
- idiom: the beach at dusk, heat, a slow afternoon; light humour and warmth.

### samba
- `v6` · vocal `male` · weirdness 35 · style_influence 75 · variety normal
- styles: `samba, Brazilian Portuguese vocals, pandeiro, cavaquinho, surdo, festive group chorus`
- exclude: `English lyrics, electronic, heavy rock guitar, rap, autotune`
- idiom: roda de samba, call-and-response chorus, "laiá" refrains, playful.

### sertanejo
- `v6` · vocal `male` · weirdness 30 · style_influence 75 · variety normal
- styles: `sertanejo, Brazilian Portuguese vocals, male duo harmony, viola caipira, acoustic guitar, accordion`
- exclude: `English lyrics, electronic, trap, heavy drums, rock guitar`
- idiom: farm gates, dirt roads, saudade, coming home; viola solo break.

### forro
- `v6` · vocal `male` · weirdness 30 · style_influence 75 · variety normal
- styles: `forró pé-de-serra, Brazilian Portuguese vocals, sanfona accordion, zabumba, triangle, festive`
- exclude: `English lyrics, electronic, rock guitar, rap, synthesizer`
- idiom: dancing till dawn, dust and heat, accordion solo break, "ai, ai" hooks.

### mpb
- `v6` · vocal `female` · weirdness 30 · style_influence 70 · variety normal
- styles: `MPB, Brazilian Portuguese vocals, intimate female vocal, nylon-string guitar, piano, soft strings`
- exclude: `English lyrics, heavy drums, electronic, rap, distorted guitar`
- idiom: reflective, poetic, everyday images; bridge lift.

### rock-br-80s
- `v6` · vocal `male` · weirdness 40 · style_influence 65 · variety normal
- styles: `1980s Brazilian rock, Brazilian Portuguese vocals, jangly electric guitars, new wave synths, punchy drums, catchy chorus`
- exclude: `English lyrics, heavy metal, rap, autotune, EDM`
- idiom: urban youth, crushes, cassette tapes, ironic but warm; guitar solo break.
