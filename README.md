# Использование сборщика модулей

```gitexclude
path = tools/build
url = git@github.com:azahalski/awz.bxbuild.tools.git
```
```
cd build
```
файл конфигурации сборки модуля:
```../bxbuildtools.json```

## 1. Добавить коммит с изменениями
## 2. Копирование изменений в архив сборки
```shell 
python checkup.py
```
## 3. Изменить .description.php обновления
## 4. Сборка архива обновлений
```shell 
python updater.py
```
## 5. Сборка cp1251 версии
```shell 
python cp1251.py
```
## 6. Добавление истории версий
```shell 
python cl.py
```
## 7. Коммитим все изменения
## 8. Создание контрольной точки
```shell 
python lhash.py
```