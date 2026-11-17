# Tools not ported from AvP Saturn

Source: the AvP Saturn repo, branch lane/duel, `tools/` and `saturn/`. Each line gives the reason it stayed behind.
Methods from many of them are written up in the skills and the playbook instead.

## Ported

| AvP file | Here |
| --- | --- |
| `tools/verify_iso_file.py` | tools/iso_verify.py (adds --list) |
| `tools/build_loader_ip.py` | tools/ip_bin.py (load address and offsets as arguments or config) |
| `tools/satgfx_pack.py` | tools/cps_tiles.py (region offsets from config) |
| `tools/sat_tile_funnel.py` | tools/cps_objects.py funnel (geometry from config) |
| `tools/learn_dis68k.py` | tools/dis68k.py (image path as an argument) |
| `tools/mame_golden.lua` | tools/mame/golden.lua (all addresses and route bits from config) |
| `tools/mame_golden_run.py` | tools/mame_golden_run.py (paths and set from config, --dry-run) |
| `tools/golden_delta_show.py` | tools/golden_reader.py (full and delta, plus diff) |
| `tools/mame_dump_code_spaces.lua` | tools/mame/dump_code_spaces.lua |
| `tools/mame_dump_rom_window.lua` | tools/mame/dump_rom_window.lua |
| `tools/mame_list_inputs.lua` | tools/mame/list_inputs.lua |
| `saturn/audio/compare_raw.py` | tools/audio_compare.py (WAV or raw capture, function form) |
| `saturn/package/build_package.py` | tools/make_cue.py (cue and hashes; the AvP build call stays behind) |
| `tools/capture_frontend_cram.py` | tools/yaba_mcp.py takes its MCP client only; the CRAM capture stays behind |
| `saturn/rt/play_yaba.py` | tools/yaba_mcp.py takes the own-window pad and port-owner check; the script runner stays behind |
| tools/sector_store.py (commit fb69ab5, AvP default line) | `tools/sector_store.py` |
| saturn/rt/build.py round_files(): shared-page and ranked-drop rules | `tools/page_plan.py` |

## Moved into the platform tree

The game-neutral parts of the AvP Saturn runtime went into `saturn/` on 2026-11-16 (see `saturn/README.md`). Entries below for those files now say which part moved.

| AvP file (v0.1.0-beta) | Here |
| --- | --- |
| `saturn/rt/boot.c` boot display | `saturn/boot/sat_diag.c` |
| `saturn/rt/boot.c` clock change, cart bring-up, entry | `saturn/boot/sat_boot.c`, `sat_boot_main.c`, `crt0.S` |
| `saturn/rt/boot.c` GFS loads, `SECTOR_STORE` reader | `saturn/cd/sat_gfs_io.c`, `sat_store.c` |
| `saturn/rt/lzdec.h` | `saturn/cd/sat_lzdec.h` |
| `saturn/rt/boot.ld`, `build.py` link script | `saturn/ld/boot.ld.in`, `rt.ld.in` |
| `saturn/rt/ctx.s` | `saturn/rt/sat_ctx.S` |
| `saturn/rt/kernel.c` slave start and hand-off | `saturn/rt/sat_sync.c` |
| `saturn/rt/pad.c` | `saturn/rt/sat_pad.c` |
| `saturn/rt/lift_target.h` OP8/OP16/OP32 | `saturn/rt/sat_opx.c` |
| `saturn/gfx/sat_gfx.c` cache | `saturn/gfx/sat_tilecache.c` |
| `saturn/gfx/sat_gfx.c` VDP1 plot protocol | `saturn/gfx/sat_vdp1.c` |
| `saturn/gfx/sat_gfx.c` VDP2 latch and init | `saturn/gfx/sat_vdp2.c`, `sat_vdp2_cycles.h` |
| `saturn/gfx/sat_gfx.c` snap_layer | `saturn/gfx/sat_layer.c` |
| `saturn/audio/sat_audio.c` | `saturn/audio/sat_scsp.c`, `sat_cdda.c` |
| `tools/perf/fn_heat.py` | `tools/fn_heat.py` |
| `saturn/rt/build.py` plan_functions | `tools/place_plan.py` |

## Not ported

