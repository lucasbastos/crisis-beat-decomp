-- Log every DATA.0 load/seek while the game runs (PCSX-Redux).
-- Launch: pcsx-redux.exe -iso "Crisis Beat (Europe).cue" -debugger -interpreter -run
--                       -dofile tools/pcsx/log_loads.lua
-- Output: out/loads-<date>-<time>.tsv (seconds, event, entry, dst, caller, scene, group, extra),
-- also echoed to the Lua console. Addresses come from notes/symbols.tsv.
-- Events: load / seek (DATA.0), group-write (g_Scenario), object (Res_RelocateObject id,
-- once per scene), model (GsMapModelingData pointer and 64 bytes from p-4, once per pointer).

local ffi = require('ffi')

local DATA_LOAD_ENTRY = 0x8001e488 -- Data_LoadEntry(_, n, dst)
local DATA_SEEK_ENTRY = 0x8001e4ec -- Data_SeekEntry(_, n)
local G_SCENE_ID      = 0x800588ac -- u32: scene number (area pair = base + scene*2)
local G_SCENE_GROUP   = 0x8005890f -- u8: g_Scenario, selects the scene-code group (base)
local OVERLAY_BASE    = 0x80064668 -- slot-1 overlays load here
local RES_RELOCATE    = 0x80068824 -- ovl16 Res_RelocateObject(id); valid only while overlay 16 is loaded
local GS_MAP_MODEL    = 0x80034318 -- GsMapModelingData(tmd + 4)
local CLOCK = 33868800             -- PS1 CPU clock, for cycles -> seconds

local LOG_PATH = 'out/loads-' .. os.date('%Y%m%d-%H%M%S') .. '.tsv' -- one file per run
local log = io.open(LOG_PATH, 'w')
if log then log:write('seconds\tevent\tentry\tdst\tcaller\tscene\tgroup\textra\n') end

local function ram(addr) return PCSX.getMemPtr() + bit.band(addr, 0x1fffff) end
local function u32(addr) return ffi.cast('uint32_t*', ram(addr))[0] end
local function u8(addr) return ffi.cast('uint8_t*', ram(addr))[0] end
local function hexdump(addr, n)
    local t = {}
    for i = 0, n - 1 do t[#t + 1] = string.format('%02x', u8(addr + i)) end
    return table.concat(t, ' ')
end

local currentOverlay = -1      -- entry last loaded at OVERLAY_BASE
local seenObjects, seenModels = {}, {}
local lastScene = -1

local function emit(event, entry, dst, caller, extra)
    -- entry is a C `short`: sign-extend the low 16 bits of a1
    entry = bit.band(entry, 0xffff)
    if entry >= 0x8000 then entry = entry - 0x10000 end
    local line = string.format('%.2f\t%s\t%d\t%08x\t%08x\t%d\t%d\t%s',
        tonumber(PCSX.getCPUCycles()) / CLOCK, event, entry, dst, caller,
        u32(G_SCENE_ID), u8(G_SCENE_GROUP), extra or '')
    print(line)
    if log then log:write(line, '\n'); log:flush() end
end

local function regs() return PCSX.getRegisters() end

-- Keep references so the breakpoints are not garbage-collected.
LoadLogBreakpoints = {
    PCSX.addBreakpoint(DATA_LOAD_ENTRY, 'Exec', 4, 'Data_LoadEntry', function()
        local r = regs().GPR.n
        if r.a2 == OVERLAY_BASE then currentOverlay = bit.band(r.a1, 0xffff) end
        emit('load', r.a1, r.a2, r.ra - 8)
        return true -- keep the breakpoint, do not pause
    end),
    PCSX.addBreakpoint(DATA_SEEK_ENTRY, 'Exec', 4, 'Data_SeekEntry', function()
        local r = regs().GPR.n
        emit('seek', r.a1, 0, r.ra - 8)
        return true
    end),
    -- Fires before the store lands: the group column shows the old value,
    -- the next load line shows the new one.
    PCSX.addBreakpoint(G_SCENE_GROUP, 'Write', 1, 'g_Scenario', function()
        emit('group-write', 0, 0, regs().rawPC)
        return true
    end),
    PCSX.addBreakpoint(RES_RELOCATE, 'Exec', 4, 'Res_RelocateObject', function()
        if currentOverlay ~= 16 then return true end
        local scene = u32(G_SCENE_ID)
        if scene ~= lastScene then seenObjects, lastScene = {}, scene end
        local r = regs().GPR.n
        local id = bit.band(r.a0, 0xffff)
        if not seenObjects[id] then
            seenObjects[id] = true
            emit('object', id, 0, r.ra - 8)
        end
        return true
    end),
    PCSX.addBreakpoint(GS_MAP_MODEL, 'Exec', 4, 'GsMapModelingData', function()
        local r = regs().GPR.n
        local p = r.a0
        if not seenModels[p] then
            seenModels[p] = true
            emit('model', 0, p, r.ra - 8, hexdump(p - 4, 64))
        end
        return true
    end),
}

print('log_loads.lua: logging DATA.0 loads to ' .. LOG_PATH)
