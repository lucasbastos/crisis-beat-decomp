-- Log every DATA.0 load/seek while the game runs (PCSX-Redux).
-- Launch: pcsx-redux.exe -iso "Crisis Beat (Europe).cue" -debugger -interpreter -run
--                       -dofile tools/pcsx/log_loads.lua
-- Output: out/loads.tsv (seconds, event, entry, dst, caller), also echoed to the Lua console.
-- Addresses come from notes/symbols.tsv.

local DATA_LOAD_ENTRY = 0x8001e488 -- Data_LoadEntry(_, n, dst)
local DATA_SEEK_ENTRY = 0x8001e4ec -- Data_SeekEntry(_, n)
local CLOCK = 33868800             -- PS1 CPU clock, for cycles -> seconds

local log = io.open('out/loads.tsv', 'w')
if log then log:write('seconds\tevent\tentry\tdst\tcaller\n') end

local function emit(event, entry, dst, ra)
    -- entry is a C `short`: sign-extend the low 16 bits of a1
    entry = bit.band(entry, 0xffff)
    if entry >= 0x8000 then entry = entry - 0x10000 end
    local line = string.format('%.2f\t%s\t%d\t%08x\t%08x',
        tonumber(PCSX.getCPUCycles()) / CLOCK, event, entry, dst, ra - 8)
    print(line)
    if log then log:write(line, '\n'); log:flush() end
end

local function regs() return PCSX.getRegisters().GPR.n end

-- Keep references so the breakpoints are not garbage-collected.
LoadLogBreakpoints = {
    PCSX.addBreakpoint(DATA_LOAD_ENTRY, 'Exec', 4, 'Data_LoadEntry', function()
        local r = regs()
        emit('load', r.a1, r.a2, r.ra)
        return true -- keep the breakpoint, do not pause
    end),
    PCSX.addBreakpoint(DATA_SEEK_ENTRY, 'Exec', 4, 'Data_SeekEntry', function()
        local r = regs()
        emit('seek', r.a1, 0, r.ra)
        return true
    end),
}

print('log_loads.lua: logging DATA.0 loads to out/loads.tsv')
