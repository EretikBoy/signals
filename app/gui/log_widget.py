from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QTextCursor
from PyQt6.QtCore import Qt

class LogWidget(QTextEdit):
    """Расширенный QTextEdit с поддержкой обновления строк"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.line_markers = {}  # Хранит позиции строк для обновления
    
    def append_with_id(self, message, line_id=None):
        """Добавляет сообщение с возможностью обновления по ID"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        if line_id and line_id in self.line_markers:
            # Обновляем существующую строку
            marker = self.line_markers[line_id]
            cursor.setPosition(marker['start'])
            cursor.setPosition(marker['end'], QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.insertText(message)
            
            # Обновляем маркер
            self.line_markers[line_id] = {
                'start': cursor.position() - len(message),
                'end': cursor.position()
            }
        else:
            # Добавляем новую строку
            if self.document().characterCount() > 1:
                cursor.insertText("\n")
            
            start_pos = cursor.position()
            cursor.insertText(message)
            end_pos = cursor.position()
            
            if line_id:
                self.line_markers[line_id] = {
                    'start': start_pos,
                    'end': end_pos
                }
        
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
    
    def update_line(self, line_id, message):
        """Обновляет строку по ID"""
        self.append_with_id(message, line_id)
    
    def append(self, message):
        """Переопределенный append без ID"""
        super().append(message)
    
    def clear_line(self, line_id):
        """Удаляет строку по ID"""
        if line_id in self.line_markers:
            cursor = self.textCursor()
            marker = self.line_markers[line_id]
            cursor.setPosition(marker['start'])
            cursor.setPosition(marker['end'], QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            del self.line_markers[line_id]
    
    def clear_all_markers(self):
        """Очищает все маркеры"""
        self.line_markers.clear()