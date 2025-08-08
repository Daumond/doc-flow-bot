# В следующем шаге добавим генерацию docx через docxtpl
class ProtocolGenerator:
    def __init__(self, template_path: str):
        self.template_path = template_path