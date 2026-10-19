// Load a DATA.0 code overlay as a Ghidra overlay block, create its entry functions,
// and auto-analyze just that block. Overlays share one load address, so each gets
// its own overlay space (e.g. ovl16::80064668); calls out of it resolve to the main exe.
// Headless: analyzeHeadless <proj> <name> -process SLES_027.93 -noanalysis
//           -scriptPath tools/ghidra_scripts -postScript LoadOverlay.java
//           out/DATA/0016.bin 80064668 ovl16 80065cb0 80066c14
//@category CrisisBeat
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.plugin.core.analysis.AutoAnalysisManager;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;

public class LoadOverlay extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        File file = new File(args[0]);
        Address base = toAddr(Long.parseUnsignedLong(args[1], 16));
        String name = args[2];

        if (currentProgram.getMemory().getBlock(name) != null) {
            println(name + ": block already exists, skipping");
            return;
        }
        MemoryBlock block;
        try (InputStream in = new FileInputStream(file)) {
            block = currentProgram.getMemory().createInitializedBlock(
                    name, base, in, file.length(), monitor, true);
        }
        block.setRead(true);
        block.setWrite(true);
        block.setExecute(true);
        AddressSpace space = block.getStart().getAddressSpace();
        println(name + ": " + block.getStart() + " - " + block.getEnd());

        for (int i = 3; i < args.length; i++) {
            Address ep = space.getAddress(Long.parseUnsignedLong(args[i], 16));
            new DisassembleCommand(ep, null, true).applyTo(currentProgram, monitor);
            new CreateFunctionCmd(ep).applyTo(currentProgram, monitor);
            currentProgram.getSymbolTable().addExternalEntryPoint(ep);
            createLabel(ep, name + "_entry_" + args[i], false, SourceType.USER_DEFINED);
        }

        AutoAnalysisManager mgr = AutoAnalysisManager.getAnalysisManager(currentProgram);
        mgr.reAnalyzeAll(new AddressSet(block.getStart(), block.getEnd()));
        mgr.startAnalysis(monitor);
        int count = currentProgram.getFunctionManager().getFunctions(
                new AddressSet(block.getStart(), block.getEnd()), true).hasNext() ? 1 : 0;
        println(name + ": analysis done" + (count > 0 ? "" : " (no functions found)"));
    }
}
