<template>
  <div>
    <q-form>
      <q-file
        label="Select an HDR file"
        accept=".hdr"
        multiple
        v-model="headerFile"
      >
        <template v-slot:prepend>
          <q-icon name="attach_file" />
        </template>
      </q-file>

      <q-banner
        v-if="headerStore.error"
        class="q-mt-md q-mb-md bg-negative text-white"
        type="negative"
        dense
      >
        <template v-slot:avatar>
          <q-icon name="error" color="white" />
        </template>
        {{ headerStore.error }}
      </q-banner>

      <q-table
        v-if="headerStore.data"
        title="Header information"
        class="q-mt-md"
        :columns="headerColumns"
        :rows="headerRows"
        dense
      />

      <q-select
        v-if="headerStore.data"
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

      <q-file
        v-if="headerStore.data"
        label="Select BIL files"
        class="q-mt-md"
        accept=".bil"
        multiple
        v-model="imageFiles"
      >
        <template v-slot:prepend>
          <q-icon name="attach_file" />
        </template>
      </q-file>

      <q-btn
        v-if="headerStore.data && !uploading"
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
    </q-form>
  </div>
</template>

<script setup lang="ts">
import type { UploadInitResponse, UploadChunkResponse, UploadFinalizeResponse, UploadCancelResponse } from 'src/models';
const headerStore = useHeaderStore();

const headerFile = ref<File | null>(null);
const imageFiles = ref<File[]>([]);
const selectedBands = ref<string[]>([]);
const uploading = ref(false);
const uploadProgress = ref(0);
const sessionIdRef = ref<string | null>(null);
let uploadController: AbortController | null = null;


watch(headerFile, async () => {
  if (headerFile.value && Array.isArray(headerFile.value) && headerFile.value.length > 0) {
    await headerStore.loadData(headerFile.value[0]);
  } else {
    headerStore.clearData();
  }
})


const headerColumns = [
  { name: 'key', label: 'Key', field: 'key', align: 'left' as const },
  { name: 'value', label: 'Value', field: 'value', align: 'left' as const },
];


const headerRows = computed(() => {
  if (!headerStore.data) {
    return [];
  }
  return Object.entries(headerStore.data).map(([key, value]) => ({
    key: key,
    value: value,
  }))
});


const bandNamesOptions = ref<string[]>([]);
watch(() => headerStore.bandNames, (newBandNames) => {
  bandNamesOptions.value = newBandNames;
}, { immediate: true });


function bandNamesFilterFn(val: string, update: (callback: () => void) => void) {
  if (val === '') {
    update(() => {
      bandNamesOptions.value = headerStore.bandNames;
    });
    return;
  }

  update(() => {
    const needle = val.toLowerCase();
    bandNamesOptions.value = headerStore.bandNames.filter(bandName => bandName.toLowerCase().includes(needle));
  });
}


const canUploadFiles = computed(() => {
  const hasHeader = headerStore.data !== null;
  const hasBil = imageFiles.value.some(file => file.name.endsWith('.bil'));
  const hasBands = selectedBands.value.length > 0;
  return hasBil && hasHeader && hasBands && !uploading.value;
});


const apiEndpoint = 'http://localhost:8000';
const chunkSizeMB = 10;
const chunkSize = chunkSizeMB * 1024 * 1024;
const concurrentUploads = 5;


async function initUpload(file: File, fileSize: number, chunkSize: number): Promise<UploadInitResponse> {
  uploadController = new AbortController();

  const filename = encodeURIComponent(file.name);
  const url = `${apiEndpoint}/upload/init?filename=${filename}&file_size=${fileSize}&chunk_size=${chunkSize}`;

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

  const url = `${apiEndpoint}/upload/chunk/${sessionId}?chunk_index=${chunkIndex}`;
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

  const url = `${apiEndpoint}/upload/finalize/${sessionId}`;

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

  const url = `${apiEndpoint}/upload/cancel/${sessionId}`;

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


async function processAndUploadChunk(sessionId: string, file: File, chunkIndex: number, chunkSize: number): Promise<UploadChunkResponse> {
  const startByte = chunkIndex * chunkSize * 2;
  const endByte = Math.min(startByte + chunkSize * 2, file.size);
  const blobSlice = file.slice(startByte, endByte);
  const readBuffer = await blobSlice.arrayBuffer();
  const processedBuffer = new Uint8Array(readBuffer.byteLength / 2);

  for (let i = 0, j = 0; i < readBuffer.byteLength; i += 2, j++) {
    processedBuffer[j] = new Uint8Array(readBuffer)[i] || 0;
  }

  return await uploadChunk(sessionId, chunkIndex, processedBuffer.buffer);
}


async function upload() {
  if (!canUploadFiles.value) return;

  const file = imageFiles.value.find(file => file.name.endsWith('.bil'));
  if (!file) return;

  // Process file: take only even-positionned bytes
  const uploadSize = file.size / 2;

  try {
    const { sessionId, totalChunks } = await initUpload(file, uploadSize, chunkSize);
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

        await processAndUploadChunk(sessionId, file, chunkIndex, chunkSize);
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
