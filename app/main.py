import sys
import os

import logging
logger = logging.getLogger(__name__)
from PyQt6.QtWidgets import QApplication

# from modules.gwinstekprovider import GWInstekProvider
# from modules.rigolprovider import *
# from modules.tektronixprovider import TektronixProvider
# import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui.window import MainWindow

def main():
    """Точка входа в приложение"""
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()

# if __name__ == '__main__':
#     with GWInstekProvider('COM8') as device:
#         # Создаем фигуру и оси для графика
#         fig, ax = plt.subplots(figsize=(10, 6))
        
#         # Перебираем все каналы
#         for channel_num in range(1, device.chnum + 1):
#             channel = device.get_channel_data(channel_num)
#             if channel and channel.data is not None:
#                 # Извлекаем временные данные и амплитуды
#                 time_data = channel.data['Время'].values
#                 amplitude_data = channel.data['Амплитуда'].values
                
#                 # Строим график для этого канала
#                 ax.plot(time_data, amplitude_data, label=f'CH{channel_num}')
                
#                 print(f"Канал CH{channel_num}:")
#                 print(f"  Количество точек: {len(time_data)}")
#                 print(f"  Временной диапазон: {time_data[0]:.6f} - {time_data[-1]:.6f} сек")
#                 print(f"  Амплитудный диапазон: {amplitude_data.min():.3f} - {amplitude_data.max():.3f} В")
#                 print()
        
#         # Настраиваем график
#         ax.set_xlabel('Время, сек')
#         ax.set_ylabel('Амплитуда, В')
#         ax.set_title('Сигналы с осциллографа GWInstek')
#         ax.grid(True)
#         ax.legend()
        
#         # Показываем график
#         plt.tight_layout()
#         plt.show()

# if __name__ == '__main__':
#     # Пример использования
#     logging.basicConfig(level=logging.INFO)
    
#     try:
#         with RigolProvider('USB0::0x1AB1::0x0588::DG1D140300224::INSTR') as rigol:
#             # Проверка соединения
#             print(f"Connected to: {rigol.model_name}")
            
#             # Настройка развертки
#             rigol.configure_sweep(
#                 start_freq=1000,
#                 stop_freq=10000,
#                 sweep_time=30,
#                 function="SIN",
#                 amplitude=2.5,
#                 offset=0.0
#             )
            
#             # Запуск развертки на 10 секунд
#             rigol.run_sweep(30)
            
#     except RigolError as e:
#         print(f"Rigol error occurred: {e}")
#     except Exception as e:
#         print(f"Unexpected error: {e}")


# if __name__ == '__main__':
#     try:
#         with TektronixProvider('USB0::0x0699::0x0408::C010852::INSTR') as device:
#             # Создаем фигуру и оси для графика
#             fig, ax = plt.subplots(figsize=(10, 6))
            
#             # Перебираем все каналы
#             for channel_num in range(1, device.chnum + 1):
#                 channel = device.get_channel_data(channel_num)
#                 if channel and channel.data is not None:
#                     # Извлекаем временные данные и амплитуды
#                     time_data = channel.data['Время'].values
#                     amplitude_data = channel.data['Амплитуда'].values
                    
#                     # Строим график для этого канала
#                     ax.plot(time_data, amplitude_data, label=f'CH{channel_num}')
                    
#                     print(f"Канал CH{channel_num}:")
#                     print(f"  Количество точек: {len(time_data)}")
#                     print()
            
#             # Настраиваем график
#             ax.set_xlabel('Время, сек')
#             ax.set_ylabel('Амплитуда, В')
#             ax.set_title(f'Сигналы с осциллографа {device.model_name}')
#             ax.grid(True)
#             ax.legend()
            
#             # Показываем график
#             plt.tight_layout()
#             plt.show()

#     except Exception as e:
#         print(f"Ошибка: {str(e)}")

    



