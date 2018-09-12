"""
Copyright (c) 2018 Riptide IO, Inc. All Rights Reserved.

"""
#supported block types
COILS = 1
DISCRETE_INPUTS = 2
HOLDING_REGISTERS = 3
ANALOG_INPUTS = 4

ADDRESS_RANGE = {
    COILS: 0,
    DISCRETE_INPUTS: 10001,
    HOLDING_REGISTERS: 40001,
    ANALOG_INPUTS: 30001

}

REGISTER_QUERY_FIELDS = {"bit": range(0, 16),
                         "byteorder": ["big", "little"],
                         "formatter": ["default", "float1"],
                         "scaledivisor": 1,
                         "scalemultiplier": 1,
                         "wordcount": 1,
                         "wordorder": ["big", "little"]}


BLOCK_TYPES = {"coils": COILS,
               "discrete_inputs": DISCRETE_INPUTS,
               "holding_registers": HOLDING_REGISTERS,
               "input_registers": ANALOG_INPUTS}
MODBUS_TCP_PORT = 5440