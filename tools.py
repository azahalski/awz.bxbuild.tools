from chardet.universaldetector import UniversalDetector
import os
import shutil
import zipfile
import tempfile
import re
import json
import subprocess
import requests


def add_zip(arch, add_folder, mode, root_zip_folder=''):
    z = zipfile.ZipFile(arch, mode, zipfile.ZIP_DEFLATED, True)
    for root, dirs, files in os.walk(add_folder):
        for file in files:
            # Создание относительных путей и запись файлов в архив
            path = os.path.join(root, file)
            len_rm = len(add_folder)
            z.write(path, root_zip_folder+path[len_rm:])
    z.close()
    print('created zip', arch)


def encode_bx(filename, encoding_from='utf-8', encoding_to='windows-1251', original_file=''):
    with open(filename, 'r', encoding=encoding_from) as fr:
        with open(filename+'.tmp', 'w', encoding=encoding_to) as fw:
            for line in fr:
                fw.write(line)
    shutil.copyfile(filename+'.tmp', filename)
    os.remove(filename+'.tmp')
    print('converting ', original_file, 'from', encoding_from, 'to', encoding_to)


def check_encoding(file_path):
    detector = UniversalDetector()
    with open(file_path, 'rb') as fh:
        for line in fh:
            detector.feed(line)
            if detector.done:
                break
        detector.close()
    return {'charset': detector.result['encoding'], 'path': file_path}


def get_files(file_path, copy_dir):
    for name in os.listdir(file_path):
        if not os.path.isdir(os.path.join(file_path,name)):
            shutil.copyfile(os.path.join(file_path,name), os.path.join(copy_dir,name))
            if os.path.join('lang','ru') in os.path.join(file_path,name) or 'description.ru' in name:
                res = check_encoding(os.path.join(copy_dir,name))
                if res['charset'] != 'utf-8':
                    raise Exception('incorrect charset: '+res['charset']+' from file '+res['path'])
                else:
                    encode_bx(os.path.join(copy_dir,name), original_file=os.path.join(file_path,name))
        else:
            if not os.path.isdir(os.path.join(copy_dir,name)):
                os.mkdir(os.path.join(copy_dir,name))
            get_files(os.path.join(file_path,name), os.path.join(copy_dir,name))


def build_main(module_path, zip_name, folder=".last_version/"):
    version = get_module_version(module_path)
    if not version:
        raise Exception('is bitrix module? path: '+module_path)
    print('creating ', zip_name, 'module version', version)
    tmp_dir = tempfile.mkdtemp()
    get_files(module_path, tmp_dir)
    add_zip(zip_name, tmp_dir, "w", folder)
    shutil.rmtree(tmp_dir)


def get_module_version(module_path, encoding_file='utf-8'):
    version = False
    version_file = os.path.join(module_path, 'install/version.php')
    if not os.path.isfile(version_file):
        return version
    with open(version_file, 'r', encoding=encoding_file) as fv:
        for line in fv:
            if 'VERSION' in line and not 'VERSION_DATE' in line:
                try:
                    ob_re = re.search(re.compile("([0-9.]+)"), line)
                    version = ob_re.group(1)
                    if len(version) < 3:
                        version = False
                except Exception as e:
                    print(e)
                    version = False
    return version


def get_config():
    conf_file = 'bxbuildtools.json'
    full_path = os.path.join('../', conf_file)
    if os.path.exists(full_path):
        with open(full_path, 'r') as file:
            json_data = json.load(file)
            require_key = [
                'module_path',
                'updates_path',
                'output_path',
                'lang_prefix',
                'git_path'
            ]
            for key in require_key:
                if not (key in json_data):
                    raise Exception(key+" is required key in "+conf_file)
            return json_data
    return False


def get_hashes(updates_path):
    mark_path = os.path.join(updates_path, 'marked_hashes.json')
    json_data = {}
    if os.path.exists(mark_path):
        with open(mark_path, 'r') as file:
            json_data = json.load(file)
    return json_data


def get_changed(updates_path, prepare_version):
    hashes_data = get_hashes(updates_path)
    conf = get_config()
    git_path = os.path.abspath(conf['git_path'])
    if prepare_version in hashes_data:
        command = 'git diff --name-only '+hashes_data[prepare_version]
        run = subprocess.run(command, capture_output=True, cwd=git_path)
        return [str(path) for path in run.stdout.decode().strip().split("\n")]
    else:
        return []


