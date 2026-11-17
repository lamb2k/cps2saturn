-- Dump a window of the 68000 program space after the first frame, then exit. Use it on the range a script
-- pointer walks, so the record format can be decoded offline. Output stays local; never commit it.
--   CPS2SAT_FIRST, CPS2SAT_LAST   range, end exclusive (required)
--   CPS2SAT_SPACE                 "program" (default) or "opcodes" (CPS-2 only)
--   CPS2SAT_OUT                   output file (required)
local machine = manager.machine
local function need(n) local v = os.getenv(n); assert(v and v ~= "", n .. " not set"); return v end
local space_name = os.getenv("CPS2SAT_SPACE") or "program"
local space = assert(machine.devices[":maincpu"].spaces[space_name],
    "no " .. space_name .. " space on this CPU (CPS-1 and CPS-Dash have no opcode view; use program)")
local first = math.tointeger(tonumber(need("CPS2SAT_FIRST")))
local last = math.tointeger(tonumber(need("CPS2SAT_LAST")))
local path = need("CPS2SAT_OUT")

cps2sat_window = emu.add_machine_frame_notifier(function()
    local file = assert(io.open(path, "wb"))
    local bytes = {}
    for address = first, last - 1 do bytes[#bytes + 1] = string.char(space:read_u8(address)) end
    file:write(table.concat(bytes))
    file:close()
    print(string.format("ROM_WINDOW_WRITTEN %06x..%06x", first, last))
    machine:exit()
end)
