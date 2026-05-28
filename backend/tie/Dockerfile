FROM ubuntu:24.04

RUN apt update; DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt install -y build-essential cmake git pkg-config libeigen3-dev libproj-dev cimg-dev libceres-dev libgoogle-glog-dev libexiv2-dev qtbase5-dev qt5-qmake pybind11-dev python3 libqcustomplot-dev
RUN apt install -y libgeotiff-dev libtclap-dev libfftw3-dev

# Compiler wrappers: appends -mno-avx512f last so it overrides any -march=native
# added by upstream CMakeLists.txt via target_compile_options (cluster nodes have no AVX-512)
RUN printf '#!/bin/bash\nexec /usr/bin/g++ "$@" -mno-avx512f -mno-avx512bw -mno-avx512vl\n' > /noavx512-cxx && \
    printf '#!/bin/bash\nexec /usr/bin/gcc "$@" -mno-avx512f -mno-avx512bw -mno-avx512vl\n' > /noavx512-cc && \
    chmod +x /noavx512-cxx /noavx512-cc

#multidimarrays
RUN git clone https://github.com/french-paragon/MultidimArrays.git; cd MultidimArrays; git checkout 78d674a3a3713feee4ced37a95fef3b53cc2832b; mkdir build; cd build; cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-march=x86-64-v3" -DCMAKE_C_FLAGS="-march=x86-64-v3" -DCMAKE_CXX_COMPILER=/noavx512-cxx -DCMAKE_C_COMPILER=/noavx512-cc; make -j$(nproc --all); make install; cd ..

#libstevi
RUN git clone https://github.com/french-paragon/LibStevi.git; cd LibStevi; git checkout 0f5075a3f7930bd4f711510bb79a4778045ff369; git submodule update --init --recursive; sed -i -e "s/SHARED/STATIC/g" CMakeLists.txt; mkdir build; cd build; cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-march=x86-64-v3" -DCMAKE_C_FLAGS="-march=x86-64-v3" -DCMAKE_CXX_COMPILER=/noavx512-cxx -DCMAKE_C_COMPILER=/noavx512-cc; make -j$(nproc --all); make install; cd ..

#status optional
RUN git clone https://github.com/french-paragon/StatusOptional.git; cd StatusOptional; git checkout fde87a772caa79d55a856572006923e526c6a62a; mkdir build; cd build; cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-march=x86-64-v3" -DCMAKE_C_FLAGS="-march=x86-64-v3" -DCMAKE_CXX_COMPILER=/noavx512-cxx -DCMAKE_C_COMPILER=/noavx512-cc; make -j$(nproc --all); make install; cd ..

#steviapp
RUN git clone https://github.com/french-paragon/steviapp.git; cd steviapp; git checkout 21fe5578bb4f5839d242bdfef5f542e4a404913e; head -n103 CMakeLists.txt >> tmp.txt; echo "find_package(StereoVision REQUIRED)" >> tmp.txt; tail -n98 CMakeLists.txt >> tmp.txt; cp tmp.txt CMakeLists.txt; mkdir build; cd build; cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-march=x86-64-v3" -DCMAKE_C_FLAGS="-march=x86-64-v3" -DCMAKE_CXX_COMPILER=/noavx512-cxx -DCMAKE_C_COMPILER=/noavx512-cc; make -j$(nproc --all); make install; cd ..

#PikaLTools
RUN git clone https://github.com/french-paragon/PikaLTools.git; cd PikaLTools; git checkout 3da34562bdf115d022211e44d651c468d17b2136; git submodule update --init --recursive; head -n37 CMakeLists.txt >> tmp.txt; echo "find_package(StereoVision REQUIRED)" >> tmp.txt; tail -n37 CMakeLists.txt >> tmp.txt; cp tmp.txt CMakeLists.txt; mkdir build; cd build; cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-march=x86-64-v3" -DCMAKE_C_FLAGS="-march=x86-64-v3" -DCMAKE_CXX_COMPILER=/noavx512-cxx -DCMAKE_C_COMPILER=/noavx512-cc -DBUILD_TESTS=OFF; make -j$(nproc --all); cd ..

COPY processing.py /

WORKDIR /steviapp/build/
ENTRYPOINT ["steviapp", "-platform", "offscreen", "--module", "/PikaLTools/build/tools/MalahydSteviappModule/pikal_steviapp_module.so", "--headless", "--script", "/processing.py"]
