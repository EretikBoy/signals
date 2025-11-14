# restore_with_analysis_fixed.py
import os
import pickle
import shutil
from datetime import datetime
import pandas as pd

class RestoredChannel:
    """Восстановленный канал, соответствующий оригинальному классу Channel"""
    def __init__(self, name):
        self.name = name
        self.data = pd.DataFrame(columns=['Время', 'Амплитуда'])
        self.metadata = {}
        self.raw_metadata = {}

    def set_data(self, time_data, amplitude_data):
        """Устанавливает данные в формате оригинального Channel"""
        self.data = pd.DataFrame({
            'Время': time_data,
            'Амплитуда': amplitude_data
        })

    def set_metadata_from_dict(self, metadata_dict):
        """Устанавливает метаданные"""
        self.raw_metadata = metadata_dict
        self.metadata = metadata_dict

    def __repr__(self):
        return f'Канал {self.name}, размер массива {len(self.data)}'

def restore_complete_analysis_fixed(original_analysis_path, output_dir):
    """
    Полное восстановление с правильной структурой Channel
    """
    print(f"=== ПОЛНОЕ ВОССТАНОВЛЕНИЕ (ИСПРАВЛЕННОЕ) ===")
    print(f"Источник: {original_analysis_path}")
    print(f"Цель: {output_dir}")
    
    if not os.path.exists(original_analysis_path):
        print(f"Файл анализа не найден: {original_analysis_path}")
        return False
    
    try:
        with open(original_analysis_path, 'rb') as f:
            analysis_data = pickle.load(f)
    except Exception as e:
        print(f"Ошибка загрузки файла анализа: {e}")
        return False
    
    # Создаем папку с именем файла анализа (без расширения)
    analysis_filename = os.path.basename(original_analysis_path)
    analysis_name = os.path.splitext(analysis_filename)[0]
    restore_base_dir = os.path.join(output_dir, analysis_name)
    csv_dir = os.path.join(restore_base_dir, analysis_name)
    os.makedirs(csv_dir, exist_ok=True)
    
    # 1. Восстанавливаем CSV файлы с правильной структурой
    print("\n1. Восстановление CSV файлов с правильной структурой...")
    csv_count = restore_csv_properly(analysis_data, csv_dir)
    
    if csv_count == 0:
        print("Не удалось восстановить CSV файлы")
        return False
    
    # 2. Создаем файл анализа с правильной структурой Channel
    print("\n2. Создание файла анализа с правильной структурой...")
    analysis_file_path = os.path.join(restore_base_dir, f'{analysis_name}.analysis')
    success = create_analysis_properly(analysis_data, csv_dir, analysis_file_path)
    
    if success:
        print(f"\n=== ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО ===")
        print(f"CSV файлов: {csv_count}")
        print(f"Файл анализа: {analysis_file_path}")
        print(f"Общая папка: {restore_base_dir}")
        
        create_instruction_file(restore_base_dir, csv_count, analysis_name)
        return True
    else:
        print("Ошибка при создании файла анализа")
        return False

