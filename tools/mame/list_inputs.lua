-- Print every input port, field name and mask, tab separated, between markers. Run with -autoboot_script.
-- Use the output to fill inputs.route_bits in the per-game config.
print("CPS2SAT_INPUTS_BEGIN")
for port_tag, port in pairs(manager.machine.ioport.ports) do
    for field_name, field in pairs(port.fields) do
        print(string.format("%s\t%s\t0x%08x", port_tag, field_name, field.mask))
    end
end
print("CPS2SAT_INPUTS_END")
manager.machine:exit()