def set_last_hash():
    """
    запись хеша контрольной точки текущей версии
    для последующей проверки изменений файлов при билде следующей версии
    """
    conf = get_config()
    git_path = os.path.abspath(conf['git_path'])
    updates_path = os.path.abspath(conf['updates_path'])
    mark_path = os.path.join(updates_path, 'marked_hashes.json')
    module_path = os.path.abspath(conf['module_path'])
    version = get_module_version(module_path)
    json_data = {}
    if os.path.exists(mark_path):
        with open(mark_path, 'r') as file:
            json_data = json.load(file)
    command = 'git rev-parse HEAD'
    run = subprocess.run(command, capture_output=True, cwd=git_path)
    json_start = json_data.copy()
    json_data[version] = run.stdout.decode().strip()
    with open(mark_path, "w") as outfile:
        json.dump(json_data, outfile)
    if version in json_start:
        if json_start[version] == json_data[version]:
            print("hash", json_data[version], "for version", version, "not updated", sep=" ")
        else:
            print("update hash", json_data[version], "for version", version, sep=" ")
    else:
        print("new hash", json_data[version], "for version", version, sep=" ")


def split_path(path, dirs=()):
    if path == '':
        return dirs
    temp_dir = os.path.split(path)
    if len(temp_dir) == 1:
        return dirs
    elif temp_dir[1] == '':
        return (temp_dir[0],)+dirs
    return split_path(temp_dir[0], temp_dir[1:]+dirs)


def parse_success_text(tx):
    regex_ok = re.compile(r'<span\sclass=(?:"|\')text-success(?:"|\')>([^<]+\s(?:<strong>)[^<]+(?:</strong>)\s[^<]+|[^<]+)</span>')
    t_ok = re.findall(regex_ok, tx)
    t_ok_text = ''
    if len(t_ok):
        t_ok_text = t_ok[0]
        t_ok_text = t_ok_text.replace('<strong>', '')
        t_ok_text = t_ok_text.replace('</strong>', '')
    return t_ok_text


def send_update(options):
    url_start = 'https://partners.1c-bitrix.ru/personal/modules/edit.php'
    url = 'https://partners.1c-bitrix.ru/personal/modules/deploy.php'
    url_ver = 'https://partners.1c-bitrix.ru/personal/modules/update.php'
    conf = get_config()
    module_id = conf['module_path'].replace('../bitrix/modules/','')[0:-1]
    url_start += '?ID='+module_id
    url += '?ID='+module_id

    if 'user' in options:
        auth_data = {"login":options["user"], "password": options["password"]}
    elif not 'market_auth' in conf:
        raise Exception('auth data for marketplace not found')
    elif os.path.exists(conf['market_auth']):
        with open(conf['market_auth'], 'r') as file:
            auth_data = json.load(file)

    session = requests.Session()
    resp = session.get(url_start, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.143 Safari/537.36'
    })

    authFormData = {
        'AUTH_FORM': 'Y',
        'TYPE': 'AUTH',
        'USER_LOGIN': auth_data['login'],
        'USER_PASSWORD': auth_data['password'],
        'USER_REMEMBER': 'Y',
        'Login': 'Войти'
    }

    #авторизация
    request = session.post(url_start, authFormData)
    module_page = request.text
    sess_id = re.match(r'.*id="sessid"\svalue="([0-9a-z]+)".*', module_page.replace("\n",""))
    #print(sess_id)

    #архивы сборки
    last_version = get_module_version(conf['module_path'])
    if not last_version:
        raise Exception('not updated version')
    arch_path = os.path.join(conf['output_path'], 'update', last_version+'.zip')
    arch_path_full = os.path.join(conf['output_path'], '.last_version.zip')
    if not os.path.isfile(arch_path):
        raise Exception('not updated version')

    #подготовка запроса на добавление версии
    updater_data = {
        'sessid': sess_id.group(1),
        'ID': module_id,
        'submit': 'Загрузить'
    }
    files = {
        'update': (last_version + '.zip', open(arch_path, "rb"))
    }
    #запрос на добавление версии
    try:
        r = session.post(url, updater_data, files=files)
        t_ok_text = parse_success_text(r.text)
        print('send', url, t_ok_text)
    except Exception as e:
        raise Exception('upload version error')

    #подготовка обновления архива модуля
    updater_data_ver = {
        'sessid': sess_id.group(1),
        'ID': module_id,
        last_version: 'stable',
        'submit': 'Загрузить'
    }
    session.post(url_ver, updater_data_ver)

    fields = {
        "sessid":sess_id.group(1),
        "ID":module_id,
        "edit_module":"Y",
        "apply":"Y"
    }
    #сбор полей редактора
    jsFields = ['descriptionRU', 'INSTALLRU', 'SUPPORTRU', 'EULA_LINK']
    field = None
    regex = r"(?:(?:var config.*)(descriptionRU)(?:.*?;$)(?:\W*\w*\W\w* = ')(.*?(?=';)))|(?:(?:var config.*)(INSTALLRU)(?:.*?;$)(?:\W*\w*\W\w* = ')(.*?(?=';)))|(?:(?:var config.*)(SUPPORTRU)(?:.*?;$)(?:\W*\w*\W\w* = ')(.*?(?=';)))|(?:(?:var config.*)(EULA_LINK)(?:.*?;$)(?:\W*\w*\W\w* = ')(.*?(?=';)))"
    matches = re.finditer(regex, module_page, re.MULTILINE | re.IGNORECASE)
    for matchNum, match in enumerate(matches, start=1):
        for groupNum in range(0, len(match.groups())):
            groupNum = groupNum + 1
            group = match.group(groupNum)
            if group in jsFields:
                field = group
            elif field:
                fields[field] = re.sub(r'\\{1,}n', '\n', group)
                field = None

    module_page = " ".join(module_page.split())

    fields['licenses'] = re.findall(r'name="licenses\[\]"\svalue="([0-9A-Z]+)"\schecked', module_page)

    sel_fields = ('mtype','category')
    for _ in sel_fields:
        fields[_] = []
        regex1 = re.compile(r'name="' + _ + '\[\]".*?</select>')
        sel = re.findall(regex1, module_page)
        if len(sel):
            regex2 = re.compile(r'option\svalue="([^"]+)"\sselected')
            fields[_] = re.findall(regex2, sel[0])

    check_fields = ('active', 'publish', 'COMPATIBLE_PHP8', 'SITE24', 'COMPOSITE', 'ADAPT', 'PARTNER_DISCOUNT',
                    'freeModuleDemo', 'freeModule','USE_SUPPORT_DEFAULT_TEXT','DETAIL_DISCUSSIONS_OFF','YA_METRIKA')
    for _ in check_fields:
        fields[_] = ''
        regex = re.compile(r'name="' + _ + '"(?:\s(?:id|size)="[^"]+")?\svalue="([^"]+)"\schecked')
        _res = re.findall(regex, module_page)
        if len(_res):
            fields[_] = _res[0]

    inp_fields = ('openLineUrl', 'nameRU', 'PRICERU', 'trial_period', 'NEW_NAME_RU', 'LICENSE_NAME', 'NEW_LICENSE_NAME',
                  'MARKETING_NAME','DEMO_LINKRU','VIDEO_LINKRU','googleAnalytics','YA_METRIKA_COUNTER','P_SORT')
    for _ in inp_fields:
        fields[_] = ''
        regex = re.compile(r'name="' + _ + '"(?:\s(?:id|size)="[^"]+")?\svalue="([^"]+)"')
        _res = re.findall(regex, module_page)
        if len(_res):
            fields[_] = _res[0]

    files = {
        'update': ('.last_version.zip', open(arch_path_full, "rb"))
    }
    # запрос на обновление данных решения
    try:
        r = session.post(url_start, fields, files=files)
        t_ok_text = parse_success_text(r.text)
        print('send', url_start, t_ok_text)
    except Exception as e:
        raise Exception('upload module error')


