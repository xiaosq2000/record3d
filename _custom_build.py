import distutils.cygwinccompiler
import os
import platform
import re
import subprocess
import sys

from setuptools import Extension
from setuptools.build_meta import *  # noqa: F403
from setuptools.command.build_ext import build_ext

# Fix for cygwin compiler
distutils.cygwinccompiler.get_msvcr = lambda: []


class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=""):
        super().__init__(name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class CMakeBuild(build_ext):
    def run(self):
        try:
            subprocess.check_output(["cmake", "--version"])
        except OSError:
            raise RuntimeError(
                "CMake must be installed to build the following extensions: "
                + ", ".join(e.name for e in self.extensions)
            )

        if platform.system() == "Windows":
            cmake_version = self._get_cmake_version()
            if cmake_version < (3, 13, 0):
                raise RuntimeError("CMake >= 3.13.0 is required on Windows")

        for ext in self.extensions:
            self.build_extension(ext)

    def _get_cmake_version(self):
        out = subprocess.check_output(["cmake", "--version"]).decode()
        version_match = re.search(r"version\s*([\d.]+)", out)
        if version_match:
            return tuple(map(int, version_match.group(1).split(".")))
        return (0, 0, 0)

    def build_extension(self, ext):
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
        cmake_args = [
            f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
            "-DBUILD_PYTHON_BINDINGS=ON",
        ]

        cfg = "Release"
        build_args = ["--config", cfg]

        if platform.system() == "Windows":
            cmake_args += [f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{cfg.upper()}={extdir}"]
            if sys.maxsize > 2**32:
                cmake_args += ["-A", "x64"]
            build_args += ["--", "/m"]
        else:
            cmake_args += [f"-DCMAKE_BUILD_TYPE={cfg}"]
            build_args += ["--", "-j4"]

        env = os.environ.copy()
        env["CXXFLAGS"] = (
            f'{env.get("CXXFLAGS", "")} -DVERSION_INFO=\\"{self.distribution.get_version()}\\"'
        )

        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)

        subprocess.check_call(["cmake", ext.sourcedir] + cmake_args, cwd=self.build_temp, env=env)
        subprocess.check_call(
            ["cmake", "--build", ".", "--target", "record3d"] + build_args, cwd=self.build_temp
        )


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    from setuptools.build_meta import build_wheel as _orig_build_wheel

    # We need to temporarily modify the setup configuration
    # Save the original setup.py content to use with our custom build
    return _orig_build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    from setuptools.build_meta import build_sdist as _orig_build_sdist

    return _orig_build_sdist(sdist_directory, config_settings)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    from setuptools.build_meta import build_editable as _orig_build_editable

    return _orig_build_editable(wheel_directory, config_settings, metadata_directory)


# We need to ensure the extension is built
__all__ = [
    "build_wheel",
    "build_sdist",
    "build_editable",
    "get_requires_for_build_wheel",  # noqa: F405
    "get_requires_for_build_sdist",  # noqa: F405
    "get_requires_for_build_editable",  # noqa: F405
    "prepare_metadata_for_build_wheel",  # noqa: F405
    "prepare_metadata_for_build_editable",  # noqa: F405
]


# Override the setup() call to inject our extension
_setup_called = False


def _override_setup():
    global _setup_called
    if _setup_called:
        return
    _setup_called = True

    import setuptools

    original_setup = setuptools.setup

    def custom_setup(**kwargs):
        # Inject our CMake extension
        kwargs["ext_modules"] = [CMakeExtension("record3d")]
        kwargs["cmdclass"] = {"build_ext": CMakeBuild}
        return original_setup(**kwargs)

    setuptools.setup = custom_setup


# Call the override when this module is imported
_override_setup()
