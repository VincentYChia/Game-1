# Geography port — working notes (2026-07-19, in progress)

Contracts: 12-agent workflow output (238k chars) at
`C:\Users\vipVi\AppData\Local\Temp\claude\c--Users-vipVi-PycharmProjects-Game-1\ec30dec9-d678-4643-82c8-b26148fd7ab7\tasks\w13x6frn1.output`
Line offsets: models 8, config 133, world_generator 190, nation 263,
region 371, political 488, village 569, ecosystem 670, names 745,
biome 851, setting_resolver 922, seam (world_system.py) at end.

## THE DECISION — Python determinism patch (do FIRST, commit separately)

CPython SET-ITERATION ORDER changes generated worlds (not just ordering):
- `nation_generator._deform_nations`: iterates `set(template.keys())` →
  patch to `template.keys()` (dict order, row-major). VALUE-IDENTICAL per
  chunk; only insertion order of result changes (downstream-visible).
- `nation_generator._validate_and_repair` Pass 1: `components.sort(key=len,
  reverse=True)` tie-breaks + `fragments.extend(comp)` iterate sets AND
  fragment reassignment mutates `result` sequentially → patch:
  `components.sort(key=lambda c: (-len(c), min(c)))` and
  `fragments.extend(sorted(comp))`.
- Pass 2 neighbor_counts built iterating `territories[nid]` (set) → patch
  `sorted(territories[nid])`. max() tie-break then deterministic.
- Check region/political/village contracts for equivalent sites; same
  treatment (sorted()).
Rationale: portable + CPython-version-robust; pre-playtest, no worlds to
preserve; cached world_map_seed_*.gz files regenerate. NOTE FOR USER:
same seed produces a DIFFERENT (but now stable) world after this patch.
Do NOT touch noise.py find_components/voronoi (already certified; sort at
call sites instead).

## FULL Python patch list (determinism; commit as its own Python commit)

1. noise.py find_components: `start = next(iter(remaining))` → `start =
   min(remaining)` (component list order becomes deterministic; contents
   unchanged; existing geo_noise fixture sorts → stays green; UPDATE C#
   GeoNoise.FindComponents to pick min too).
2. nation_generator._deform_nations: iterate `template.keys()` instead of
   `set(template.keys())` (values identical; row-major result order).
3. nation_generator._validate_and_repair Pass1: `fragments.extend(sorted(comp))`;
   Pass2 neighbor_counts loop: `for (cx, cy) in sorted(territories[nid])`.
4. region_generator._find_adjacent_region: `for (cx, cy) in sorted(region)`.
5. region_generator.generate_regions step 13: `for pos in sorted(region_chunks):
   region_map[pos] = rid` (region_map insertion order feeds biome-ID
   allocation downstream!).
6. political_generator._fix_contiguity: `for cx, cy in sorted(fragment)`.
7. political_generator._merge_tiny: `for cx, cy in sorted(result[i])`.
8. ecosystem_generator.generate_ecosystems: `for pos in
   chunk_type_map.keys():` (drop the `set(...)` wrapper) — eco-cell
   first-seen order (eco IDs + smoothing order = OUTPUT) becomes dict
   order, which after patch #5 is sorted region order.
9. name_generator: NO patch needed (pure hash; only quirk = locality
   naming uses FIRST-INSERTED nation via `for nid, n in nations.items():
   nation = n; break` — nations dict inserted 0..count-1 ascending by
   nation_generator, so first-inserted == nation 0; PORT the
   first-inserted semantics with insertion-ordered structure).
10. village_generator: NO PATCH NEEDED — sets are membership-only;
    candidate scan iterates chunk_data.items() whose insertion order is
    world_generator Phase-8 assembly (y outer, x inner, -half..half-1 —
    already deterministic). MT19937 via random.Random(seed+777777) →
    PythonRandom replays. PATCH LIST IS FINAL AT ITEMS 1-8.

## Village generator key facts (contract 569-669; full detail there)

- config Definitions.JSON/village-config.JSON v2.0 EXISTS (world_system
  path + fallback dead). placement: target 2500, min_distance 8 STRICT <
  Manhattan on anchors, dangers {1..6}, 7 excluded types. tiers order
  tiny,small,medium,large,fortress (filter: dict values, no "_" prefix).
  tier_selection_by_danger "1".."6" pools (all resolve → exactly ONE
  uniform draw per village). Live tier stats in contract line 659.
