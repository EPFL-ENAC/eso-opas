<template>
  <div>
    <q-stepper
      v-model="step"
      vertical
      animated
    >
      <q-step
        :name="1"
        title="Select files"
        icon="attach_file"
        :done="step > 1"
      >
        <q-file
          label="Select HDR and BIL files"
          accept=".hdr,.bil"
          multiple
          v-model="files"
        >
          <template v-slot:prepend>
            <q-icon name="attach_file" />
          </template>
        </q-file>

        <q-banner
          v-if="enviImagesStore.error"
          class="q-mt-md q-mb-md bg-negative text-white"
          type="negative"
          dense
        >
          <template v-slot:avatar>
            <q-icon name="error" color="white" />
          </template>
          {{ enviImagesStore.error }}
        </q-banner>

        <q-table
          v-if="enviImagesStore.images"
          title="Header information (from first image)"
          class="q-mt-md"
          :columns="headerColumns"
          :rows="headerRows"
          dense
        />

        <q-stepper-navigation
          v-if="filesSelectionIsValid && enviImagesStore.images"
        >
          <q-btn
            @click="step = 2"
            label="Continue"
            color="primary"
          />
        </q-stepper-navigation>

        <q-banner
          v-else
          class="q-mt-md bg-info text-black"
          type="info"
          dense
        >
          <template v-slot:avatar>
            <q-icon name="info" color="black" />
          </template>
          Please select at least one BIL file and its corresponding HDR file(s).
        </q-banner>
      </q-step>

      <q-step
        :name="2"
        title="Select channels"
        icon="tune"
        :done="step > 2"
      >
        <q-select
          v-if="enviImagesStore.wavelengths"
          v-model="selectedWavelengths"
          label="Select wavelengths (at least one)"
          class="q-mt-md"
          :options="wavelengthsOptions"
          @filter="wavelengthsFilterFn"
          clearable
          multiple
          use-input
          input-debounce="0"
          use-chips
          behavior="menu"
        />

        <q-select
          v-if="!enviImagesStore.wavelengths && enviImagesStore.bandNames"
          v-model="selectedBands"
          label="Select bands (at least one)"
          class="q-mt-md"
          :options="bandNamesOptions"
          @filter="bandNamesFilterFn"
          clearable
          multiple
          use-input
          input-debounce="0"
          use-chips
          behavior="menu"
        />

        <q-stepper-navigation
          v-if="selectedWavelengths.length > 0 || selectedBands.length > 0"
        >
          <q-btn
            @click="step = 3"
            label="Continue"
            color="primary"
          />
          <q-btn flat @click="step = 1" color="primary" label="Back" class="q-ml-sm" />
        </q-stepper-navigation>

        <q-banner
          v-else
          class="q-mt-md bg-info text-black"
          type="info"
          dense
        >
          <template v-slot:avatar>
            <q-icon name="info" color="black" />
          </template>
          Please select at least one channel.
        </q-banner>
      </q-step>

      <q-step
        :name="3"
        title="Upload and process"
        icon="cloud_upload"
        :done="step > 3"
      >
        <q-btn
          v-if="enviImagesStore.images && !uploading"
          label="Upload"
          color="primary"
          class="q-mt-md"
          :disable="!canUploadFiles"
          @click="upload"
        />

        <q-btn
          label="Cancel"
          class="q-mt-md"
          v-if="uploading"
          @click="cancel"
        />

        <q-linear-progress
          v-if="uploading"
          :value="uploadProgress"
          color="primary"
          class="q-mt-md"
          :animation-speed="200"
        />

        <q-stepper-navigation>
          <q-btn flat @click="step = 2" color="primary" label="Back" class="q-ml-sm" />
        </q-stepper-navigation>
      </q-step>
    </q-stepper>
  </div>
</template>

<script setup lang="ts">
import type { UploadInitResponse, UploadChunkResponse, UploadFinalizeResponse, UploadCancelResponse } from 'src/models';
import type { EnviImage } from '../envi_bil_reader/image';
import { baseUrl as apiBaseUrl } from 'src/boot/api';

const step = ref(1);
const enviImagesStore = useEnviImagesStore();
const files = ref<File[]>([]);
const selectedWavelengths = ref<string[]>([]);
const selectedBands = ref<string[]>([]);
const uploading = ref(false);
const uploadProgress = ref(0);
const sessionIdRef = ref<string | null>(null);
let uploadController: AbortController | null = null;


