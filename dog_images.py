import requests
import json
import csv
import time
import os
from tqdm import tqdm

#Параметры для доступа к API
DOG_URL = r'https://dog.ceo/api/breed/'
YA_URL = r'https://cloud-api.yandex.net/v1/disk/resources'


#Функция для получения словаря для заголовков формируемого https запроса
def get_YA_DISK_headers(YA_TOKEN):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"OAuth {YA_TOKEN}"
    }
    return headers

#Функция для проверки существуют ли загружаемые файлы на Яндекс.Диске для исключения повторной отпарвки
def get_existing_files(breed):
    headers = get_YA_DISK_headers(YA_TOKEN)
    params = {
        "path": breed,
    }
    file_list = []
    try:
        response = requests.get(YA_URL, headers=headers, params = params)
        if response.status_code == 200:
            limit = response.json()['_embedded']['total']
            if limit > 0:
                params.update({'limit': limit})
                response = requests.get(YA_URL, headers=headers, params = params)
                file_info_list = response.json()['_embedded']['items']
                for file in file_info_list:
                    file_list.append(file['name'])
                return file_list, f"Получен список ранее загруженных файлов, всего в папке сейчас хранится {limit} файлов. Повторная загрузка ранее загруженных файлов не требуется."
            else:
                return True, f"Папка {breed} пока не содержит файлов"
        else:
            error_data = response.json()
            error_msg = error_data.get('message', 'Неизвестная ошибка')
            error_desc = error_data.get('description', 'Нет дополнительной информации')
            return False, f"Ошибка {response.status_code}: {error_msg}\nДетали: {error_desc}"
    except requests.exceptions.RequestException as exc:
        return False, f"Сетевая ошибка при проверке существующих файлов: {str(exc)}"

#Функция для создания папки на Яндекс.Диске
def create_folder(breed):
    headers = get_YA_DISK_headers(YA_TOKEN)
    params = {
        "path": breed,
    }
    try:
        response = requests.put(YA_URL, headers=headers, params=params)
        if response.status_code == 201:
            return True, f"Папка '{breed}' успешно создана на Яндекс.Диске"
        elif response.status_code == 409:
            return True, f"Папка '{breed}' уже существует на Яндекс.Диске. Повторное создание не требуется."
        else:
            error_data = response.json()
            error_msg = error_data.get('message', 'Неизвестная ошибка')
            error_desc = error_data.get('description', 'Нет дополнительной информации')
            return False, f"Ошибка {response.status_code}: {error_msg}\nДетали: {error_desc}"
    except requests.exceptions.RequestException as exc:
        return False, f"Сетевая ошибка при создании папки: {str(exc)}"

#Функция получения всех подпород заданной породы
def get_sub_breed_list(breed):   
    try:
        response = requests.get(f"{DOG_URL}{breed}/list")
        if response.status_code != 200:
            return False, f"Порода собак '{breed}' отсутвует в справочнике ресурса {DOG_URL}"
        else:
            sub_breed_list = response.json()['message']
            sub_breed_list.append(breed)
            return sub_breed_list, f"Получен список всех подпород заданной породы. Всего {len(sub_breed_list)-1} подпороды"
    except requests.exceptions.RequestException as exc:
        return False, f"Сетевая ошибка при получении списка подпород породы: {str(exc)}"

#Функция получения изображений породы и всех ее подпород
def get_images_by_breed(breed):
    sub_breed_list, sub_breed_list_message = get_sub_breed_list(breed)
    if not sub_breed_list:
        return sub_breed_list_message
    print(sub_breed_list_message)
    images_list = []
    try:
        for sub_breed in sub_breed_list:
            if sub_breed == breed:
                response = requests.get(f"{DOG_URL}{sub_breed}/images")
            else:
                response = requests.get(f"{DOG_URL}{breed}/{sub_breed}/images")
            if response.status_code != 200:
                return False, f"Порода собак '{sub_breed}' отсутвует в справочнике ресурса {DOG_URL}"
            else:
                images_list += response.json()['message']       
        return images_list, f"Получен список всех изображений породы, включая все ее подпороды. Всего {len(images_list)} изображений"
    except requests.exceptions.RequestException as exc:
        return False, f"Сетевая ошибка при получении изображений породы: {str(exc)}"