def get_all_versions():
    conf = get_config()
    updates_path = os.path.abspath(conf['updates_path'])
    change_log = {'0001.0000.0000':[]}
    for name in os.listdir(updates_path):
        if name[-5:] == '.json':
            continue
        else:
            if os.path.isfile(os.path.join(updates_path, str(name), 'description.ru')):
                ver = str(name)
                ver_list = [f'{int(x):04}' for x in ver.split(".")]
                ver_key_str = '.'.join(ver_list)
                change_log[ver_key_str] = []
    sorted_change_log = dict(sorted(change_log.items()))
    cl = []
    for _ in sorted_change_log.keys():
        cl.append('.'.join(str(int(_2)) for _2 in _.split(".")))
    return cl

def add_description():
    conf = get_config()
    updates_path = os.path.abspath(conf['updates_path'])
    module_path = os.path.abspath(conf['module_path'])
    git_path = os.path.abspath(conf['git_path'])
    last_version = get_module_version(module_path)

    all_versions = get_all_versions()
    prepare_version = all_versions[len(all_versions) - 1]
    hashes_data = get_hashes(updates_path)

    new_version_path = os.path.abspath(os.path.join(updates_path, last_version))
    new_version_desc = os.path.join(new_version_path, 'description.ru')
    if not os.path.isfile(new_version_desc):
        with open(new_version_desc, "w", encoding='utf-8') as outfile:
            if prepare_version in hashes_data:
                command = 'git log --pretty=format:"%H:::%s"'
                run = subprocess.run(command, capture_output=True, cwd=git_path)
                rows = [str(path) for path in run.stdout.decode().strip().split("\n")]
                rows_print = []
                for row in rows:
                    row_ar = row.split(":::")
                    _row = row_ar[1]
                    if hashes_data[prepare_version] == row_ar[0]:
                        break
                    if _row[0] == '-' and len(_row)>10:
                        if _row[-1] == ';':
                            rows_print.append(_row[1:-1].strip())
                        elif row[-1] == '.':
                            rows_print.append(_row[1:-1].strip())
                        else:
                            rows_print.append(_row[1:].strip())
                if not len(rows_print):
                    rows_print.append('обновление '+str(last_version))
                for _ in rows_print:
                    sep = ";\n"
                    if rows_print[len(rows_print)-1] == _:
                        sep = "."
                    outfile.write('- '+_+sep)
            print("created file", "description.ru", rows_print)
    else:
        print(new_version_desc, "is exists")