const headerFiles = computed(() => {
  return files.value.filter(file => file.name.endsWith('.hdr'));
});

const imageFiles = computed(() => {
  return files.value.filter(file => file.name.endsWith('.bil'));
});

const filesSelectionIsValid = computed(() => {
  if (headerFiles.value.length === 0) {
    return false;
  }

  if (imageFiles.value.length !== headerFiles.value.length) {
    return false;
  }

  for (const headerFile of headerFiles.value) {
    const baseName = headerFile.name.slice(0, -4);
    const imageName = `${baseName}.bil`;
    const matchingImageFile = imageFiles.value.find(file => file.name === imageName);
    if (!matchingImageFile) {
      return false;
    }
  }

  return true;
});


watch(headerFiles, async () => {
  if (filesSelectionIsValid.value) {
    enviImagesStore.loadData(headerFiles.value, imageFiles.value);
  } else {
    enviImagesStore.clearData();
  }
})


const headerColumns = [
  { name: 'key', label: 'Key', field: 'key', align: 'left' as const },
  { name: 'value', label: 'Value', field: 'value', align: 'left' as const },
];


const headerRows = computed(() => {
  if (!enviImagesStore.images) {
    return [];
  }
  const firstImage = Object.values(enviImagesStore.images)[0];
  if (!firstImage || !firstImage.headerData) {
    return [];
  }
  return Object.entries(firstImage.headerData).map(([key, value]) => ({
    key: key,
    value: Array.isArray(value) ? value.join(',') : String(value),
  }))
});


const wavelengthsOptions = ref<string[]>([]);
watch(() => enviImagesStore.wavelengths, (newWavelengths) => {
  wavelengthsOptions.value = newWavelengths || []
}, { immediate: true });


function wavelengthsFilterFn(val: string, update: (callback: () => void) => void) {
  update(() => {
    const needle = val.toLowerCase();
    wavelengthsOptions.value = enviImagesStore.wavelengths?.filter(wavelength => wavelength.toLowerCase().includes(needle)) || [];
  });
}


const bandNamesOptions = ref<string[]>([]);
watch(() => enviImagesStore.bandNames, (newBandNames) => {
  bandNamesOptions.value = newBandNames || [];
}, { immediate: true });


function bandNamesFilterFn(val: string, update: (callback: () => void) => void) {
  update(() => {
    const needle = val.toLowerCase();
    bandNamesOptions.value = enviImagesStore.bandNames?.filter(bandName => bandName.toLowerCase().includes(needle)) || [];
  });
}


const canUploadFiles = computed(() => {
  const hasHeader = enviImagesStore.images !== null;
  const hasBil = imageFiles.value.some(file => file.name.endsWith('.bil'));
  const hasWavelengths = selectedWavelengths.value.length > 0;
  const hasBands = selectedBands.value.length > 0;
  return hasBil && hasHeader && (hasWavelengths || hasBands) && !uploading.value;
});


const chunkSizeMB = 10;
const chunkSize = chunkSizeMB * 1024 * 1024;
const concurrentUploads = 5;


async function initUpload(filename: string, fileSize: number, chunkSize: number): Promise<UploadInitResponse> {
  uploadController = new AbortController();
  const url = `${apiBaseUrl}/upload/init?filename=${filename}&file_size=${fileSize}&chunk_size=${chunkSize}`;

  const initResponse = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: uploadController.signal,
  });

  if (!initResponse.ok) {
    throw `Failed to initialize upload: ${initResponse.statusText}`;
  }

  const data = await initResponse.json();
  return {
    sessionId: data.session_id,
    totalChunks: data.total_chunks,
  }
}


async function uploadChunk(sessionId: string, chunkIndex: number, chunkData: ArrayBuffer): Promise<UploadChunkResponse> {
  if (!uploadController) {
    throw 'Upload controller not initialized';
  }

  const url = `${apiBaseUrl}/upload/chunk/${sessionId}?chunk_index=${chunkIndex}`;
  const formData = new FormData();
  formData.append('file', new Blob([chunkData]));

  const chunkResponse = await fetch(url, {
    method: 'POST',
    headers: {
      'accept': 'application/json',
    },
    body: formData,
    signal: uploadController.signal,
  });

  if (!chunkResponse.ok) {
    throw `Failed to upload chunk ${chunkIndex}: ${chunkResponse.statusText}`;
  }

  const data = await chunkResponse.json();
  return {
    progress: data.progress,
    isComplete: data.complete,
  };
}