def restore_csv_properly(analysis_data, output_dir):
    """
    Восстанавливает CSV файлы в правильном формате с временными метками из метаданных
    """
    restored_count = 0
    
    for subject_code, subject_info in analysis_data.get('subjects', {}).items():
        for analysis_index, analysis_info in subject_info.get('analyses', {}).items():
            try:
                # Создаем уникальное имя файла с временной меткой из метаданных
                file_name = create_proper_filename_from_metadata(subject_code, analysis_index, analysis_info)
                
                # Восстанавливаем данные каналов в правильном формате
                channels_data = analysis_info.get('channels_data', {})
                if channels_data:
                    # Создаем общий DataFrame для всех каналов в правильном формате
                    all_data = pd.DataFrame()
                    
                    for channel_name, channel_info in channels_data.items():
                        # Получаем данные канала в правильном формате
                        channel_df = pd.DataFrame(channel_info['data'])
                        
                        # Убеждаемся, что колонки называются 'Время' и 'Амплитуда'
                        if 'Время' in channel_df.columns and 'Амплитуда' in channel_df.columns:
                            # Переименовываем колонки для многоканального CSV
                            channel_data_renamed = pd.DataFrame({
                                f'{channel_name}_Время': channel_df['Время'],
                                f'{channel_name}_Амплитуда': channel_df['Амплитуда']
                            })
                            
                            if all_data.empty:
                                all_data = channel_data_renamed
                            else:
                                all_data = pd.concat([all_data, channel_data_renamed], axis=1)
                    
                    if not all_data.empty:
                        output_path = os.path.join(output_dir, file_name)
                        all_data.to_csv(output_path, index=False, encoding='utf-8')
                        restored_count += 1
                        print(f"✓ {file_name} (каналы: {list(channels_data.keys())})")
                    
            except Exception as e:
                print(f"✗ Ошибка восстановления {subject_code}_{analysis_index}: {e}")
                continue
    
    print(f"Восстановлено CSV файлов: {restored_count}")
    return restored_count

def create_proper_filename_from_metadata(subject_code, analysis_index, analysis_info):
    """
    Создает правильное имя файла на основе временной метки из метаданных
    """
    params = analysis_info.get('params', {})
    
    # Используем временную метку из метаданных если есть
    timestamp = params.get('timestamp')
    if timestamp:
        # Преобразуем временную метку в формат, пригодный для имени файла
        try:
            # Пробуем разные форматы временных меток
            if isinstance(timestamp, str):
                # Убираем недопустимые символы для имени файла
                clean_timestamp = timestamp.replace(':', '').replace('/', '').replace(' ', '_').replace('-', '')
                return f"{subject_code}_{analysis_index}_{clean_timestamp}.csv"
            else:
                # Если это datetime объект или другой формат
                clean_timestamp = str(timestamp).replace(':', '').replace('/', '').replace(' ', '_').replace('-', '')
                return f"{subject_code}_{analysis_index}_{clean_timestamp}.csv"
        except:
            # Если не удалось обработать временную метку, используем параметры измерения
            pass
    
    # Используем параметры измерения как запасной вариант
    start_freq = params.get('start_freq', 'unknown')
    end_freq = params.get('end_freq', 'unknown')
    record_time = params.get('record_time', 'unknown')
    return f"{subject_code}_{analysis_index}_{start_freq}_{end_freq}_{record_time}.csv"

