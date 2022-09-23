import json
import os
from os import walk, path
from urllib.parse import parse_qs
import datetime
import pwd
import grp
import hashlib
import traceback


def application(env, start_response):
    post_data_provided = False
    tree_json = ''
    cur_dir = ''
    level_str = ''
    try:
        # get post data; https://wsgi.tutorial.codepoint.net/parsing-the-request-post
        # the environment variable CONTENT_LENGTH may be empty or missing
        try:
            request_body_size = int(env.get('CONTENT_LENGTH', 0))
        except (ValueError):
            request_body_size = 0

        # When the method is POST the variable will be sent
        # in the HTTP request body which is passed by the WSGI server
        # in the file like wsgi.input environment variable.
        request_body = env['wsgi.input'].read(request_body_size)
        post = parse_qs(request_body.decode(), True)
        cur_dir = post.get('dir', [''])[0]
        level_str = post.get('level', [''])[0]
        secret_word = post.get('sec_word', [''])[0]

        # set a flag that parameters were send through the POST method
        if len(secret_word) > 0:
            post_data_provided = True

        # get query string and its values
        qs = parse_qs(env['QUERY_STRING'])
        cur_dir = cur_dir if len(cur_dir) > 0 else qs.get('dir', [''])[0]
        level_str = level_str if len(level_str) > 0 else qs.get('level', [''])[0]
        secret_word = secret_word if len(secret_word) > 0 else qs.get('sec_word', [''])[0]
        # secret_word = qs.get('sec_word', [''])[0]

        # tree_json += 'env -->"{}"<br/>'.format(env)
        # tree_json += 'request_body -->"{}"<br/>'.format(request_body)
        # tree_json += 'query string -->"{}"<br/>'.format(qs)
        # tree_json += 'post -->"{}"<br/>'.format(post)
        # tree_json += 'cur_dir -->"{}"<br/>'.format(cur_dir)
        # tree_json += 'level_str -->"{}"<br/>'.format(level_str)
        # tree_json += 'secret_word -->"{}"<br/>'.format(secret_word)

        # x = 2/0  # row to test the error

        level = 1  # default shows one level only; -1 will show all available levels
        if level_str.isdigit():
            level = int(level_str)
        # tree_json += 'level -->"{}"<br/>'.format(level)

        expected_password = get_password()
        # tree_json += 'expected_password -->"{}"<br/>'.format(expected_password)

        if str(secret_word) == str(expected_password):
            resp_dict = tree_to_json(cur_dir, level)
            # tree_json += json.dumps(resp_dict)
            # start_response(resp_dict['status'], [('Content-Type', 'text/html')])
            # return [tree_json.encode('utf-8')]
        else:
            # prepare dictionary for response
            resp_dict = {
                'path': cur_dir,
                'level': level,
                'status': '403',
                'message': 'Access to the site is unauthorized.',
                'tree': '',
            }
        tree_json += json.dumps(resp_dict)
        resp_status = resp_dict['status'] + (' OK' if resp_dict['status'] == '200' else ' Error')
        start_response(resp_status, [('Content-Type', 'text/html')])
        return [tree_json.encode('utf-8')]

    except Exception as ex:
        # report unexpected error
        if post_data_provided:
            # if post data provided, return detailed error description back to caller
            _str = 'Unexpected Error "{}" occurred during processing the latest POST request: \n{} ' \
                .format(ex, traceback.format_exc())
            resp_dict = {
                'path': cur_dir,
                'level': level_str,
                'status': '500',
                'message': _str,
                'tree': '',
            }
            tree_json += json.dumps(resp_dict)
            start_response('500 Error', [('Content-Type', 'text/html')])
            return [tree_json.encode('utf-8')]
        else:
            # if no POST data provided, return just a standard message
            start_response('500 Error', [('Content-Type', 'text/html')])
            return ['500 Internal Error has occurred'.encode('utf-8')]

def file_to_dict(fpath, node_id):
    # print('{} - {}'.format(node_id, path.basename(fpath)))
    try:
        grp_name = str(grp.getgrgid(os.stat(fpath).st_uid).gr_name)
    except Exception:
        grp_name = ''
    return {
        'name': path.basename(fpath),
        'node_id': node_id,
        'type': 'file',
        'path': fpath,
        'modified': str(modification_date(fpath)),
        'size': file_size(fpath),
        'owner': str(pwd.getpwuid(os.stat(fpath).st_uid).pw_name),
        'group': grp_name,
        }, node_id + 1

def folder_to_dict(rootpath, node_id):
    # print('{} - {}'.format(node_id, path.basename(rootpath)))
    return {
            'name': path.basename(rootpath),
            'node_id': node_id,
            'type': 'folder',
            'path': rootpath,
            'children': [],
            'read_permissions': os.access(rootpath, os.R_OK),  # read permissions of the current dir
            'modified': str(modification_date(rootpath)),
            'owner': str(pwd.getpwuid(os.stat(rootpath).st_uid).pw_name),
            'group': str(grp.getgrgid(os.stat(rootpath).st_gid).gr_name),
            }, node_id + 1

