-- Sprite-layer check capture, run by tools/sprite_check.py. A golden run (golden.lua, unchanged) plus, at chosen
-- frames, the screen with the scroll layers switched off, so MAME draws sprites only, and MAME's sprite palette.
-- The scroll layers go off by clearing their enable bits in every write the game makes to the CPS-B layer control
-- register. That changes only what MAME draws; the game reads nothing back from it. Output stays local.
--   CPS2SAT_GOLDEN_LUA   path of golden.lua; it runs first with its own CPS2SAT_* settings
--   CPS2SAT_LAYER_CTRL   "address,mask": the layer control register and the enable bits to clear
--   CPS2SAT_FRAMES       "f,f,..." frames to capture (each before the golden's last frame)
--   CPS2SAT_FRAMES_DIR   output folder: fNNNNN.rgb (screen:pixels(), host byte order), fNNNNN.pal (pens 0-0x1ff
--                        then 0xbff, big-endian 0xAARRGGBB), frames.txt ("byteorder le|be", then "frame irq w h")
--   CPS2SAT_GFX_OUT      optional: MAME's graphics region written here before the run
--   CPS2SAT_GFX_REGION   region tag (default ":gfx")
local function need(name) local v = os.getenv(name); assert(v and v ~= "", name .. " not set"); return v end
local function num(s) return math.tointeger(tonumber(s)) end

dofile(need("CPS2SAT_GOLDEN_LUA"))

local machine = manager.machine
local prog = machine.devices[":maincpu"].spaces["program"]
local screen = assert(machine.screens[":screen"], "no :screen")
local palette = assert(screen.palette, "the screen has no palette")
local dir = need("CPS2SAT_FRAMES_DIR")

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

local lc_addr, lc_mask = need("CPS2SAT_LAYER_CTRL"):match("^%s*([^,]+),%s*([^,]+)%s*$")
lc_addr, lc_mask = num(lc_addr), num(lc_mask)
cps2sat_layer_tap = prog:install_write_tap(lc_addr, lc_addr + 1, "cps2sat_layers", function(off, data, mask)
    return data & ~lc_mask
end)

local want = {}
for n in need("CPS2SAT_FRAMES"):gmatch("%d+") do want[num(n)] = true end
local log = assert(io.open(dir .. "/frames.txt", "w"))
log:write(string.pack("=I4", 1):byte(1) == 1 and "byteorder le\n" or "byteorder be\n")
local frame = 0
cps2sat_sprite_frames = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    if not want[frame] then return end
    local px, w, h = screen:pixels()
    local name = string.format("%s/f%05d", dir, frame)
    local f = assert(io.open(name .. ".rgb", "wb")); f:write(px); f:close()
    local pens = {}
    for i = 0, 0x1ff do pens[#pens + 1] = string.pack(">I4", palette:pen_color(i)) end
    pens[#pens + 1] = string.pack(">I4", palette:pen_color(0xbff))
    f = assert(io.open(name .. ".pal", "wb")); f:write(table.concat(pens)); f:close()
    log:write(string.format("%d %d %d %d\n", frame, cps2sat_golden_irq(), w, h))
    log:flush()
end)
