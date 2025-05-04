import requests
import json

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
        'limit': 10000
    }
    file_list = []
    file_info_list = requests.get(YA_URL, headers=headers, params = params).json()['_embedded']['items']
    for file in file_info_list:
        file_list.append(file['name'])
    result = file_list 
    return result

#Функция для создания папки на Яндекс.Диске
def create_folder(breed):
    headers = get_YA_DISK_headers(YA_TOKEN)
    params = {
        "path": breed,
    }
    response = requests.put(YA_URL, headers=headers, params=params)
    if response.status_code == 201 or response.status_code == 409:
        result = True
    else:
        result = False
    return result

#Функция для загрузки файлов с ресурса https://dog.ceo/api/breed/ на Яндекс.Диск
def get_images_by_breed(breed):
    en_breed = breed.lower()
    
    #Получаем список изображений всех подпород выбранной породы
    dog_response = requests.get(f"{DOG_URL}{en_breed}/images")
    
    if dog_response.status_code != 200:
        return f"Порода собак '{en_breed}' отсутвует в справочнике ресурса {DOG_URL}"

    sub_breed_images_list = dog_response.json()['message']
    total_image_count = len(sub_breed_images_list)

    #Создаем папку на Яндекс.Диске с наименованием породы
    folder = create_folder(en_breed)

    if not folder:
        return f"При создании папки '{en_breed}' на Яндекс.Диске произошла ошибка."

    upload_list = []
    count = 0
    existing_files = get_existing_files(en_breed)
    errors = []
    for image in sub_breed_images_list:
        
        file_name = f"{en_breed}_{image.split('/')[-1]}"

        #Пропускаем ранее загруженные файлы
        if file_name in existing_files:
            print(f"Файл {file_name} был загружен на Яндекс.Диск ранее. Повторная загрузка не требуется")
            continue
        else:
            path = f"{en_breed}/{file_name}"
            headers = get_YA_DISK_headers(YA_TOKEN)
            params = {
                'path': path,
                'url': image
            }
            try:
                operation = requests.post(f"{YA_URL}/upload", headers=headers, params=params, stream=True).json()['href']

                #Проверяем статус асинхронной отправки изображения 
                operation_status_check = requests.get(operation, headers=headers).status_code
                if operation_status_check == 200:
                    count += 1
                    upload_list.append({'file_name': file_name})  
                    print(f"Файл {file_name} успешно загружен на Яндекс.Диск.")
                else:
                    raise Exception(f"HTTP {operation_status_check.status_code}")
            except Exception as exp:
                    error_msg = f"Ошибка: {file_name} ({str(exp)})"
                    errors.append(error_msg)

    #Сохраняем список загруженных изображений в json файл
    if upload_list:
        with open('uploaded_files.json', 'w', encoding='utf-8') as f:
            json.dump(upload_list,f, indent=2)

    # Выводим сообщение со статистикой загрузки пользователю
    result = [
        f"Порода: {breed}",
        f"Всего изображений: {total_image_count}",
        f"Успешно загружены: {count}",
        f"Загружены ранее: {len(existing_files)}",
        f"Ошибки: {len(errors)}"
    ]
        
    return '\n'.join(result)
    

breed = input('Введите наименование породы собак на английском языке: ')
YA_TOKEN = input('Введите значение OAuth-токена, полученного для работы с API Яндекс.Диска: ')

result = get_images_by_breed(breed)

print(result)