#Функция для загрузки файлов с ресурса https://dog.ceo/api/breed/ на Яндекс.Диск
def upload_images_to_YA_DISK(breed):
    en_breed = breed.lower().strip()
    
    #Получаем список изображений всех подпород выбранной породы
    sub_breed_images_list, dog_message = get_images_by_breed(breed)
    if not sub_breed_images_list:
        return dog_message
    print(dog_message)
    total_image_count = len(sub_breed_images_list)

    #Создаем папку на Яндекс.Диске с наименованием породы
    folder, folder_message = create_folder(en_breed)

    if not folder:
        return folder_message
    print(folder_message)

    current_date = time.strftime("%d.%m.%Y", time.localtime())
    current_time = time.strftime("%H:%M:S", time.localtime())
    upload_list = []
    count = 0
    errors = [['Дата', 'Наименование файла', 'Описание ошибки']]
    existing_files_count = 0
    
    existing_files, existing_files_message = get_existing_files(en_breed)
    if not existing_files:
        return existing_files_message
    print(existing_files_message)
    
    # Главный прогресс-бар
    with tqdm(total=total_image_count, desc=f"Статистика загрузки изображений({breed})", unit="файл", position=0) as progress_bar_total:
        for image in sub_breed_images_list:
            
            file_name = f"{en_breed}_{image.split('/')[-1]}"

            #Пропускаем ранее загруженные файлы
            if type(existing_files) == list and file_name in existing_files:
                #print(f"Файл {file_name} был загружен на Яндекс.Диск ранее. Повторная загрузка не требуется")
                existing_files_count += 1
                upload_list.append({'file_name': file_name})
                progress_bar_total.write(f"Пропущен: {file_name} (уже существует)")
                progress_bar_total.update(1)
                continue
            
            path = f"{en_breed}/{file_name}"
            headers = get_YA_DISK_headers(YA_TOKEN)
            params = {
                'path': path,
                'url': image
            }
            try:
                upload_response = requests.post(f"{YA_URL}/upload", headers=headers, params=params, stream=True)
                upload_response.raise_for_status()

                #Проверяем статус асинхронной отправки изображения 
                operation_status_check = requests.get(upload_response.json()['href'], headers=headers).status_code
                if operation_status_check == 200:
                    count += 1
                    upload_list.append({'file_name': file_name})  
                    progress_bar_total.write(f"Успешно загружен: {file_name}")
                    progress_bar_total.update(1)
                else:
                    raise Exception(f"HTTP {operation_status_check.status_code}")
            except Exception as exc:
                    error_msg = [f"{current_date} {current_time}", file_name, str(exc)]
                    errors.append(error_msg)
                    progress_bar_total.write(f"Ошибка загрузки: {file_name}")

    # Сохраняем список загруженных изображений в json файл
    if upload_list:
        path_json_file = os.path.join(os.getcwd(), 'uploaded_files.json')
        with open(path_json_file, 'w', encoding='utf-8') as f:
            json.dump(upload_list,f, indent=2)

    # Сохраняем список файлов, по которым возникла ошибка
    csv.register_dialect("csv_for_excel", delimiter=";", quoting=csv.QUOTE_NONE, escapechar="\\")
    if len(errors) > 1:
        path_error_file = os.path.join(os.getcwd(), 'error_logs', f'error_file_{current_date}.csv')
        if os.path.isfile(path_error_file):
            with open(path_error_file, 'a', encoding='utf-8', newline="") as error_file:   
                writer = csv.writer(error_file, dialect='csv_for_excel')
                writer.writerows(errors[1:])
        else:
             with open(path_error_file, 'w', encoding='utf-8', newline="") as error_file:   
                writer = csv.writer(error_file, dialect='csv_for_excel')
                writer.writerows(errors)     
            
    # Выводим сообщение со статистикой загрузки пользователю
    result = [
        f"\nРезультат обработки:",
        f"Порода: {breed}",
        f"Всего изображений: {total_image_count}. Список загруженных изображений: {f.name}",
        f"Успешно загружены: {count}",
        f"Загружены ранее: {existing_files_count}",
    ]
    if len(errors) >  1:
        result.insert(-1, f"Ошибки: {len(errors)-1}. Просмотреть ошибки: {error_file.name}") 
    return '\n'.join(result)
    

breed = input('Полный список пород доступен по адресу: https://dog.ceo/dog-api/breeds-list. Введите наименование породы собак на английском языке, например, african: ')

YA_TOKEN = input('Введите значение OAuth-токена, полученного для работы с API Яндекс.Диска: ')

result = upload_images_to_YA_DISK(breed)
print(result)

