import logging
from os import listdir, makedirs
from os.path import join, exists

from benchmark.utils.io import copy_tree, remove_tree
from benchmark.utils.shell import Shell


class ProjectCheckout:
    def __init__(self, url: str, base_path: str, name: str):
        self._logger = logging.getLogger("checkout.project")
        self.url = url
        self.base_path = base_path
        self.name = name
        self.checkout_dir = join(self.base_path, name, "checkout")

    def exists(self) -> bool:
        raise NotImplementedError

    def create(self) -> None:
        raise NotImplementedError

    def delete(self) -> None:
        raise NotImplementedError


class LocalProjectCheckout(ProjectCheckout):
    def exists(self):
        return exists(self.checkout_dir) and listdir(self.checkout_dir)

    def create(self):
        if not exists(self.checkout_dir):
            self._logger.debug("Create checkout directory %s", self.checkout_dir)
            makedirs(self.checkout_dir)
        if not listdir(self.checkout_dir):
            self._logger.debug("Copy from %s", self.url)
            copy_tree(self.url, self.checkout_dir)

    def delete(self):
        self._logger.debug("Delete %s", self.checkout_dir)
        remove_tree(self.checkout_dir)

    def __str__(self):
        return "synthetic:{}".format(self.url)


class RepoProjectCheckout(ProjectCheckout):
    def __init__(self, url: str, base_path: str, name: str, version: str, revision: str):
        super(RepoProjectCheckout, self).__init__(url, base_path, name)
        self.version = version
        self.revision = revision
        self.__base_checkout_dir = self.checkout_dir
        self.__child = LocalProjectCheckout(self.checkout_dir, join(self.base_path, self.name), self.version)
        self.checkout_dir = self.__child.checkout_dir

    def exists(self):
        return self.__child.exists() and self._is_repo(self.checkout_dir)

    def create(self):
        if not self._is_repo(self.__base_checkout_dir):
            self._logger.debug("Create base checkout directory %s", self.__base_checkout_dir)
            makedirs(self.__base_checkout_dir, exist_ok=True)
            self._logger.debug("Clone from %s", self)
            self._clone(self.url, self.revision, self.__base_checkout_dir)

        if not self._is_repo(self.__child.checkout_dir):
            self.__child.create()
            self._logger.debug("Update to revision %s", self.revision)
            self._update(self.url, self.revision, self.__child.checkout_dir)

    def delete(self):
        self._logger.debug("Delete %s", self.__base_checkout_dir)
        remove_tree(self.__base_checkout_dir)
        self.__child.delete()

    def _clone(self, url: str, revision: str, path: str):
        raise NotImplementedError

    def _update(self, url: str, revision: str, path: str):
        raise NotImplementedError

    def _is_repo(self, path: str) -> bool:
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError


class GitProjectCheckout(RepoProjectCheckout):
    def _clone(self, url: str, revision: str, path: str):
        Shell.exec("git clone {} . --quiet".format(url), cwd=path, logger=self._logger)

    def _update(self, url: str, revision: str, path: str):
        Shell.exec("git checkout {} --quiet".format(revision), cwd=path, logger=self._logger)

    def _is_repo(self, path: str):
        return exists(path) and Shell.try_exec("git status", cwd=path, logger=self._logger)

    def __str__(self):
        return "git:{}#{}".format(self.url, self.revision[:8])


class SVNProjectCheckout(RepoProjectCheckout):
    def _clone(self, url: str, revision: str, path: str):
        Shell.exec("svn checkout {}@{} .".format(url, revision), cwd=path)

    def _update(self, url: str, revision: str, path: str):
        Shell.exec("svn update -r {}".format(revision), cwd=path)

    def _is_repo(self, path: str):
        return exists(path) and Shell.try_exec("svn info", cwd=path)

    def __str__(self):
        return "svn:{}@{}".format(self.url, self.revision)