- place_villages(world_map, seed): rng=Random(seed+777777). scan
  chunk_data.items() insertion order: skip checked/excluded/invalid
  danger (anchor only!); validate min_size(2)² block existence+excluded
  (NOT danger); candidates append (cx,cy,dl); mark block checked.
  rng.shuffle(candidates). select ≤2500 with Manhattan < 8 reject.
  Per village i: _select_tier(rng, dl) [1 uniform]; npc_count=
  randint(min,max); per npc: nx=inner_x+randint(2,max(3,inner_w-2)),
  ny likewise, template=_select_npc_template(rng) [uniform(0,100)];
  name = prefixes[hash_2d_int(i,0,seed+888888,len)] + suffixes[
  hash_2d_int(i,1,seed+888888,len)] (HASH not MT); lid=next_lid+i
  (next_lid = max existing locality_id, default -1, +1); LocalityData
  (feature "village", adjacent=chunks dx-OUTER dy-INNER actual_size²);
  stamp gd.locality_id=lid (skip missing); villages dict rows (order:
  center_chunk, chunks, size, tier, tier_config REF, npc_positions,
  npc_templates, locality_id, name, nation=name or "Unknown").
  inner_x=cx*16+inset+3, inner_w=size*16-(inset+3)*2.
- _select_tier: pools [[name,weight]..] cumulative, roll=uniform(0,
  total), roll <= cumulative AND name in tiers → return; else fallback
  spawn_weight loop (2nd draw!). _select_npc_template: uniform(0,total),
  <= cumulative; empty templates → NO draw + hardcoded default.
- get_village_wall_tiles (NO rng): x1=cx*16+inset, x2=(cx+size)*16-
  inset-1; mid=(x1+x2)//2 PYTHON FLOOR (negative!); entrance:
  n==1 → |x-mid| <= ew//2; n>=2 → pos = x1+int(span*(e+1)/(n+1)) DOUBLE
  division then int-truncate; order: north row x1..x2, south row, west
  col y1+1..y2-1, east col. _distribute_entrances: [south,north,east,
  west] priority; >=4 → all + walls[i%4] extras; else first n.
- get_village_building_tiles(village, seed): rng=Random(seed+
  locality_id); count=randint(bmin,bmax); per building: bw,bh randint
  (CONSUMES even for (3,3)); 20 attempts: bx=x1+randint(1,max(1,
  area_w-bw-2)) etc; overlap = ANY rect tile in occupied (occupied gets
  only PERIMETER-minus-door tiles); door = (ty==by+bh-1 && tx==bx+bw//2)
  skipped; column-major tiles. Dropped building consumed all draws.
  x1=cx*16+inset+2, area=size*16-(inset+2)*2.

## Name generator key facts (contract 745-850; BANKS VERBATIM at output
   file lines 841-847 — transcribe from there when porting)

- All draws hash_2d_int(entity_id, y_channel, seed+offset, len(list)).
  Channel table: nation(y=0,+900000,10 names); region adj(y=1,+910000;
  STOIC 14 adjectives, others 12) + " " + identity display_name
  (capitalize: FOREST→"Forest"); province prefix(y=2,+920000,14) +
  suffix(y=3,+930000,14) NO space; district style(y=4,+940000,max 2):
  style 0 → "The " + adj(y=5,+950000) + " " + noun(y=6,+960000,10);
  style 1 → prefix(y=7,+970000) + suffix(y=8,+980000) no space;
  locality prefix(y=9,+990000) + " " + suffix(y=10,+991000 IRREGULAR).
- Locality feature tables (dungeon/npc/station/rare_resource) hardcoded
  5/6-entry lists (output lines 846); unknown feature → bank adjectives
  + district_nouns. IMPERIAL suffixes have "ium" at idx 0 AND 10 — keep.
- name_all: each tier sorted ascending by id; nation missing → skip
  (name unchanged). Mutates .name; returns nothing.
- _pick: empty → "Unknown"; else items[idx % len].

## Ecosystem generator key facts (contract 670-744)

