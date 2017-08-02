"""
Copyright (c) 2017 Riptide IO, Inc. All Rights Reserved.

"""
from __future__ import absolute_import, unicode_literals

from pymodbus.server.sync import ModbusSerialServer
from pymodbus.server.sync import ModbusTcpServer
from pymodbus.server.sync import ModbusSingleRequestHandler
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext

from pymodbus.transaction import ModbusRtuFramer

from threading import Thread, RLock
import logging

log = logging.getLogger(__name__)

SERVERS = {
    "tcp": ModbusTcpServer,
    "rtu": ModbusSerialServer
}

_FX_MAPPER = {
    "coils": 1,
    'discrete_inputs': 2,
    'input_registers': 4,
    'holding_registers': 3
}

_STORE_MAPPER = {
    "coils": "c",
    'discrete_inputs': 'd',
    'input_registers': 'i',
    'holding_registers': 'h'
}


class CustomDataBlock(ModbusSequentialDataBlock):

    def __init__(self, *args, **kwargs):
        super(CustomDataBlock, self).__init__(*args, **kwargs)
        self._data_lock = RLock()

    def update(self, size):
        with self._data_lock:
            values = [self.default_value] * size
            self.values.extend(values)


class CustomSingleRequestHandler(ModbusSingleRequestHandler):

    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.running = True
        self.setup()


class MbusSerialServer(ModbusSerialServer):

    handler = None

    def __init__(self, *args, **kwargs):
        super(MbusSerialServer, self).__init__(*args, **kwargs)
        self._build_handler()

    def _build_handler(self):
        ''' A helper method to create and monkeypatch
            a serial handler.

        :returns: A patched handler
        '''
        request = self.socket
        request.send = request.write
        request.recv = request.read
        self.handler = CustomSingleRequestHandler(request,
            (self.device, self.device), self)

    def serve_forever(self):
        ''' Callback for connecting a new client thread

        :param request: The request to handle
        :param client: The address of the client
        '''
        log.debug("Started thread to serve client")
        if not self.handler:
            self._build_handler()
        while self.is_running:
            self.handler.handle()

    def server_close(self):
        ''' Callback for stopping the running server
        '''
        log.debug("Modbus server stopped")
        self.is_running = False
        self.handler.finish()
        self.handler.running = False
        self.handler = None
        self.socket.close()


class ThreadedModbusServer(Thread):

    def __init__(self, server):
        super(ThreadedModbusServer, self).__init__(name="ModbusServerThread")
        self._server = server
        self.daemon = True

    def run(self):
        self._server.serve_forever()

    def stop(self):
        if isinstance(self._server, ModbusTcpServer):
            self._server.shutdown()
        else:
            if self._server.socket:
                self._server.server_close()


class ModbusSimu(object):
    _server_add = ()

    def __init__(self, server="tcp", *args, **kwargs):
        # initialize server information
        self.identity = ModbusDeviceIdentification()
        self._add_device_info()
        self._server_type = server
        self._port = kwargs.get('port', None)

        self.context = ModbusServerContext(single=False)
        self.simulate = kwargs.get('simulate', False)
        if server == "tcp":
            self._port = int(self._port)
            self._address = kwargs.get("address", "localhost")
            self.server = ModbusTcpServer(self.context,
                                          identity=self.identity,
                                          address=(self._address, self._port))
        else:
            self.server = MbusSerialServer(self.context,
                                             framer=ModbusRtuFramer,
                                             identity=self.identity, **kwargs)
        self.server_thread = ThreadedModbusServer(self.server)

    def _add_device_info(self):
        self.identity.VendorName = 'Riptide'
        self.identity.ProductCode = 'sim-007'
        self.identity.VendorUrl = 'http://github.com/riptideio/'
        self.identity.ProductName = 'Modbus Server'
        self.identity.ModelName = 'Modbus Server'
        self.identity.MajorMinorRevision = '1.0.0'

    @property
    def server_type(self):
        return self._server_type

    @property
    def port(self):
        return self._port

    def _add_default_slave_context(self):
        return ModbusSlaveContext(
            di=CustomDataBlock(0, 0),
            hr=CustomDataBlock(0, 0),
            co=CustomDataBlock(0, 0),
            ir=CustomDataBlock(0, 0),

        )

    def add_slave(self, slave_id):
        self.context[slave_id] = self._add_default_slave_context()

    def remove_slave(self, slave_id):
        del self.context[slave_id]

    def remove_all_slave(self):
        self.context = ModbusServerContext(single=False)

    def add_block(self, slave_id, block_name, block_type, starting_add, size):
        slave = self.get_slave(slave_id)
        if not slave.validate(_FX_MAPPER[block_name], starting_add, count=size):
            slave.store[_STORE_MAPPER[block_name]].update(size)
        else:
            log.debug("Block '{}' on slave '{}' already exists".format(block_name, slave_id))

    def remove_block(self, slave_id, block_name):
        slave = self.get_slave(slave_id)
        slave.remove_block(block_name)

    def remove_all_blocks(self, slave_id):
        slave = self.get_slave(slave_id)
        slave.remove_all_blocks()

    def set_values(self, slave_id, block_name, address, values):
        values = values if isinstance(values, (list, tuple)) else [values]
        slave = self.get_slave(slave_id)
        if slave.validate(_FX_MAPPER[block_name], address, count=len(values)):
            slave.setValues(_FX_MAPPER[block_name], address, values)

    def get_values(self, slave_id, block_name, address, size):
        slave = self.get_slave(slave_id)
        if slave.validate(_FX_MAPPER[block_name], address, count=size):
            return slave.getValues(_FX_MAPPER[block_name], address, size)

    def get_slave(self, slave_id):
        return self.context[slave_id]

    def start(self):
        self.server_thread.start()

    def stop(self):
        self.server_thread.stop()
        # if self._server_type == 'rtu':
        #     self._serial.close()
        # self._server_add = ()

    def get_slaves(self):
        if self.server is not None:
            return self.server._databank._slaves


if __name__ == "__main__":
    s = ModbusSimu(server="rtu", port="/dev/ptyp0")
    # s = ModbusSimu(address="localhost", port=5020)
    s.start()
    s.add_slave(1)
    s.add_block(1, "holding registers", "holding_registers", 0, 100)
    s.add_block(1, "coils", "holding_registers", 0, 100)
    s.set_values(1, "holding registers", 0, [34] * 55)
    log.info(s.get_values(1, "holding registers", 0, 100))
    s.stop()
