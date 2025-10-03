#utils/constants.py

# Стили кнопок
BUTTON_STYLE_SUCCESS = 'background-color: rgba(76, 150, 80, 60);'
BUTTON_STYLE_ERROR = 'background-color: rgba(160, 80, 80, 60);'
BUTTON_STYLE_NORMAL = 'background-color: rgba(200, 200, 200, 60);'
BUTTON_STYLE_WARNING = 'background-color: rgba(252, 215, 3, 60);'
BUTTON_STYLE_ACTIVE = 'background-color: rgba(70, 130, 180, 60);'
BUTTON_STYLE_MEASURE = '''
    QPushButton {
        background-color: rgba(70, 130, 180, 180);
        color: white;
        font-weight: bold;
        font-size: 14px;
        padding: 8px;
        border: 2px solid rgba(50, 110, 160, 200);
        border-radius: 5px;
    }
    QPushButton:hover {
        background-color: rgba(80, 140, 190, 220);
    }
    QPushButton:pressed {
        background-color: rgba(60, 120, 170, 250);
    }
'''

BUTTON_STYLE_STOP = '''
    QPushButton {
        background-color: rgba(160, 80, 80, 180);
        color: white;
        font-weight: bold;
        padding: 8px;
        border: 2px solid rgba(140, 60, 60, 200);
        border-radius: 5px;
    }
    QPushButton:hover {
        background-color: rgba(170, 90, 90, 220);
    }
'''

# Заголовки таблицы
TABLE_HEADERS = [
    'Код предмета', 
    'Файл', 
    'Графики и \nподстройка значений', 
    'Параметр 1', 
    'Параметр 2', 
    'Параметр 3',
    'Параметр 4'
]

# Параметры по умолчанию
DEFAULT_PARAMS = {
    'start_freq': 100,
    'end_freq': 1000,
    'amplitude': 1,
    'offset': 0,
    'sweep_time': 30,
    'record_time': 1,
    'cut_second': 0,
    'fixedlevel': 0.6,
    'gain': 7
}

# Пути и файлы
MEASUREMENTS_DIR = 'measurements'
TABLES_DIR = 'tables'
ANALYSIS_EXTENSION = '*.analysis'