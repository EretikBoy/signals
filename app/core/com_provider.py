# core/com_provider.py
import serial
from serial.tools import list_ports
import time
from typing import Optional, List, Union, Dict, Any, Type
from types import TracebackType
import logging

class COMError(Exception):
    """Базовое исключение для ошибок COM-порта"""
    pass

class COMConnectionError(COMError):
    """Ошибка подключения к COM-порту"""
    pass

class COMTimeoutError(COMError):
    """Ошибка таймаута операции"""
    pass

class COMReadWriteError(COMError):
    """Ошибка чтения/записи в порт"""
    pass

class COMProvider:    
    DEFAULT_SETTINGS = {
        'gwinstek': {
            'baudrate': 38400,
            'bytesize': serial.EIGHTBITS,
            'parity': serial.PARITY_NONE,
            'stopbits': serial.STOPBITS_ONE,
            'xonxoff': False,
            'rtscts': False,
            'dsrdtr': False,
            'timeout': 5.0,
            'write_timeout': 5.0
        }
    }
    
    def __init__(self, port: Optional[str] = None, device_type: str = 'gwinstek', 
                 logger: Optional[logging.Logger] = None, **kwargs):
        self.port = port
        self.device_type = device_type
        self.connection = None
        self.is_connected = False
        self.settings = self.DEFAULT_SETTINGS.get(device_type, {}).copy()
        self.settings.update(kwargs)
        self.logger = logger or logging.getLogger(__name__)
        
    def connect(self, port: Optional[str] = None) -> None:
        if port is not None:
            self.port = port
        if not self.port:
            raise COMConnectionError("COM port not specified")
            
        try:
            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.settings['baudrate'],
                bytesize=self.settings['bytesize'],
                parity=self.settings['parity'],
                stopbits=self.settings['stopbits'],
                xonxoff=self.settings['xonxoff'],
                rtscts=self.settings['rtscts'],
                dsrdtr=self.settings['dsrdtr'],
                timeout=self.settings['timeout'],
                write_timeout=self.settings['write_timeout']
            )
            time.sleep(2)
            self.clear_buffers()
            self.is_connected = True
            self.logger.info(f"Connected to {self.port}")
            return True
            
        except serial.SerialException as e:
            self.is_connected = False
            self.logger.error(f"Connection failed: {e}")
            raise COMConnectionError(f"Failed to connect to {self.port}: {e}")
            
    def disconnect(self) -> None:
        if self.connection and self.connection.is_open:
            self.connection.close()
            self.is_connected = False
            self.logger.info(f"Disconnected from {self.port}")
            
    def write(self, data: Union[str, bytes]) -> None:
        if not self.is_connected or not self.connection:
            raise COMConnectionError("Not connected to COM port")
            
        try:
            if isinstance(data, str):
                data = data.encode()
            self.connection.write(data)
        except serial.SerialException as e:
            self.is_connected = False
            self.logger.error(f"Write failed: {e}")
            raise COMReadWriteError(f"Write operation failed: {e}")
            
    def read(self, size: int = 1) -> bytes:
        if not self.is_connected or not self.connection:
            raise COMConnectionError("Not connected to COM port")
            
        try:
            return self.connection.read(size)
        except serial.SerialException as e:
            self.is_connected = False
            self.logger.error(f"Read failed: {e}")
            raise COMReadWriteError(f"Read operation failed: {e}")
            
    def read_line(self, timeout: Optional[float] = None) -> str:
        if not self.is_connected or not self.connection:
            raise COMConnectionError("Not connected to COM port")
            
        try:
            original_timeout = self.connection.timeout
            if timeout is not None:
                self.connection.timeout = timeout
                
            line = self.connection.readline()
            
            if timeout is not None:
                self.connection.timeout = original_timeout
                
            if not line:
                raise COMTimeoutError("Read timeout occurred")
                
            return line.decode(errors='ignore').strip()
            
        except serial.SerialException as e:
            self.is_connected = False
            self.logger.error(f"Read line failed: {e}")
            raise COMReadWriteError(f"Read line operation failed: {e}")
            
    def clear_buffers(self) -> None:
        if self.connection and self.connection.is_open:
            try:
                self.connection.reset_input_buffer()
                self.connection.reset_output_buffer()
            except serial.SerialException as e:
                self.logger.warning(f"Clear buffers failed: {e}")
            
    def query(self, command: str, delay: float = 0.1) -> str:
        self.write(command)
        time.sleep(delay)
        return self.read_line()
        
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type: Optional[Type[BaseException]], 
                 exc_val: Optional[BaseException], 
                 exc_tb: Optional[TracebackType]) -> bool:
        self.disconnect()
        return False
    

if __name__ == '__main__':
    # Пример использования с базовой настройкой логгирования
    logging.basicConfig(level=logging.INFO)
    
    try:
        with COMProvider('COM8') as com:
            response = com.query("*IDN?\n")
            print(f"Device ID: {response}")
    except COMError as e:
        print(f"COM error occurred: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")