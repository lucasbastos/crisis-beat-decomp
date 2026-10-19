// Disassemble and create a function at each given hex address (skips existing ones).
// Headless: analyzeHeadless <proj> <name> -process SLES_027.93 -noanalysis
//           -scriptPath tools/ghidra_scripts -postScript CreateFunctions.java 800233a8 ...
//@category CrisisBeat
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class CreateFunctions extends GhidraScript {
    @Override
    public void run() throws Exception {
        for (String arg : getScriptArgs()) {
            Address a = toAddr(Long.parseUnsignedLong(arg, 16));
            if (getFunctionAt(a) != null) {
                println(arg + ": already a function");
                continue;
            }
            new DisassembleCommand(a, null, true).applyTo(currentProgram, monitor);
            boolean ok = new CreateFunctionCmd(a).applyTo(currentProgram, monitor);
            println(arg + (ok ? ": created " + getFunctionAt(a).getName() : ": FAILED"));
        }
    }
}
