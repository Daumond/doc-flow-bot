# В следующем шаге добавим методы: create_folder, upload_file, make_public
class YandexDiskClient:
    def __init__(self, token: str):
        self.token = token

    async def create_folder(self, remote_path: str) -> None: ...

    async def upload_file(self, local_path: str, remote_path: str) -> None: ...

    async def publish(self, remote_path: str) -> str: ...  # вернуть публичный URL