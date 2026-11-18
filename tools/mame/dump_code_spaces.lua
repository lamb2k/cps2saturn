-- Dump the main CPU's program (data) view and, on CPS-2, its decrypted opcode view over one address range, then exit.
-- MAME exposes them as separate address spaces on the CPS-2 68000. CPS-1 and CPS-Dash have no opcode view: the
-- script writes the program view only and prints NO_OPCODE_SPACE (the program dump is then the lifter's whole image).
-- Output stays local; never commit it.
--   CPS2SAT_FIRST, CPS2SAT_LAST   range, end exclusive (default 0 .. 0x200000)
--   CPS2SAT_OUT_PROGRAM, CPS2SAT_OUT_OPCODES   output files (OPCODES is not needed without an opcode view)
local machine = manager.machine
local cpu = machine.devices[":maincpu"]
local first = math.tointeger(tonumber(os.getenv("CPS2SAT_FIRST") or "0"))
local last = math.tointeger(tonumber(os.getenv("CPS2SAT_LAST") or "0x200000"))

local function dump_space(name, space)
    local path = assert(os.getenv("CPS2SAT_OUT_" .. name), "CPS2SAT_OUT_" .. name .. " not set")
    local output = assert(io.open(path, "wb"))
    local bytes = {}
    for address = first, last - 1 do
        bytes[#bytes + 1] = string.char(space:read_u8(address))
        if #bytes == 4096 then output:write(table.concat(bytes)); bytes = {} end
    end
    if #bytes > 0 then output:write(table.concat(bytes)) end
    output:close()
end

cps2sat_dump = emu.add_machine_frame_notifier(function()
    dump_space("PROGRAM", cpu.spaces["program"])
    if cpu.spaces["opcodes"] then
        dump_space("OPCODES", cpu.spaces["opcodes"])
    else
        print("NO_OPCODE_SPACE program view only")
    end
    print(string.format("CODE_SPACES_WRITTEN %06x..%06x", first, last))
    machine:exit()
end)
