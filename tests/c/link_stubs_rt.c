/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Written for the kit. Link check only (tools/saturn_build_check.py): the four functions a game gives sat_ctx.S. Nothing here runs. */
void sat_main(void) {}
void sat_slave_main(void) {}
void sat_vblank(void) {}
void sat_exception(unsigned vec, unsigned pc, unsigned pr) { (void)vec; (void)pc; (void)pr; }
