import os, shutil, fnmatch

class FileOps:
    def find(self, root, pattern):
        matches = []
        for base, _, files in os.walk(root):
            for name in fnmatch.filter(files, pattern):
                matches.append(os.path.join(base,name))
        return matches

    def make_folder(self, path):
        os.makedirs(path, exist_ok=True)

    def rename(self, src, dst):
        os.rename(src, dst)

    def copy(self, src, dst):
        shutil.copy2(src, dst)

    def move(self, src, dst):
        shutil.move(src, dst)