- _chunk_to_ecosystem: cx>=0 → cx//gs; else (cx-gs+1)//gs PYTHON FLOOR →
  same double-shift quirk as biome cells (gs=3: cell -1 = {-1} ONLY,
  cell -2 = {-2,-3,-4}, -3 = {-5,-6,-7}). FloorDiv helper + verbatim.
- eco_cells: setdefault first-seen over (patched) chunk_type_map order.
- _compute_base_danger per cell: Chebyshev max(|ex|,|ey|) <= safe_radius
  (2) INCLUSIVE → TRANQUIL early (NO draw). weights = COPY of config
  dict (insertion order 1..6). counts over cell chunks: safe {lake,
  river,forest}, dangerous {deep_cave,cursed_marsh,crystal_cavern,
  barren_waste}; total = len or 1; safe_ratio > 0.5 STRICT → weights
  [1,2,3] *= (1+safe_ratio); dangerous_ratio > 0.3 STRICT → [4,5,6] *=
  (1+dr*2); .get(level,0) may APPEND missing keys at end. total_weight =
  sum(values()) in dict order; <= 0 → MODERATE. roll = hash_2d(ex, ey,
  seed+700000) (ONLY draw; can be exactly 1.0). cumulative loop over
  sorted keys ascending: cumulative += w[level]/total_weight (divide
  then add); roll < cumulative STRICT → level; fallback MODERATE.
- _smooth_gradient(eco_dangers, 2 (models constant, config field
  IGNORED), seed dead): result copy; up to 20 passes; per pass SNAPSHOT
  list(result.items()) pass-start values, but neighbor levels read LIVE;
  cell's own `level` local STALE within its 4-neighbor loop (last
  qualifying write wins); dirs (-1,0),(1,0),(0,-1),(0,1); diff >
  gradient_max STRICT; new = neighbor + gm if level > neighbor else
  neighbor - gm; clamp 1..6; break when pass makes no change.
- IDs: sequential 0.. in eco_cells order; danger = DangerLevel(clamp
  smoothed); ecosystem_metadata[eid] = EcosystemData(eid, danger,
  eco_x=eco_pos[0], eco_y=eco_pos[1]) — VERIFIED IN SOURCE (:241-246;
  the contract's algorithm prose omitted this — contracts are good but
  not infallible, adversarial verify phase is mandatory). per-chunk maps
  in cell-set order (order-insensitive fixture compare).

## Political generator key facts (contract 488-568)

