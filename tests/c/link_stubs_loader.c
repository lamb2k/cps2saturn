/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 lamb2k and cps2saturn contributors
 * Written for the kit. Link check only (tools/saturn_build_check.py): stand-ins for Sega's GFS functions and a one entry file list, so the loader image
 * links without the SDK libraries. Nothing here runs. */
#include "../../saturn/boot/sat_boot_main.h"
int GFS_Init(void) { return 0; }
int GFS_NameToId(void) { return 0; }
int GFS_Open(void) { return 0; }
int GFS_GetFileSize(void) { return 0; }
int GFS_SetTmode(void) { return 0; }
int GFS_Fread(void) { return 0; }
int GFS_Seek(void) { return 0; }
int GFS_Close(void) { return 0; }
int GFS_Reset(void) { return 0; }
const SatBootFile sat_boot_files[] = { { "RT.BIN", (void *)0x06014000u, 0x100u } };
const unsigned sat_boot_file_count = 1;
