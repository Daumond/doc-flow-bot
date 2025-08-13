from docx import Document
import shutil
import os

def fill_protocol(template_path: str, output_path: str, data: dict):
    """
    Заполняет шаблон Word, подставляя значения из data по маркерам {{ключ}}
    """
    # Копируем шаблон, чтобы не испортить оригинал
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    shutil.copy(template_path, output_path)

    doc = Document(output_path)

    def replace_text_in_paragraphs(paragraphs):
        for p in paragraphs:
            for key, value in data.items():
                marker = f"{{{{{key}}}}}"
                if marker in p.text:
                    inline = p.runs
                    for i in range(len(inline)):
                        if marker in inline[i].text:
                            inline[i].text = inline[i].text.replace(marker, str(value))

    # Заменяем в абзацах
    replace_text_in_paragraphs(doc.paragraphs)

    # Заменяем в таблицах
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                replace_text_in_paragraphs(cell.paragraphs)

    doc.save(output_path)