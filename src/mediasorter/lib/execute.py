import os.path
import shutil
import subprocess
from subprocess import DEVNULL

from loguru import logger

from mediasorter.lib.config import Action


class ExecutionError(Exception):
    pass


class Executable:

    @classmethod
    def from_action_type(cls, action: Action):
        if action == "copy":
            return Copy()
        if action == "move":
            return Move()
        if action == "symlink":
            return RunSubprocess('ln', '-s', stdout=DEVNULL, stderr=DEVNULL)
        if action == "hardlink":
            return RunSubprocess('ln', stdout=DEVNULL, stderr=DEVNULL)
        raise NotImplementedError(f"Action executor '{action}' not implemented")

    def _commit(self, source, destination):
        pass

    def __str__(self) -> str:
        return f"{__class__.__name__}"

    def commit(self, source, destination):
        logger.info(f"[{self}: sorting: {source} -> {destination}")
        try:
            # Sanity check
            if not os.path.exists(source):
                raise FileNotFoundError(f"File not found '{source}'")

            # Create parent dir(s)
            parent_dir = os.path.dirname(destination)
            if not os.path.isdir(parent_dir):
                logger.info(f"Creating target directory '{parent_dir}'")
                os.makedirs(parent_dir)

            # Let's go
            return self._commit(source, destination)
        except Exception as e:
            raise ExecutionError(e)


class RunSubprocess(Executable):
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def __str__(self) -> str:
        return f"{super}(args={self.args})"

    def _commit(self, source, destination):
        args = self.args + (source, destination)
        output = subprocess.run(args, **self.kwargs)
        if output.returncode != 0:
            raise ExecutionError(f"'{args}' subprocess failed. {output.stdout=}, {output.stderr=}")


class Copy(Executable):
    def _commit(self, source, target):
        return shutil.copy(source, target)


class Move(Executable):
    def _commit(self, source, target):
        return shutil.move(source, target)