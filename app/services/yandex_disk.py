import os
import requests

YADISK_API_URL = "https://cloud-api.yandex.net/v1/disk"
YADISK_TOKEN = os.getenv("YANDEX_DISK_TOKEN")  # храним токен в .env

HEADERS = {
    "Authorization": f"OAuth {YADISK_TOKEN}"
}

def create_folder(folder_name: str) -> str:
    """Создаёт папку на Яндекс.Диске и возвращает путь"""
    url = f"{YADISK_API_URL}/resources"
    params = {"path": f"app:/{folder_name}"}
    resp = requests.put(url, headers=HEADERS, params=params)
    if resp.status_code not in (201, 409):  # 201 — создано, 409 — уже существует
        raise Exception(f"Ошибка создания папки: {resp.status_code} {resp.text}")
    return folder_name

def upload_file(folder_path: str, local_path: str, filename: str) -> None:
    """Загружает файл в указанную папку на Яндекс.Диске"""
    upload_url = f"{YADISK_API_URL}/resources/upload"
    params = {"path": f"app:/{folder_path}/{filename}", "overwrite": "true"}
    resp = requests.get(upload_url, headers=HEADERS, params=params)
    resp.raise_for_status()
    href = resp.json()["href"]

    with open(local_path, "rb") as f:
        upload_resp = requests.put(href, files={"file": f})
        upload_resp.raise_for_status()

def get_public_link(folder_path: str) -> str:
    """Делает папку публичной и возвращает ссылку"""
    url = f"{YADISK_API_URL}/resources/publish"
    params = {"path": f"app:/{folder_path}"}
    resp = requests.put(url, headers=HEADERS, params=params)
    resp.raise_for_status()

    # Получаем публичную ссылку
    meta_url = f"{YADISK_API_URL}/resources"
    resp_meta = requests.get(meta_url, headers=HEADERS, params={"path": f"app:/{folder_path}"})
    resp_meta.raise_for_status()
    return resp_meta.json().get("public_url")