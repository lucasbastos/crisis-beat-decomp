// Apply names and comments from notes/symbols.tsv (address<TAB>name<TAB>comment).
// Functions at the address are renamed; otherwise a primary label is created.
// Headless: analyzeHeadless <proj> <name> -process SLES_027.93 -noanalysis
//           -scriptPath tools/ghidra_scripts -postScript ApplySymbols.java notes/symbols.tsv
//@category CrisisBeat
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;
import java.nio.file.Files;
import java.nio.file.Path;

public class ApplySymbols extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String path = args.length > 0 ? args[0] : askFile("symbols.tsv", "Apply").getPath();
        int count = 0;
        for (String line : Files.readAllLines(Path.of(path))) {
            if (line.isBlank() || line.startsWith("#")) continue;
            String[] cols = line.split("\t", 3);
            Address a = toAddr(Long.parseUnsignedLong(cols[0], 16));
            Function f = getFunctionAt(a);
            if (f != null) {
                f.setName(cols[1], SourceType.USER_DEFINED);
            } else {
                createLabel(a, cols[1], true, SourceType.USER_DEFINED);
            }
            if (cols.length > 2 && !cols[2].isBlank()) {
                currentProgram.getListing().setComment(a, CodeUnit.PLATE_COMMENT, cols[2]);
            }
            count++;
        }
        println("applied " + count + " symbols");
    }
}
