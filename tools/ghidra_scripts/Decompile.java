// Decompile the given functions (names or hex addresses) into one C file.
// Headless: analyzeHeadless <proj> <name> -process SLES_027.93 -readOnly -noanalysis
//           -scriptPath tools/ghidra_scripts -postScript Decompile.java out/f.c Mode_LoadOverlay 8001e488
//@category CrisisBeat
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class Decompile extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (int i = 1; i < args.length; i++) {
                Function f = lookup(args[i]);
                if (f == null) {
                    out.printf("// %s: no function%n%n", args[i]);
                    continue;
                }
                DecompileResults res = dec.decompileFunction(f, 60, monitor);
                out.printf("// ==== %s @ %s%n%s%n", f.getName(), f.getEntryPoint(),
                        res.decompileCompleted() ? res.getDecompiledFunction().getC()
                                : "// decompile failed: " + res.getErrorMessage());
            }
        }
        dec.dispose();
    }

    private Function lookup(String s) {
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (f.getName().equals(s)) return f;
        }
        try {
            return getFunctionAt(toAddr(Long.parseUnsignedLong(s, 16)));
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