- _subdivide_territories(territories, seed, seed_offset, min_area,
  max_area, amp, freq): parents sorted ascending; empty skip (no id/draw);
  child_seed = seed + parent_id*500 + offset (200000 prov, 300000 dist);
  count: min_count=max(2, chunks//max_area); max_count=max(min_count,
  chunks//min_area); if min>=max return min_count (NO draw); else
  offset=hash_2d_int(parent_id, 0, child_seed, range) → min+off.
  count<=1 branch (unreachable w/ defaults): one child copy.
  voronoi(territory, count, child_seed, amp, freq) → _fix_contiguity →
  _merge_tiny(min_area) → per non-empty child in list order: cid=next_id++
  (GLOBAL dense); child_map[pos]=cid; records (cid, parent, chunks).
- political _fix_contiguity: per index i asc; find_components; sort len
  desc STABLE; main=first (REBIND result[i]=main); fragments in order:
  scan sorted(fragment)-chunks × dirs [(-1,0),(1,0),(0,-1),(0,1)] ×
  enumerate(result) asc, j!=i, FIRST hit wins → result[j] |= fragment;
  not merged → result[i] |= fragment. |= MUTATES shared sets.
- _merge_tiny: while changed && max_iter(5)>0: while i<len: len<min
  STRICT && len>1: first-adjacent (sorted chunks × dirs × asc j) →
  result[best] |= result[i]; pop(i); no i++; else i++. (comment says
  most-border — CODE takes first; port code.)
- generate_provinces: territories from region_map setdefault;
  offset 200000; cfg province 600/2400/4.0/0.06; metadata ascending pid;
  nation_id = region.nation_id else -1; region.province_ids.append(pid);
  nation_metadata param UNUSED. generate_districts mirror: offset 300000,
  cfg district 200/800/2.0/0.08; district_metadata: region_id/nation_id
  from province else -1; province.district_ids.append(did).
After patching: re-run Game-1-modular tests (1219 green baseline) +
regenerate ALL goldens (dump_databases.py) — chunks.json geo cases may
change if region/biome outputs shift (they derive from ChunkTemplate
dispatch, not geography módule — verify). Existing world caches
(world_map_seed_*.gz) stale → delete on sight in save dirs (dev-only).

## Region generator key facts (contract 371-487)

- per nation SORTED ascending; region_seed = seed + nid*1000 + 100000.
- count: size_factor=min(1, chunks/60000); base=min_r+sf*range;
  variance=hash_2d(nid,0,rs+33333)*2-1; int(base+var*1.5) clamp [3,8].
- voronoi_subdivide(territory, count, rs, amp=8.0, freq=0.04): seeds via
  _place_spread_seeds (sorted territory list; first idx
  hash_2d_int(0,0,rs,N); sample_size=min(N,max(100,N//20)); candidates
  hash_2d_int(i,j,rs+999,N); farthest-point strict >, earliest j wins;
  DEAD precompute loop j 0..sample_size-1 EXISTS but unused — skip).
  assignment: noise=value_noise_2d(cx*.04,cy*.04,rs+77777)*64.0; dist=
  dx²+dy²+(i%2==0?+:-)offset; strict < lowest idx wins. drop empties.
- _fix_contiguity: per index; find_components; sort len desc STABLE;
  main=first; fragments merged via _find_adjacent_region (edge counts,
  4-neighbors (-1,0),(1,0),(0,-1),(0,1), enumerate ascending, first-max
  tie); target>=0 → |= else back to main. mutates shared sets.
- _validate_region_areas: min_area=int(chunks*0.10); while changed &&
  iter<10: inner while i<len: len<min STRICT && len>1: target=|= then
  pop(i), no i++ on merge. order preserved.
- ids: global dense counter, per validated list position; identity =
  _ALL_IDENTITIES[hash_2d_int(i, nid, rs+44444, 10)] — i = LIST INDEX
  within nation. bounds=min/max. nation_data.region_ids.append(rid).

## Porting state

DONE: GeoModels.cs (models.py — enums as strings, tables, tier data,
WorldMap; no save/load yet). Committed? NO — commit with the rest.
TODO order: GeoConfig.cs (defaults only + same JSON search →
world_system/config/geography-config.json then Definitions.JSON; neither
exists → pure defaults; world 512, nation count 5/min_area 30000/
corridor 12/amp 24.0/freq 0.02/oct 4/scale_var 0.12; region 3-8 per
nation, 10-45% area, amp 8 freq .04; province 600-2400 amp 4 freq .06;
district 200-800 amp 2 freq .08; biome 400-800 w .70/.30; eco group 3
gradient 2 weights {1:.15,2:.25,3:.25,4:.20,5:.10,6:.05} safe_radius 2)
→ NationGenerator.cs → RegionGenerator.cs → PoliticalGenerator.cs →
GeoBiomeGenerator.cs → EcosystemGenerator.cs → NameGenerator.cs →
VillageGenerator.cs → WorldGeneratorPipeline.cs → SettingResolver.cs.

## Nation generator — key algorithm facts (contract lines 263-369)

- default template: y outer, x outer -half..half-1; angle=atan2(y,x)+pi;
  nid=int(angle/step)%count. FloorDiv OK (positive).
- deform: scale hash_2d(nid,0,seed+7777)*2-1 → 1+raw*0.12; per chunk
  fractal(cx*f, cy*f, seed+11111, oct) & fractal(cx*f+500, cy*f+500,
  seed+22222); lookup=int(round()) BANKER'S; clamp -half..half-1;
  displaced wins iff scale_displaced > scale_original STRICT.
- shuffle ids: Fisher-Yates i=n-1..1, j=hash_2d_int(i,0,seed+55555,i+1);
  map old→ids[old]; .get(nid,nid) passthrough.
- repair: territories setdefault insertion order; Pass1 snapshot ONCE;
  find_components (contents deterministic); fragments reassigned via
  _find_nearest_nation(ring radius 1..49, dx outer dy inner ascending,
  perimeter only, first hit; fallback 0) — result mutated mid-loop.
  Pass2 FRESH snapshot; len < min_area STRICT; neighbor_counts via
  4-neighbors [(-1,0),(1,0),(0,-1),(0,1)]; merge_into = FIRST max in
  insertion order; territories[nid] emptied not deleted.
- metadata: flavor Fisher-Yates seed+88888; flavor_idx=order[nid]%5;
  color=_DEFAULT_COLORS[flavor_idx%12] (only 0-4 reachable);
  name="" (named later); chunk_count=len(territories.get(nid,set())).
- _DEFAULT_COLORS (12): (70,110,170),(80,155,80),(190,155,60),
  (155,95,70),(130,100,175),(170,80,80),(80,155,150),(160,140,90),
  (100,80,140),(140,160,80),(180,120,100),(90,130,120).
- hash_2d/value_noise/fractal already in C# GeoNoise (certified).
  find_components also in GeoNoise. hash_2d can return EXACTLY 1.0;
  hash_2d_int trailing % absorbs it.

## Biome generator — key facts (contract lines 851-921; full detail there)

- Step1: chunk_type per chunk = pure fn: value_noise_2d(cx*.03, cy*.03,
  seed+500000) → biome_val=(v+1)*0.5; pool = primary if biome_val <
  cfg.biome.primary_weight (STRICT) else secondary (fallback primary if
  empty); type_idx = int(hash_2d(cx,cy,seed+600000)*len(pool)) %
  len(pool); iterate region_map in INSERTION order.
- Step2 biome cells: 16-cell coarse grid with QUIRKY neg floor-div:
  bx = cx>=0 ? cx//16 : (cx-15)//16 with PYTHON FLOOR division —
  double-shifts negatives: bx=-1 covers ONLY cx=-1; bx=-2 covers
  [-17,-2]; bx=-k covers [15-16k,30-16k] k>=2. C# needs FloorDiv helper
  + verbatim formula. First-encounter cell → new biome id 0,1,2...;
  BiomeData dominant=FIRST chunk's type; bounds=(cx,cy,cx,cy) never
  updated; chunk_count counts all incl. first. REFERENCE type.

## Setting resolver (lines 922-961): priority village(locality_id>=0,
feature_type=="village") → underground{cave,deep_cave,crystal_cavern,
flooded_cave} → ruins{overgrown_ruins} → waterside{lake,river,wetland}
→ wasteland{barren_waste} → thicket{dense_thicket} → "wilderness".

## World generator orchestration (read directly, in context earlier):
phases nations→regions→provinces→districts→biomes→ecosystems→names
(localities={} at naming!)→assemble WorldMap (chunk grid y outer x inner
-half..half-1, .get defaults -1/MODERATE)→villages (place_villages(wm,
seed), try/except → []). Villages held on gen._villages (informal).

## Seam (world_system.py): cache world_map_seed_{seed}.gz (skip in C# —
regen deterministic); WorldGenerator(seed, GeographicConfig.load());
villages rebuilt from localities + random.Random(seed+777777);
Chunk(cx,cy,biome_generator=legacy,geographic_data=geo) — chunk derives
its own chunk_type via geo dispatch (ChunkGenerator.Generate geoChunkType
param maps: pass geo.chunk_type string + geo.danger_level int).
Dungeons still legacy biome_generator rolls. in_bounds via map.

## Oracle plan (after Python patch + port)

Dump `geography.json`: for seeds [777, 20260719]: run REAL WorldGenerator
(patched) → dump: nations/regions/provinces/districts/biomes(sample)/
ecosystems metadata FULLY; sha256 canon over sorted chunk_data rows
(cx,cy,nation,region,province,district,chunk_type,biome,eco,danger);
dense 24x24 window at origin + 3 offset windows raw; villages (id, name,
chunk, feature, adjacent). names via name_all — full name lists dumped.
C# test regenerates both seeds and compares. NOTE world 512x512: python
gen ~seconds, C# similar. If too slow for fixtures, add config override
world_size 128 AND ALSO run one full-512 sha canon.

## Remaining contract sections to read before porting each file
region 371-487, political 488-568, village 569-669, ecosystem 670-744,
names 745-850. READ EACH JUST BEFORE PORTING THAT FILE.

## After port: adversarial verify workflow (per-file source-vs-port),
then wire WorldBootstrap geographic mode (WorldMap → per-chunk geo →
ChunkGenerator geoChunkType/geoDangerLevel + village walls later),
visual run, commit, plan+memory.
