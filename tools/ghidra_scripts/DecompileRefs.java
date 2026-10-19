// Decompile every function that references the given targets (function names or addresses).
// Headless: analyzeHeadless <proj> <name> -process SLES_027.93 -readOnly -noanalysis
//           -scriptPath tools/ghidra_scripts -postScript DecompileRefs.java out/refs.c CdRead 8001a790
//@category CrisisBeat
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class DecompileRefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (int i = 1; i < args.length; i++) {
                Address target = resolve(args[i]);
                if (target == null) {
                    out.printf("// %s: not found%n%n", args[i]);
                    continue;
                }
                Set<Function> callers = new LinkedHashSet<>();
                for (Reference r : getReferencesTo(target)) {
                    Function f = getFunctionContaining(r.getFromAddress());
                    out.printf("// %s <- %s (%s)%n", args[i], r.getFromAddress(),
                            f == null ? "no function" : f.getName());
                    if (f != null) callers.add(f);
                }
                for (Function f : callers) {
                    DecompileResults res = dec.decompileFunction(f, 60, monitor);
                    out.printf("%n// ==== %s @ %s (refs %s)%n%s%n", f.getName(), f.getEntryPoint(),
                            args[i], res.decompileCompleted() ? res.getDecompiledFunction().getC()
                                    : "// decompile failed: " + res.getErrorMessage());
                }
            }
        }
        dec.dispose();
    }

    private Address resolve(String s) {
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (f.getName().equals(s)) return f.getEntryPoint();
        }
        try {
            return toAddr(Long.parseUnsignedLong(s, 16));
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