def create_analysis_properly(original_analysis_data, csv_directory, output_analysis_path):
    """
    Создает файл анализа с правильной структурой Channel
    """
    print(f"Создание анализа для данных в: {csv_directory}")
    
    if not os.path.exists(csv_directory):
        print(f"Папка с CSV не найдена: {csv_directory}")
        return False
    
    csv_files = [f for f in os.listdir(csv_directory) if f.endswith('.csv')]
    print(f"Найдено CSV файлов: {len(csv_files)}")
    
    if not csv_files:
        print("Нет CSV файлов для создания анализа")
        return False
    
    # Создаем структуру анализа на основе оригинальной
    analysis_data = {
        'subjects': {},
        'files': {},
        'timestamp': datetime.now().isoformat(),
        'auto_save': False,
        'restored': True,
        'restored_from': csv_directory
    }
    
    # Восстанавливаем структуру предметов и анализов из оригинальных данных
    for subject_code, subject_info in original_analysis_data.get('subjects', {}).items():
        analysis_data['subjects'][subject_code] = {
            'analyses': {},
            'metadata': subject_info.get('metadata', {}),
            'subject_name': subject_info.get('subject_name', subject_code)
        }
        
        # Восстанавливаем анализы для этого предмета
        for analysis_index, original_analysis_info in subject_info.get('analyses', {}).items():
            # Находим соответствующий CSV файл
            csv_file = find_matching_csv(csv_files, subject_code, analysis_index)
            if not csv_file:
                continue
                
            file_path = os.path.join(csv_directory, csv_file)
            
            try:
                # Читаем CSV и создаем каналы в правильном формате
                df = pd.read_csv(file_path)
                channels_data = {}
                
                # Определяем каналы по колонкам
                channel_names = set()
                for col in df.columns:
                    if '_Время' in col:
                        channel_name = col.replace('_Время', '')
                        channel_names.add(channel_name)
                    elif '_Амплитуда' in col:
                        channel_name = col.replace('_Амплитуда', '')
                        channel_names.add(channel_name)
                
                # Создаем структуру каналов в формате оригинального Channel
                for channel_name in channel_names:
                    time_col = f'{channel_name}_Время'
                    amp_col = f'{channel_name}_Амплитуда'
                    
                    if time_col in df.columns and amp_col in df.columns:
                        # СОЗДАЕМ ДАННЫЕ В ФОРМАТЕ ОРИГИНАЛЬНОГО CHANNEL
                        channel_data = {
                            'Время': df[time_col].to_dict(),
                            'Амплитуда': df[amp_col].to_dict()
                        }
                        
                        channels_data[channel_name] = {
                            'data': channel_data,
                            'name': channel_name
                        }
                
                # Восстанавливаем параметры из оригинального анализа
                params = original_analysis_info.get('params', {})
                
                # Создаем запись анализа
                analysis_data['subjects'][subject_code]['analyses'][analysis_index] = {
                    'file_name': csv_file,
                    'original_file_name': original_analysis_info.get('original_file_name', csv_file),
                    'params': params,
                    'channels_data': channels_data
                }
                
                analysis_data['files'][(subject_code, analysis_index)] = csv_file
                
                print(f"✓ Обработан: {csv_file} -> {subject_code}_{analysis_index}")
                
            except Exception as e:
                print(f"✗ Ошибка обработки {csv_file}: {e}")
                continue
    
    # Сохраняем файл анализа
    try:
        with open(output_analysis_path, 'wb') as f:
            pickle.dump(analysis_data, f)
        
        print(f"\nФайл анализа создан: {output_analysis_path}")
        print(f"Всего предметов: {len(analysis_data['subjects'])}")
        total_analyses = sum(len(subject['analyses']) for subject in analysis_data['subjects'].values())
        print(f"Всего анализов: {total_analyses}")
        
        return True
        
    except Exception as e:
        print(f"Ошибка сохранения анализа: {e}")
        return False

def find_matching_csv(csv_files, subject_code, analysis_index):
    """
    Находит CSV файл, соответствующий предмету и индексу анализа
    """
    for csv_file in csv_files:
        if csv_file.startswith(f"{subject_code}_{analysis_index}_"):
            return csv_file
    return None

def create_instruction_file(directory, file_count, analysis_name):
    """
    Создает файл с инструкцией
    """
    instruction_path = os.path.join(directory, "ИНСТРУКЦИЯ.txt")
    
    instructions = f"""ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ ВОССТАНОВЛЕННЫХ ДАННЫХ

Восстановлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
Количество файлов: {file_count}
Имя анализа: {analysis_name}

СТРУКТУРА ПАПКИ:
├── data/              - папка с CSV файлами измерений (правильный формат)
├── {analysis_name}.analysis - файл анализа для загрузки в программу
└── ИНСТРУКЦИЯ.txt    - этот файл

ФОРМАТ ДАННЫХ:
- CSV файлы сохранены в формате: CH1_Время, CH1_Амплитуда, CH2_Время, CH2_Амплитуда
- Имена CSV файлов содержат временные метки из оригинальных измерений
- Файл анализа содержит правильную структуру Channel с колонками 'Время' и 'Амплитуда'

КАК ЗАГРУЗИТЬ ДАННЫЕ В ПРОГРАММУ:

1. Откройте программу "Анализатор каналов осциллографа"
2. В главном меню выберите "Загрузить анализ"
3. Укажите путь к файлу: {os.path.basename(directory)}/{analysis_name}.analysis
4. Программа загрузит все восстановленные измерения

ОСОБЕННОСТИ:
- Все измерения будут размещены в соответствующих предметах (AN1, AN2, etc.)
- Структура каналов полностью соответствует оригинальному формату
- Параметры измерений восстановлены из оригинальных данных
- Временные метки в именах файлов соответствуют оригинальным измерениям

При возникновении проблем:
1. Убедитесь, что файл {analysis_name}.analysis не поврежден
2. Проверьте, что папка data содержит все CSV файлы
"""
    
    with open(instruction_path, 'w', encoding='utf-8') as f:
        f.write(instructions)
    
    print(f"Файл инструкции создан: {instruction_path}")

