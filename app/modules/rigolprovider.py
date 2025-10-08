# modules/rigolprovider.py
import logging
from typing import Dict, Any, Optional
import time
from core.VISA_provider import VISAProvider

# Настройка логирования
logger = logging.getLogger(__name__)

class RigolError(Exception):
    """Базовое исключение для ошибок Rigol"""
    pass

class RigolCommunicationError(RigolError):
    """Ошибка связи с прибором"""
    pass

class RigolConfigurationError(RigolError):
    """Ошибка конфигурации прибора"""
    pass

class RigolProvider:
    def __init__(self, resource_name: str = None):
        self.visa = VISAProvider(resource_name)
        self.connection_status = 0
        self.model_name = ""
        
    def connect(self) -> bool:
        """Установка соединения с прибором"""
        try:
            if not self.visa.connect():
                raise RigolCommunicationError("Failed to establish VISA connection")
            
            response = self.visa.query("*IDN?", delay=0.5)
            if not response:
                raise RigolCommunicationError("No response to IDN query")
            
            parts = response.split(',')
            if len(parts) < 2:
                raise RigolCommunicationError(f"Invalid IDN response: {response}")
            
            self.model_name = parts[1]
            self.connection_status = 1
            logger.info(f"Connected to {self.model_name}")
            return True
            
        except Exception as e:
            self.connection_status = 0
            logger.error(f"Connection failed: {str(e)}")
            raise RigolCommunicationError(f"Connection failed: {str(e)}")
        
    def disconnect(self):
        """Разрыв соединения с прибором"""
        try:
            self.visa.disconnect()
            self.connection_status = 0
            logger.info("Disconnected from device")
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            raise RigolCommunicationError(f"Disconnect failed: {str(e)}")
    
    def set_function(self, function: str) -> None:
        """Установка формы сигнала"""
        try:
            self.visa.write(f"FUNC {function}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to set function: {str(e)}")
            raise RigolConfigurationError(f"Failed to set function: {str(e)}")
    
    def set_frequency(self, frequency: float) -> None:
        """Установка частоты сигнала"""
        try:
            self.visa.write(f"FREQ {frequency}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to set frequency: {str(e)}")
            raise RigolConfigurationError(f"Failed to set frequency: {str(e)}")
    
    def set_amplitude(self, amplitude: float) -> None:
        """Установка амплитуды сигнала"""
        try:
            self.visa.write(f"VOLT {amplitude}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to set amplitude: {str(e)}")
            raise RigolConfigurationError(f"Failed to set amplitude: {str(e)}")
    
    def set_offset(self, offset: float) -> None:
        """Установка смещения сигнала"""
        try:
            self.visa.write(f"VOLT:OFFS {offset}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to set offset: {str(e)}")
            raise RigolConfigurationError(f"Failed to set offset: {str(e)}")
    
    def enable_sweep(self, enable: bool = True) -> None:
        """Включение/выключение режима развертки"""
        try:
            state = "ON" if enable else "OFF"
            self.visa.write(f"SWE:STAT {state}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to set sweep state: {str(e)}")
            raise RigolConfigurationError(f"Failed to set sweep state: {str(e)}")
    
    def set_sweep_spacing(self, spacing: str) -> None:
        """Установка типа развертки (LIN - линейная, LOG - логарифмическая)"""
        try:
            self.visa.write(f"SWE:SPAC {spacing}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to set sweep spacing: {str(e)}")
            raise RigolConfigurationError(f"Failed to set sweep spacing: {str(e)}")
    
    def set_sweep_start_frequency(self, frequency: float) -> None:
        """Установка начальной частоты развертки"""
        try:
            self.visa.write(f"FREQ:STAR {frequency}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to set sweep start frequency: {str(e)}")
            raise RigolConfigurationError(f"Failed to set sweep start frequency: {str(e)}")
    
    def set_sweep_stop_frequency(self, frequency: float) -> None:
        """Установка конечной частоты развертки"""
        try:
            self.visa.write(f"FREQ:STOP {frequency}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to set sweep stop frequency: {str(e)}")
            raise RigolConfigurationError(f"Failed to set sweep stop frequency: {str(e)}")
    
    def set_sweep_time(self, sweep_time: float) -> None:
        """Установка времени развертки"""
        try:
            self.visa.write(f"SWE:TIME {sweep_time}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to set sweep time: {str(e)}")
            raise RigolConfigurationError(f"Failed to set sweep time: {str(e)}")
    
    def set_trigger_source(self, source: str = "IMM") -> None:
        """Установка источника триггера"""
        try:
            self.visa.write(f"TRIG:SOUR {source}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to set trigger source: {str(e)}")
            raise RigolConfigurationError(f"Failed to set trigger source: {str(e)}")
    
    def set_output(self, enable: bool = True) -> None:
        """Включение/выключение выхода"""
        try:
            state = "ON" if enable else "OFF"
            self.visa.write(f"OUTP {state}")
        except Exception as e:
            logger.error(f"Failed to set output state: {str(e)}")
            raise RigolConfigurationError(f"Failed to set output state: {str(e)}")
    
    def configure_sweep(self, start_freq: float, stop_freq: float, sweep_time: float, 
                        function: str = "SIN", amplitude: float = 1.0, offset: float = 0.0) -> None:
        """Конфигурация полного цикла развертки"""
        try:
            self.set_function(function)
            self.set_amplitude(amplitude)
            self.set_offset(offset)
            self.enable_sweep(True)
            self.set_sweep_spacing("LIN")
            self.set_sweep_start_frequency(start_freq)
            self.set_sweep_stop_frequency(stop_freq)
            self.set_sweep_time(sweep_time)
            self.set_trigger_source("IMM")
        except Exception as e:
            logger.error(f"Failed to configure sweep: {str(e)}")
            raise RigolConfigurationError(f"Failed to configure sweep: {str(e)}")
    
    def run_sweep(self, duration: float = 10.0) -> None:
        """Запуск развертки на указанное время"""
        try:
            self.set_output(True)
            time.sleep(duration)
            self.set_output(False)
        except Exception as e:
            logger.error(f"Failed to run sweep: {str(e)}")
            raise RigolConfigurationError(f"Failed to run sweep: {str(e)}")
        
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


if __name__ == '__main__':
    # Пример использования
    logging.basicConfig(level=logging.INFO)
    
    try:
        with RigolProvider('USB0::0x1AB1::0x0588::DG1D140300224::INSTR') as rigol:
            # Проверка соединения
            print(f"Connected to: {rigol.model_name}")
            
            # Настройка развертки
            rigol.configure_sweep(
                start_freq=100,
                stop_freq=1000,
                sweep_time=10,
                function="SIN",
                amplitude=1.0,
                offset=0.0
            )
            
            # Запуск развертки на 10 секунд
            rigol.run_sweep(10)
            
    except RigolError as e:
        print(f"Rigol error occurred: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")