def tree_to_dict(rootpath, node_id: int, level: int = None):
    if level is None:
        level = -1
    if level == 0:
        return
    level = level - 1
    root_dict, node_id = folder_to_dict(rootpath, node_id)
    if level != 0:
        try:
            root, folders, files = next(walk(rootpath))  # .next()

            # root_dict['children'] = [file_to_dict(path.sep.join([root, fpath])) for fpath in files]
            # root_dict['children'] += [tree_to_dict(path.sep.join([root, folder]), level) for folder in folders]

            for folder in folders:
                fld_dict, node_id = tree_to_dict(path.sep.join([root, folder]), node_id, level)
                root_dict['children'].append(fld_dict)

            for fpath in files:
                fl_dict, node_id = file_to_dict(path.sep.join([root, fpath]), node_id)
                root_dict['children'].append(fl_dict)

        except Exception as ex:
            # error will be produced if there are no read permissions for the current folder
            pass
    return root_dict, node_id

# https://stackoverflow.com/questions/24265971/filesytem-tree-to-json
def tree_to_json(rootdir, level: int = None):
    if level is None:
        level = -1

    node_id = 1

    # prepare dictionary for response
    resp_dict = {
        'path': rootdir,
        'level': level,
        'status': '',
        'message': '',
        'tree': '',
    }

    if os.path.exists(rootdir):
        root, folders, files = next(walk(rootdir))  # .next()

        root_dict = []
        # prepare dictionary to store structure of the path
        if level != 0:
            # root_dict, cur_node_id = [tree_to_dict(path.sep.join([root, folder]), level) for folder in folders]

            for folder in folders:
                fld_dict, node_id = tree_to_dict(path.sep.join([root, folder]), node_id, level)
                root_dict.append(fld_dict)
            # root_dict += [file_to_dict(path.sep.join([root, fpath])) for fpath in files]
            for fpath in files:
                fl_dict, node_id = file_to_dict(path.sep.join([root, fpath]), node_id)
                root_dict.append(fl_dict)
        # else:
        #     root_dict = []

        resp_dict['status'] = '200'
        resp_dict['tree'] = root_dict
    else:
        resp_dict['status'] = '510'
        resp_dict['message'] = 'Directory does not exists or not accessible.'
        # return 'Directory does not exists or not accessible.'

    return resp_dict

def modification_date(path):
    t = os.path.getmtime(path)
    return datetime.datetime.fromtimestamp(t)

def convert_bytes(num):
    # this function will convert bytes to MB.... GB... etc
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0

def file_size(file_path):
    # this function will return the file size
    if os.path.isfile(file_path):
        file_info = os.stat(file_path)
        return convert_bytes(file_info.st_size)

def get_password():
    basedir = path.abspath(path.dirname(__file__))
    cfg = ConfigData(os.path.join(basedir, '.config.json'))
    secret_word = cfg.get_item_by_key('SECRET_WORD')
    return hashlib.md5(str(secret_word).encode('utf-8')).hexdigest()

class ConfigData:
    def __init__(self, cfg_path = None, cfg_content_dict = None):
        self.loaded = False

        if cfg_path and self.file_exists(cfg_path):
            with open(cfg_path, 'r') as env_cfg_file:
                self.cfg = json.load (env_cfg_file)
            self.loaded = True
        else:
            if cfg_content_dict:
                self.cfg = cfg_content_dict
                self.loaded = True
            else:
                self.cfg = None

    def get_value(self, yaml_path, delim='/'):
        path_elems = yaml_path.split(delim)

        # loop through the path to get the required key
        val = self.cfg
        for el in path_elems:
            # make sure "val" is not None and continue checking if "el" is part of "val"
            if val and el in val:
                try:
                    val = val[el]
                except Exception:
                    val = None
                    break
            else:
                val = None

        return val

    def get_item_by_key(self, key_name):
        # return str(self.get_value(key_name))
        v = self.get_value(key_name)
        if v is not None:
            return str(self.get_value(key_name))
        else:
            return v

    def get_all_data(self):
        return self.cfg

    def file_exists(self, fn):
        try:
            with open(fn, "r"):
                return 1
        except IOError:
            return 0


if __name__ == '__main__':
    basedir = path.abspath(path.dirname(__file__))
    cfg = ConfigData(os.path.join(basedir, '.config.json'))
    # if cfg.loaded:
    #     print(cfg.get_item_by_key('SECRET_WORD'))
    # else:
    #     print ('No SECRET_WORD provided')
    print(tree_to_json('/home/stas/test_structure', level=3))