async function finalizeUpload(sessionId: string): Promise<UploadFinalizeResponse> {
  if (!uploadController) {
    throw 'Upload controller not initialized';
  }

  const url = `${apiBaseUrl}/upload/finalize/${sessionId}`;

  const finalizeResponse = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: uploadController.signal,
  });

  if (!finalizeResponse.ok) {
    throw `Failed to finalize upload: ${finalizeResponse.statusText}`;
  }

  const data = await finalizeResponse.json();
  return {
    filename: data.filename,
    filepath: data.filepath,
    fileSize: data.file_size,
    chunksReceived: data.chunks_received,
  };
}


async function cancelUpload(sessionId: string): Promise<UploadCancelResponse> {
  if (!uploadController) {
    throw 'Upload controller not initialized';
  }

  const url = `${apiBaseUrl}/upload/cancel/${sessionId}`;

  const cancelResponse = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: uploadController.signal,
  });

  if (!cancelResponse.ok) {
    throw `Failed to cancel upload: ${cancelResponse.statusText}`;
  }

  const data = await cancelResponse.json();
  return {
    detail: data.message,
  };
}


async function uploadBuffer(buffer: ArrayBuffer, filename: string) {
  const uploadSize = buffer.byteLength;

  try {
    const { sessionId, totalChunks } = await initUpload(filename, uploadSize, chunkSize);
    uploading.value = true;
    sessionIdRef.value = sessionId;
    console.log(`Upload initialized with session ID: ${sessionId}, total chunks: ${totalChunks}`);

    let nextChunkIndex = 0;
    let completedChunks = 0;
    const worker = async (): Promise<void> => {
      while (true) {
        const chunkIndex = nextChunkIndex++;
        if (chunkIndex >= totalChunks || !uploading.value) {
          break;
        }

        await uploadChunk(sessionId, chunkIndex, buffer);
        completedChunks++;
        uploadProgress.value = completedChunks / totalChunks;
        console.log(`Uploaded chunk ${chunkIndex + 1}/${totalChunks}, progress: ${100 * uploadProgress.value}%`);
      }
    }

    const workers: Promise<void>[] = [];
    for (let i = 0; i < concurrentUploads; i++) {
      workers.push(worker());
    }
    await Promise.all(workers);

    const finalizeResponse = await finalizeUpload(sessionId);
    console.log('Upload finalized:', finalizeResponse);

  } catch (error) {
    console.error('Upload failed:', error);
    return;
  } finally {
    uploading.value = false;
    sessionIdRef.value = null;
    uploadProgress.value = 0;
    uploadController = null;
  }
}


async function uploadHeader(image: EnviImage) {
  const readBuffer = await image.headerFile.arrayBuffer();
  const filename = encodeURIComponent(image.headerFile.name);
  uploadBuffer(readBuffer, filename);
}


async function uploadImage(image: EnviImage) {
  let selectedChannels: number[];

  if (selectedWavelengths.value.length > 0) {
    selectedChannels = selectedWavelengths.value.map(wavelength => image.headerData["wavelength"]?.indexOf(wavelength) || -1);
  } else {
    selectedChannels = selectedBands.value.map(bandName => image.headerData["band names"]?.indexOf(bandName) || -1);
  }

  const readBuffer = (await image.getBilData(selectedChannels)).buffer as ArrayBuffer;
  const filename = encodeURIComponent(image.bilFile.name);
  uploadBuffer(readBuffer, filename);
}


async function upload() {
  if (!enviImagesStore.images) {
    return;
  }

  for (const image of Object.values(enviImagesStore.images)) {
    uploadHeader(image);
    uploadImage(image)
  }
}


async function cancel() {
  if (!sessionIdRef.value) {
    return;
  }
  try {
    const cancelResponse = await cancelUpload(sessionIdRef.value);
    console.log('Upload cancelled:', cancelResponse);
  } catch (error) {
    console.error('Failed to cancel upload:', error);
  } finally {
    uploading.value = false;
    sessionIdRef.value = null;
    uploadProgress.value = 0;
    uploadController = null;
  }
}


</script>
