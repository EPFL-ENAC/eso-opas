#!/usr/bin/env python3
"""Patch backend/tie/Dockerfile from the upstream base got from
https://gitlab.epfl.ch/topo/opastiepointsdetectordocker/-/raw/main/Dockerfile
"""

import os
import sys

TIE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(TIE_DIR, "Dockerfile")
TARGET_PATH = os.path.join(TIE_DIR, "Dockerfile")

COMPILER_WRAPPER_BLOCK = (
    "RUN apt install -y libgeotiff-dev libtclap-dev libfftw3-dev\n\n"
    "# Compiler wrappers: appends -mno-avx512f last so it overrides any -march=native\n"
    "# added by upstream CMakeLists.txt via target_compile_options (cluster nodes have no AVX-512)\n"
    "RUN printf '#!/bin/bash\\nexec /usr/bin/g++ \"$@\" -mno-avx512f -mno-avx512bw -mno-avx512vl\\n' > /noavx512-cxx && \\\n"
    "    printf '#!/bin/bash\\nexec /usr/bin/gcc \"$@\" -mno-avx512f -mno-avx512bw -mno-avx512vl\\n' > /noavx512-cc && \\\n"
    "    chmod +x /noavx512-cxx /noavx512-cc\n"
)

CMAKE_FLAGS = (
    '-DCMAKE_CXX_FLAGS="-march=x86-64-v3" '
    '-DCMAKE_C_FLAGS="-march=x86-64-v3" '
    "-DCMAKE_CXX_COMPILER=/noavx512-cxx "
    "-DCMAKE_C_COMPILER=/noavx512-cc"
)


def read_base() -> str:
    with open(BASE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def patch(content: str) -> str:
    content = content.replace("\r\n", "\n")

    # 1. Insert compiler-wrapper block after the second apt-install line.
    apt_line = "RUN apt install -y libgeotiff-dev libtclap-dev libfftw3-dev\n"
    if apt_line not in content:
        raise ValueError("Could not find the second apt-install line.")
    content = content.replace(apt_line, COMPILER_WRAPPER_BLOCK, 1)

    # 2. Patch the three plain cmake lines (libstevi, status optional, steviapp).
    old_plain = "cmake .. -DCMAKE_BUILD_TYPE=Release; make"
    new_plain = f"cmake .. -DCMAKE_BUILD_TYPE=Release {CMAKE_FLAGS}; make"

    count = 0
    while old_plain in content and count < 3:
        content = content.replace(old_plain, new_plain, 1)
        count += 1
    if count != 3:
        raise ValueError(
            f"Expected 3 occurrences of '{old_plain}', found {count}. The upstream Dockerfile may have changed."
        )

    # 3. Patch the PikaLTools cmake line.
    old_pikal = "cmake .. -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF; make"
    new_pikal = f"cmake .. -DCMAKE_BUILD_TYPE=Release {CMAKE_FLAGS} -DBUILD_TESTS=OFF; make"
    if old_pikal not in content:
        raise ValueError(
            f"Could not find PikaLTools cmake line '{old_pikal}'. The upstream Dockerfile may have changed."
        )
    content = content.replace(old_pikal, new_pikal, 1)

    return content


def main() -> int:
    content = read_base()

    print("Patching Dockerfile...")
    try:
        result = patch(content)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    with open(TARGET_PATH, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Patched {TARGET_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
