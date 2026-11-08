-- Golden run for the host check. At each real level 2 IRQ entry, write the interrupted PC and d0-d7/a0-a6,
-- then work RAM and object RAM. Log every read of the I/O ranges so the host can replay the board's inputs.
-- Optional: play a saved input route (real ports only) and save states at chosen frames.
--
-- Settings come from the environment (tools/mame_golden_run.py sets them from the per-game config):
--   CPS2SAT_OUT          output file (records); CPS2SAT_OUT.io.txt gets the I/O log
--   CPS2SAT_IRQ_TAP      "first,last" opcode addresses of the IRQ entry fetch
--   CPS2SAT_IRQ_VECTOR   PC value that marks a real IRQ entry (not a prefetch)
--   CPS2SAT_WORK         "base,size" of work RAM;  CPS2SAT_OBJ  "base,size" of object RAM
--   CPS2SAT_IO           "lo-hi;lo-hi" I/O ranges to log
--   CPS2SAT_MAXIRQ       records to write (default 6000)
--   CPS2SAT_DELTA=1      write only changed 32-bit words per record
--   CPS2SAT_ROUTE        route file: "frame word" lines and "last N"; CPS2SAT_ROUTE_BITS "tag|field;tag|field..."
--   CPS2SAT_LAST         stop frame (overrides the route's last)
--   CPS2SAT_SAVE         "frame,frame" to save states named f<frame>
--
-- Record: "VBLK", u32 irq number, 16 x u32 (pc, d0-d7, a0-a6), then either work RAM + object RAM in full, or
-- (delta) u32 run count, then per run u16 first word, u16 words, data. Word index counts work RAM from 0 and
-- object RAM from work_size / 4.

local function num(s) return math.tointeger(tonumber(s)) end
local function pair(s) local a, b = s:match("^%s*([^,]+),%s*([^,]+)%s*$"); return num(a), num(b) end
local function need(name) local v = os.getenv(name); assert(v and v ~= "", name .. " not set"); return v end

local cpu = manager.machine.devices[":maincpu"]
local prog = cpu.spaces["program"]
local ops = cpu.spaces["opcodes"]
local path = need("CPS2SAT_OUT")
local tap_lo, tap_hi = pair(need("CPS2SAT_IRQ_TAP"))
local vector = num(need("CPS2SAT_IRQ_VECTOR"))
local work_base, work_size = pair(need("CPS2SAT_WORK"))
local obj_base, obj_size = pair(need("CPS2SAT_OBJ"))
local maxirq = num(os.getenv("CPS2SAT_MAXIRQ") or "6000")
local delta = os.getenv("CPS2SAT_DELTA") == "1"

local out = assert(io.open(path, "wb"))
local iolog = assert(io.open(path .. ".io.txt", "w"))
local irq = 0
local work_words, obj_words = work_size // 4, obj_size // 4
local total_words = work_words + obj_words

local function dump(base, n)
    local t = {}
    for i = 0, n - 4, 4 do t[#t + 1] = string.pack(">I4", prog:read_u32(base + i)) end
    out:write(table.concat(t))
end

local prevw = {}
local function delta_dump()
    local cur = {}
    for i = 0, work_words - 1 do cur[i] = prog:read_u32(work_base + i * 4) end
    for i = 0, obj_words - 1 do cur[work_words + i] = prog:read_u32(obj_base + i * 4) end
    local t, nruns, i = {}, 0, 0
    while i < total_words do
        if cur[i] ~= prevw[i] then
            local b = i
            while i < total_words and cur[i] ~= prevw[i] and i - b < 0xffff do i = i + 1 end
            t[#t + 1] = string.pack(">I2I2", b, i - b)
            for k = b, i - 1 do t[#t + 1] = string.pack(">I4", cur[k]) end
            nruns = nruns + 1
        else i = i + 1 end
    end
    out:write(string.pack(">I4", nruns)); out:write(table.concat(t))
    prevw = cur
end

cps2sat_tap_irq = ops:install_read_tap(tap_lo, tap_hi, "cps2sat_golden", function()
    -- The tap also fires on prefetch; at a real entry PC still reads as the vector and the frame is at SP.
    if cpu.state["PC"].value ~= vector then return end
    if irq < maxirq then
        out:write(string.pack(">c4I4", "VBLK", irq))
        local sp = cpu.state["SP"].value
        local rr = {prog:read_u32(sp + 2) & 0xffffff}
        for i = 0, 7 do rr[#rr + 1] = cpu.state["D" .. i].value end
        for i = 0, 6 do rr[#rr + 1] = cpu.state["A" .. i].value end
        out:write(string.pack(">" .. string.rep("I4", 16), table.unpack(rr)))
        if delta then delta_dump() else dump(work_base, work_size); dump(obj_base, obj_size) end
        out:flush()
    end
    irq = irq + 1
    iolog:write("V\n")
end)

cps2sat_io_taps = {}
for lo, hi in (os.getenv("CPS2SAT_IO") or ""):gmatch("(%w+)%-(%w+)") do
    cps2sat_io_taps[#cps2sat_io_taps + 1] = prog:install_read_tap(num(lo), num(hi), "cps2sat_io" .. #cps2sat_io_taps,
        function(off, data, mask) iolog:write(string.format("%x %x %x\n", off, data, mask)) end)
end
cps2sat_flush = emu.add_machine_frame_notifier(function() iolog:flush() end)

local route = os.getenv("CPS2SAT_ROUTE")
local saves = {}
for n in (os.getenv("CPS2SAT_SAVE") or ""):gmatch("%d+") do saves[num(n)] = true end
local steps, last = {}, nil
local fields = {}
if route and route ~= "" then
    for spec in need("CPS2SAT_ROUTE_BITS"):gmatch("[^;]+") do
        local tag, name = spec:match("^(.-)|(.*)$")
        local port = assert(manager.machine.ioport.ports[tag], "no port " .. tag)
        fields[#fields + 1] = assert(port.fields[name], "no field " .. name .. " in " .. tag)
    end
    for l in io.lines(route) do
        local a, b = l:match("^(%d+) (%d+)")
        if a then steps[num(a)] = num(b) else last = num(l:match("^last (%d+)") or "") or last end
    end
end
last = num(os.getenv("CPS2SAT_LAST") or "") or last
local frame = 0
cps2sat_frames = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    local w = steps[frame]
    if w then
        for i, f in ipairs(fields) do
            if w & (1 << (i - 1)) ~= 0 then f:set_value(1) else f:clear_value() end
        end
    end
    if saves[frame] then manager.machine:save("f" .. frame) end
    if last and frame == last then iolog:close(); out:close(); manager.machine:exit() end
end)