def restore_from_directory(analysis_dir, output_dir):
    """
    Восстанавливает все файлы анализа из указанной папки
    """
    if not os.path.exists(analysis_dir):
        print(f"Папка с анализами не найдена: {analysis_dir}")
        return False
    
    # Ищем все файлы анализа в папке
    analysis_files = []
    for file in os.listdir(analysis_dir):
        if file.endswith('.analysis'):
            analysis_files.append(os.path.join(analysis_dir, file))
    
    if not analysis_files:
        print(f"Файлы анализа не найдены в папке: {analysis_dir}")
        return False
    
    print(f"Найдено файлов анализа: {len(analysis_files)}")
    
    success_count = 0
    for analysis_file in analysis_files:
        print(f"\n--- Обработка файла: {os.path.basename(analysis_file)} ---")
        if restore_complete_analysis_fixed(analysis_file, output_dir):
            success_count += 1
    
    print(f"\n=== ИТОГИ ВОССТАНОВЛЕНИЯ ===")
    print(f"Успешно восстановлено: {success_count}/{len(analysis_files)}")
    
    return success_count > 0

def main():
    """
    Основная функция восстановления
    """
    # Папки для поиска файлов анализа
    search_dirs = [
        os.path.dirname(__file__),
        os.path.join(os.path.dirname(__file__), 'emergency_backups'),
        os.path.join(os.path.dirname(__file__), '..', 'emergency_backups')
    ]
    
    # Папка для восстановленных данных
    output_dir = os.path.join(os.path.dirname(__file__), 'restored_data')
    os.makedirs(output_dir, exist_ok=True)
    
    print("=== ПОЛНОЕ ВОССТАНОВЛЕНИЕ ДАННЫХ (ИСПРАВЛЕННОЕ) ===")
    print("Восстановление с правильной структурой Channel\n")
    
    # Вариант 1: Восстановление из конкретной папки с анализами
    analysis_directory = input("Введите путь к папке с файлами анализа (или Enter для автоматического поиска): ").strip()
    
    if analysis_directory and os.path.isdir(analysis_directory):
        # Восстанавливаем из указанной папки
        success = restore_from_directory(analysis_directory, output_dir)
    else:
        # Вариант 2: Автоматический поиск файлов анализа
        print("Автоматический поиск файлов анализа...")
        found_files = []
        for search_dir in search_dirs:
            if os.path.exists(search_dir):
                for file in os.listdir(search_dir):
                    if file.endswith('.analysis'):
                        found_files.append(os.path.join(search_dir, file))
                        print(f"Найден файл анализа: {os.path.join(search_dir, file)}")
        
        if not found_files:
            print("Файлы анализа не найдены!")
            return
        
        # Обрабатываем все найденные файлы
        success_count = 0
        for analysis_file in found_files:
            print(f"\n--- Обработка файла: {os.path.basename(analysis_file)} ---")
            if restore_complete_analysis_fixed(analysis_file, output_dir):
                success_count += 1
        
        success = success_count > 0
        print(f"\nУспешно восстановлено: {success_count}/{len(found_files)}")
    
    if success:
        print("\n✅ Восстановление успешно завершено!")
        print(f"Восстановленные данные находятся в: {output_dir}")
        print("Теперь вы можете загрузить восстановленные данные в программу.")
    else:
        print("\n❌ Восстановление не удалось!")

if __name__ == "__main__":
    main()