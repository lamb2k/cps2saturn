-- Video check capture, run by tools/video_check.py. A golden run (golden.lua, unchanged) plus, at chosen frames,
-- MAME's picture, its palette, GFX RAM and the CPS-A / CPS-B registers it drew that picture with. Optionally some
-- layers are switched off by clearing bits in every write the game makes to CPS-B layer control or CPS-A video
-- control; that changes only what MAME draws, the game reads neither back. Output stays local.
--   CPS2SAT_GOLDEN_LUA   path of golden.lua; it runs first with its own CPS2SAT_* settings
--   CPS2SAT_LAYER_CTRL   optional "address,mask": layer control register and the enable bits to clear
--   CPS2SAT_VIDEO_CTRL   optional "address,mask": video control register and the bits to clear
--   CPS2SAT_FRAMES       "f,f,..." frames to capture (each before the golden's last frame)
--   CPS2SAT_FRAMES_DIR   output folder, per frame fNNNNN.*:
--                          rgb   screen:pixels() at the end of frame NNNNN, host byte order
--                          pal   pens 0-0xbff at the same moment (pixels() converts with them), 0xAARRGGBB BE
--                          gfx   GFX RAM, CPS2SAT_GFX_RAM "base,size" read from the program space
--                          regs  CPS-A then CPS-B registers, 32 big-endian words each, from MAME's own copies
--                        and frames.txt ("byteorder le|be", then "frame irq w h", irq at the end of the frame).
--                        gfx and regs are read at the end of frame NNNNN - 1: measured on dino, the picture
--                        pixels() returns at the end of a frame was drawn from the state at the end of the frame
--                        before (state read with the picture matched no frame where the scroll moved; state from
--                        the frame before matched every one)
--   CPS2SAT_REG_SHARES   "cps_a_tag,cps_b_tag": MAME's register shares (default ":cps_a_regs,:cps_b_regs"). The
--                        registers are write-only on the bus, so the check reads MAME's copies; the tags are
--                        names in MAME's CPS driver, not part of the board
--   CPS2SAT_GFX_OUT      optional: MAME's graphics region written here before the run
--   CPS2SAT_GFX_REGION   region tag (default ":gfx")
local function need(name) local v = os.getenv(name); assert(v and v ~= "", name .. " not set"); return v end
local function num(s) return math.tointeger(tonumber(s)) end
local function pair(s) local a, b = s:match("^%s*([^,]+),%s*([^,]+)%s*$"); return a, b end

dofile(need("CPS2SAT_GOLDEN_LUA"))

local machine = manager.machine
local prog = machine.devices[":maincpu"].spaces["program"]
local screen = assert(machine.screens[":screen"], "no :screen")
local palette = assert(screen.palette, "the screen has no palette")
local dir = need("CPS2SAT_FRAMES_DIR")
local ram_base, ram_size = pair(need("CPS2SAT_GFX_RAM"))
ram_base, ram_size = num(ram_base), num(ram_size)
local tag_a, tag_b = pair(os.getenv("CPS2SAT_REG_SHARES") or ":cps_a_regs,:cps_b_regs")
local share_a = assert(machine.memory.shares[tag_a], "no share " .. tag_a)
local share_b = assert(machine.memory.shares[tag_b], "no share " .. tag_b)

local gfx_out = os.getenv("CPS2SAT_GFX_OUT")
if gfx_out and gfx_out ~= "" then
    local tag = os.getenv("CPS2SAT_GFX_REGION") or ":gfx"
    local region = assert(machine.memory.regions[tag], "no region " .. tag)
    local f = assert(io.open(gfx_out, "wb"))
    local bytes = {}
    for a = 0, region.size - 1 do
        bytes[#bytes + 1] = string.char(region:read_u8(a))
        if #bytes == 65536 then f:write(table.concat(bytes)); bytes = {} end
    end
    f:write(table.concat(bytes))
    f:close()
end

local function clear_tap(var, name)
    local spec = os.getenv(var)
    if not spec or spec == "" then return nil end
    local addr, mask = pair(spec)
    addr, mask = num(addr), num(mask)
    return prog:install_write_tap(addr, addr + 1, name, function(off, data, m) return data & ~mask end)
end
cps2sat_layer_tap = clear_tap("CPS2SAT_LAYER_CTRL", "cps2sat_layers")
cps2sat_video_tap = clear_tap("CPS2SAT_VIDEO_CTRL", "cps2sat_video")

local want, want_state = {}, {}
for n in need("CPS2SAT_FRAMES"):gmatch("%d+") do want[num(n)] = true; want_state[num(n) - 1] = num(n) end
local log = assert(io.open(dir .. "/frames.txt", "w"))
log:write(string.pack("=I4", 1):byte(1) == 1 and "byteorder le\n" or "byteorder be\n")

local function save(path, data) local f = assert(io.open(path, "wb")); f:write(data); f:close() end

local frame = 0
cps2sat_video_frames = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    if want_state[frame] then
        local name = string.format("%s/f%05d", dir, want_state[frame])
        local t = {}
        for a = 0, ram_size - 2, 2 do t[#t + 1] = string.pack(">I2", prog:read_u16(ram_base + a)) end
        save(name .. ".gfx", table.concat(t))
        t = {}
        for i = 0, 31 do t[#t + 1] = string.pack(">I2", share_a:read_u16(i * 2)) end
        for i = 0, 31 do t[#t + 1] = string.pack(">I2", share_b:read_u16(i * 2)) end
        save(name .. ".regs", table.concat(t))
    end
    if want[frame] then
        local name = string.format("%s/f%05d", dir, frame)
        local px, w, h = screen:pixels()
        save(name .. ".rgb", px)
        local t = {}
        for i = 0, 0xbff do t[#t + 1] = string.pack(">I4", palette:pen_color(i)) end
        save(name .. ".pal", table.concat(t))
        log:write(string.format("%d %d %d %d\n", frame, cps2sat_golden_irq(), w, h))
        log:flush()
    end
end)
