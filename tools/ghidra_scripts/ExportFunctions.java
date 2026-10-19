// Write every function as "address<TAB>size<TAB>name<TAB>callers" to a TSV file.
// Headless: analyzeHeadless <proj> <name> -process SLES_027.93 -readOnly
//           -scriptPath tools/ghidra_scripts -postScript ExportFunctions.java out/functions.tsv
//@category CrisisBeat
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class ExportFunctions extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String path = args.length > 0 ? args[0] : askString("Output", "TSV path");
        try (PrintWriter out = new PrintWriter(path, "UTF-8")) {
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                out.printf("%s\t%d\t%s\t%d%n", f.getEntryPoint(), f.getBody().getNumAddresses(),
                        f.getName(), f.getSymbol().getReferenceCount());
            }
        }
    }
}