- `saturn/audio/build_pack.py`: AvP audio build or standalone test, bound to its clip set.
- `saturn/audio/render_mame.lua`: AvP audio build or standalone test, bound to its clip set.
- `saturn/audio/sat_audio.c`: Generic core (SCSP slot play, SMPC sound start, CD audio chain, fades) moved to `saturn/audio/sat_scsp.c` and `sat_cdda.c`; the Z80 mailbox policy and pan sweeps stay in AvP.
- `saturn/audio/sat_audio.h`: Interface of the AvP driver; the generic interfaces are `saturn/audio/sat_scsp.h` and `sat_cdda.h`.
- `saturn/audio/sound_table.py`: Reads the AvP Z80 driver table at fixed offsets; method in skills/saturn-audio.
- `saturn/audio/standalone.ld`: AvP audio build or standalone test, bound to its clip set.
- `saturn/audio/standalone.py`: AvP audio build or standalone test, bound to its clip set.
- `saturn/audio/standalone_main.c`: AvP audio build or standalone test, bound to its clip set.
- `saturn/audio/yaba_wav_dump.patch`: Patch against GPL-2.0 code (Yabasanshiro) or the AvP engine setup; kept out of this MIT kit (NOTICE.md).
- `saturn/game/game_bind.c`: AvP lifted-game bindings and overrides.
- `saturn/game/game_hot.c`: AvP lifted-game bindings and overrides.
- `saturn/game/game_hot.h`: AvP lifted-game bindings and overrides.
- `saturn/game/overrides.txt`: AvP lifted-game bindings and overrides.
- `saturn/gfx/host_test.c`: AvP Saturn graphics adapter, bound to its pack layout and VDP setup.
- `saturn/gfx/sat_gfx.c`: Generic parts (tile cache, VDP1 plot protocol, VDP2 latch and layout, layer memo) moved to `saturn/gfx/`; the pack format, layer drawing, HUD and home menu stay in AvP.
- `saturn/gfx/sat_gfx.h`: AvP's configuration of the drawing library; the generic headers are in `saturn/gfx/`.
- `saturn/gfx/standalone.ld`: AvP Saturn graphics adapter, bound to its pack layout and VDP setup.
- `saturn/gfx/standalone_main.c`: AvP Saturn graphics adapter, bound to its pack layout and VDP setup.
- `saturn/package/HARDWARE_TEST.md`: AvP hardware test sheet or round list.
- `saturn/package/HARDWARE_TEST_ROUNDS.txt`: AvP hardware test sheet or round list.
- `saturn/rt/boot.c`: Boot display, clock change, cart bring-up, GFS loads and the sector store reader moved to `saturn/boot/` and `saturn/cd/`; the AvP save record, reveal and cycle diagnostic stay.
- `saturn/rt/boot.ld`: Template form in `saturn/ld/boot.ld.in`.
- `saturn/rt/build.py`: AvP Saturn runtime (kernel, boot, home and duel code) or its build.
- `saturn/rt/ctx.s`: Moved to `saturn/rt/sat_ctx.S` (stack tops from C variables, optional r14).
- `saturn/rt/duel.inc`: AvP Saturn runtime (kernel, boot, home and duel code) or its build.
- `saturn/rt/duel_smash.inc`: AvP Saturn runtime (kernel, boot, home and duel code) or its build.
- `saturn/rt/home.c`: AvP Saturn runtime (kernel, boot, home and duel code) or its build.
- `saturn/rt/home_cold.c`: AvP Saturn runtime (kernel, boot, home and duel code) or its build.
- `saturn/rt/kernel.c`: The slave start, hand-off and vblank prologue moved to `saturn/rt/sat_sync.c`; the lifted-game scheduler and traps stay in AvP.
- `saturn/rt/lift_target.h`: AvP Saturn runtime (kernel, boot, home and duel code) or its build.
- `saturn/rt/pad.c`: The SMPC sequence moved to `saturn/rt/sat_pad.c`; the AvP input latch mapping and test scripts stay.
- `saturn/rt/play_duel_hits.py`: AvP bot or run script: reads AvP RAM fields and symbols. Pattern kept in tools/yaba_mcp.py.
- `saturn/rt/play_full_bot.py`: AvP bot or run script: reads AvP RAM fields and symbols. Pattern kept in tools/yaba_mcp.py.
- `saturn/rt/play_game_bot.py`: AvP bot or run script: reads AvP RAM fields and symbols. Pattern kept in tools/yaba_mcp.py.
- `saturn/rt/play_home_stage.py`: AvP bot or run script: reads AvP RAM fields and symbols. Pattern kept in tools/yaba_mcp.py.
- `saturn/rt/play_round1_bot.py`: AvP bot or run script: reads AvP RAM fields and symbols. Pattern kept in tools/yaba_mcp.py.
- `saturn/rt/play_smash.py`: AvP bot or run script: reads AvP RAM fields and symbols. Pattern kept in tools/yaba_mcp.py.
- `saturn/rt/present.c`: AvP Saturn runtime (kernel, boot, home and duel code) or its build.
- `saturn/rt/run_yaba.py`: AvP bot or run script: reads AvP RAM fields and symbols. Pattern kept in tools/yaba_mcp.py.
- `saturn/rt/sat_rt.h`: AvP Saturn runtime (kernel, boot, home and duel code) or its build.
- `saturn/rt/yaba_pad_set.patch`: Patch against GPL-2.0 code (Yabasanshiro) or the AvP engine setup; kept out of this MIT kit (NOTICE.md).
- `saturn/rt/yaba_soft_core.patch`: Patch against GPL-2.0 code (Yabasanshiro) or the AvP engine setup; kept out of this MIT kit (NOTICE.md).
- `tools/New-ReviewBundle.ps1`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_avsp_palette_coverage.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_avsp_stage_scroll.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_avsp_table_set_writer.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_boss_actions.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_boss_ko.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_enemy_actions.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_enemy_contact.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_frontend.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_frontend_geometry.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_frontend_interaction.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_frontend_rom_composition.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_frontend_segments.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_hitbox_brackets.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_hitbox_geometry.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle04_controls.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle05_ai.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle06_encounter.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle07_player_action.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle08_navigation.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle09_alien_state.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle10_counterfactuals.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle10_round1.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle10_round1_census_extension.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle10_round1_p2_closure.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_actor_scheduler.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_global_audio_handlers.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_global_audio_load_release.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_global_audio_trigger_owners.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_global_load_release_boundaries.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_player_air_authority.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_player_audio.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_player_authority.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_player_hitko_continue.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_player_route_ownership.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_player_weapon.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_round1_auxiliary.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_round1_boss.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_round1_encounters.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_round1_enemies.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_round1_handoff.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_round1_navigation.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_round1_rng.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_oracle11_round1_writer_reconciliation.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_player_actions.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_player_damage.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_round1_debug_overlays.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_source_bound_combat_presentation.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_stalker_actions.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_street_alien_object_emission.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/analyze_watchpoint_log.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/avsp_vdp1_model.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_boss_tile_workset.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_round1_content_archive.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec01_encounter_contract.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_boss_audio_owner_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_class00_type12.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_class01_type12.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_class06_type12.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_class07_type20.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_class10_type24.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_class3d_type24.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_class49_type24.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_class4b_type24.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_class4e_type24.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_encounter_audio_owner_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_enemy_audio_owner_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_presentation_audio_owner_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_projectile_audio_owner_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_round1_contract.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_route_83d4_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_route_8418_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_route_8546_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_route_8bb2_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_route_90f2_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_route_audio_owner_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_route_c200_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/build_spec02_route_c886_program.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/capture_reimplement13_coffee_shop_scene.py`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/capture_street_readback.py`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/census_full_route.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/check_layout_anchor.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/classify_route_rowscroll.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/decode_avsp_animation_scripts.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/decode_avsp_collision.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/decode_avsp_object_stream.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/decode_avsp_table_set.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/diag_seed_key.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/ending_pkgrun.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/extract_avsp_actor_classes.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/extract_avsp_dispatchers.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/extract_avsp_table_set_states.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/extract_avspu_stage1.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/extract_qsound_event.py`: Little AvP coupling, but built on the old pipeline's capture CSV and manifest format. Candidate for a later port with a documented capture format.
- `tools/gate1_measure.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gate_avsp_table_set.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gate_outmap.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_action_seeds.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_anim_records.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_emit_windows.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_frontend.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_gfx_tiles.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_residency_budget.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_scene_manifest.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_street_planes.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_table_set_classes.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_table_set_evidence.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_avsp_table_set_source.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_boss_rom_data.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/gen_spec02_round1_entry.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/generate_assets.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/generate_boss_anim_script.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/generate_round1_authority_matrix.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/generate_stage1_route.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/golden_census.lua`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/golden_census.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/golden_roots.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/home_font.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_actor_lineage.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_actor_mutate.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_actor_probe_alloc.lua`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_actor_survey.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_audio_alldis.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_audio_helpers.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_audio_map.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_audio_owners.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_audio_probe.lua`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_audio_ring.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_audio_z80.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_cfg68k.py`: Lifter and code map bound to the AvP image and roots; method in skills/sh2-game-logic.
- `tools/learn_ledger.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_probe_cover.lua`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_probe_entries.lua`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_probe_exec.lua`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_probe_hold.lua`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_probe_irqsp.lua`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_probe_regs.lua`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_probe_watch.lua`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_run_probe.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_task_census.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_task_resume.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_tick_rule.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_tick_runs.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/learn_unit.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/lift68k.py`: Lifter and code map bound to the AvP image and roots; method in skills/sh2-game-logic.
- `tools/lift_audit.py`: Lifter and code map bound to the AvP image and roots; method in skills/sh2-game-logic.
- `tools/lift_audit_main.c`: Lifter and code map bound to the AvP image and roots; method in skills/sh2-game-logic.
- `tools/lift_host_main.c`: Lifter and code map bound to the AvP image and roots; method in skills/sh2-game-logic.
- `tools/lift_profile.py`: Lifter and code map bound to the AvP image and roots; method in skills/sh2-game-logic.
- `tools/lift_runner/add_missing.py`: AvP host runner and lifter glue, bound to its roots, kernel and RAM map.
- `tools/lift_runner/apply_overrides.py`: AvP host runner and lifter glue, bound to its roots, kernel and RAM map.
- `tools/lift_runner/build.py`: AvP host runner and lifter glue, bound to its roots, kernel and RAM map.
- `tools/lift_runner/host_kernel.c`: AvP host runner and lifter glue, bound to its roots, kernel and RAM map.
- `tools/lift_runner/iterate.py`: AvP host runner and lifter glue, bound to its roots, kernel and RAM map.
- `tools/lift_runner/iterate_lane.py`: AvP host runner and lifter glue, bound to its roots, kernel and RAM map.
- `tools/lift_runner/mask.txt`: AvP host runner and lifter glue, bound to its roots, kernel and RAM map.
- `tools/lift_runner/oplog.sh`: AvP host runner and lifter glue, bound to its roots, kernel and RAM map.
- `tools/lift_runner/run.sh`: AvP host runner and lifter glue, bound to its roots, kernel and RAM map.
- `tools/lift_test.py`: Lifter and code map bound to the AvP image and roots; method in skills/sh2-game-logic.
- `tools/make_merged.py`: Lifter and code map bound to the AvP image and roots; method in skills/sh2-game-logic.
- `tools/make_route.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/mame_capture_boss_actions.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_boss_ko.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_collision_probe.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_enemy_actions.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_enemy_contact.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_frontend.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_frontend_interaction.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_frontend_rom.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_frontend_wipe.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_full_route.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle04_controls.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle05_ai.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle06_encounter.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle07_player_action.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle08_enemy_bounds.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle08_navigation.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle09_alien_state.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle10_round1.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_aux_suppression.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_coffee_exit_player.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_first_segment_progression.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_global_audio_mutation.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_global_audio_transport.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_global_load_release.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_player_audio.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_player_contextual_melee.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_player_hitko_continue.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_player_locomotion.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_player_route_events.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_player_route_ownership.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_player_weapon.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_round1_auxiliary.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_round1_boss.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_round1_enemies.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_round1_entry_correction.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_round1_handoff.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_round1_navigation.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_oracle11_round1_route.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_player2_hud.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_player_action.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_reimplement13_coffee_shop_pickup.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_reimplement13_navigation_fields.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_round1_debug_overlays.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_stage1.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_stage1_audio.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_stage1_boss.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_stage1_full.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_stalker_actions.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_capture_vertical_slice.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_configure_debug_switches.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_dump_stage1_state.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_map_frontend_timeline.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_probe_actor_struct.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_probe_debug_overlays.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_route_bot.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_route_bot_run.py`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_save_replay_state.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_trace_stage1_qsound.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_watch_actor_writers.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_watch_actor_writers.txt`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/mame_watch_street_alien_object_emission.lua`: AvP capture for one scene, actor or oracle: fixed addresses and frames.
- `tools/map_avsp_hit_ko_writer_set.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/map_avsp_translation_boundary.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/measure_avsp_sprite_demand.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/measure_round1_audio_map.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/measure_round1_qsound_samples.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/measure_round1_shrink.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/measure_saturn_frame_cost.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/probe_boot_freeze_mcp.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/ref_interp.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/render_preview.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/roots.txt`: Lifter and code map bound to the AvP image and roots; method in skills/sh2-game-logic.
- `tools/rounds_census.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_config.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_from_golden2.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_hostcheck.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_hostfinal.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_pack.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_rank.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_union.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_variants.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_variants_report.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_walk.lua`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/rounds_walk.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/routes/co2p_to_1e.txt`: AvP input route: recorded play of one game.
- `tools/routes/full_c1.txt`: AvP input route: recorded play of one game.
- `tools/routes/full_c2.txt`: AvP input route: recorded play of one game.
- `tools/routes/full_c3.txt`: AvP input route: recorded play of one game.
- `tools/routes/pw_full_game.txt`: AvP input route: recorded play of one game.
- `tools/routes/r1_pw_ko_boss.txt`: AvP input route: recorded play of one game.
- `tools/run_interactive_emulator.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/sat_heat.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/sat_pc_rank.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satgfx_mame_scene.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satgfx_ref.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satgfx_scene.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satgfx_scene_probe.lua`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satint_census.lua`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satint_census.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satint_fit.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satint_merge.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satint_oreads.lua`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satint_pack.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satint_reads.lua`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/satint_scan_tables.py`: AvP round, pack or integration step tied to its census and pack layout; rules in tools/page_plan.py.
- `tools/select_rp4_interval.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/table_gap_roots.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/test_avsp_collision.py`: Test of an AvP-only analyzer or contract.
- `tools/test_boss_rom_data.py`: Test of an AvP-only analyzer or contract.
- `tools/trace_boss_play_sequence.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/trim_stage1_audio.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_avsp_actor_classes.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_avsp_anchor_anim_replay.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_avsp_collision.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_avsp_object_corpus.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_avsp_substate_model.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_avsp_table_set_states.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_avsp_vertical_slice_oracle.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_boss_rom_poses.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_confirm_shutter.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_fixture_separation.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_frontend_cram.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_frontend_objects.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_pose_gate.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_position_gate.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_residency_budget.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_route_census.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_rowscroll_classification.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_scene_manifest.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.
- `tools/verify_street_planes.py`: AvP analysis, generator or check, fixed to its ROM layout, actors, stages or evidence.

## Clips and video

Ported from the private AvP Saturn skills (game-neutral parts only): `tools/clip/shot_script.py` (route and take
language, with every game constant moved to the config's `capture:` section), `tools/clip/align_audio.py` (the clock
fit and median-latency method, with no fixed recorder or disc paths), `tools/video/assemble.py` and
`tools/video/mix.py`. The AvP menu routes, the process-loopback recorder and the disc layout stay behind.

- **Exact game sound from a sound-chip dump (method only).** The real-time alignment is only as good as the audio
  pipeline's jitter. The exact alternative needs an emulator patched to write the sound chip's own output (raw 44.1 kHz
  16 bit stereo) in emulated time, whatever the host does. Replay the stepped take from the same saved state with the same
  keys on a disc whose CD audio tracks are zero-filled (so only game sound effects and voices remain). Stepping is
  deterministic, so the replay's pictures equal the original take's (check by hashing them) and the dump position at the
  end of every stepped chunk is known. Fit samples against picture number (line fit; the residual is the writer's
  jitter) to get the dump sample at the start of each picture, cut from picture 0, and measure event onsets as in
  `align_audio.py`. It is not ported because the dump is a patch against GPL-2.0 emulator code (see NOTICE.md).
