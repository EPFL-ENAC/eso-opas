<template>
  <div>
    <q-form>
      <q-file
        label="Select BIL and HDR files"
        accept=".bil,.hdr"
        multiple
        v-model="files"
      >
        <template v-slot:prepend>
          <q-icon name="attach_file" />
        </template>
      </q-file>

      <q-btn
        label="Upload"
        color="primary"
        class="q-mt-md"
        :disable="!canUploadFiles"
        @click="upload"
      />
    </q-form>
  </div>
</template>

<script setup lang="ts">
import type { UploadInitResponse, UploadChunkResponse, UploadFinalizeResponse, UploadCancelResponse } from 'src/models';
const files = ref<File[]>([]);
let uploadController: AbortController | null = null;


const canUploadFiles = computed(() => {
  const hasBil = files.value.some(file => file.name.endsWith('.bil'));
  const hdrCount = files.value.filter(file => file.name.endsWith('.hdr')).length;
  return hasBil && hdrCount === 1;
});


const apiEndpoint = 'http://localhost:8000';
const chunkSizeMB = 10;
const chunkSize = 2; // chunkSizeMB * 1024 * 1024;
const parallelCount = 4;


async function upload() {
  if (!canUploadFiles.value) return;

  const file = files.value.find(file => file.name.endsWith('.bil'));
  if (!file) return;

  // Process file: take only even-positionned bytes
  const uploadSize = file.size / 2;

  try {
    const { sessionId, totalChunks } = await initUpload(file, uploadSize, chunkSize);
    console.log(`Upload initialized with session ID: ${sessionId}, total chunks: ${totalChunks}`);

    for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
      const startByte = chunkIndex * chunkSize * 2;
      const endByte = Math.min(startByte + chunkSize * 2, file.size);
      const blobSlice = file.slice(startByte, endByte);
      const readBuffer = await blobSlice.arrayBuffer();
      const processedBuffer = new Uint8Array(readBuffer.byteLength / 2);

      for (let i = 0, j = 0; i < readBuffer.byteLength; i += 2, j++) {
        processedBuffer[j] = new Uint8Array(readBuffer)[i] || 0;
      }

      const { progress, isComplete } = await uploadChunk(sessionId, chunkIndex, processedBuffer.buffer);
      console.log(`Uploaded chunk ${chunkIndex + 1}/${totalChunks}, progress: ${100 * progress}%`);

      if (isComplete) {
        console.log('Upload complete!');
      }
    }

    const finalizeResponse = await finalizeUpload(sessionId);
    console.log('Upload finalized:', finalizeResponse);

  } catch (error) {
    console.error('Upload failed:', error);
    return;
  }
}


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


</script>
