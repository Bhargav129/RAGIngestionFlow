import json


class FileOperationRepo(object):

    def __init__(self, file_name):
        self.file_name = file_name

    def file_reader(self, mode):
        with open(self.file_name, mode) as fr:
            return json.load(fr)


    def file_writer(self, mode, data):
        with open(self.file_name, mode) as fw:
            json.dump(data, fw, indent=4)