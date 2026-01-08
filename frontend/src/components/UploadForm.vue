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
          :label="`Drag and drop or select ${SUPPORTED_IMAGE_EXTENSIONS.join('/')} and ${SUPPORTED_HEADER_EXTENSIONS.join('/')} files`"
          :accept="[...SUPPORTED_IMAGE_EXTENSIONS, ...SUPPORTED_HEADER_EXTENSIONS].join(',')"
          hint="Files will be processed locally before upload."
          v-model="files"
          multiple
          append
          use-chips
          clearable
          counter
          outlined
        >
          <template v-slot:prepend>
            <q-icon name="cloud_upload" />
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
          Please select at least one {{ SUPPORTED_IMAGE_EXTENSIONS.join('/') }} file and its corresponding {{
            SUPPORTED_HEADER_EXTENSIONS.join('/') }} header file.
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
          v-if="selectedWavelengths?.length > 0 || selectedBands?.length > 0"
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
        <q-linear-progress
          :value="uploadStats.progress"
          color="primary"
          class="q-mt-md"
          size="25px"
          :animation-speed="200"
        >
          <div v-if="uploadStats.progressStr" class="absolute-full flex flex-center">
            <q-badge color="white" text-color="primary" :label="uploadStats.progressStr" />
          </div>
        </q-linear-progress>

        <div class="text-caption text-grey-8 q-mt-sm">
          <div>
            <strong>Processing speed:</strong> {{ uploadStats.processSpeedStr }}
          </div>
          <div>
            <strong>Upload speed:</strong> {{ uploadStats.uploadSpeedStr }}
          </div>
          <div>
            <strong>ETA:</strong> {{ uploadStats.estimatedTimeRemainingStr }}
          </div>
        </div>

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

        <q-stepper-navigation>
          <q-btn flat @click="step = 2" color="primary" label="Back" class="q-ml-sm" />
        </q-stepper-navigation>
      </q-step>
    </q-stepper>
  </div>
</template>

<script setup lang="ts">
import { Notify } from 'quasar'; // Import Quasar Notify
import type { UploadInitResponse } from 'src/models';
import type { EnviImage } from 'envi-image-reader/image';
import { SUPPORTED_IMAGE_EXTENSIONS, SUPPORTED_HEADER_EXTENSIONS } from 'envi-image-reader/image';
import { baseUrl as apiBaseUrl } from 'src/boot/api';

const step = ref(1);
const enviImagesStore = useEnviImagesStore();
const files = ref<File[] | null>(null);
const selectedWavelengths = ref<string[]>([]);
const selectedBands = ref<string[]>([]);
const uploading = ref(false);
const sessionIdRef = ref<string | null>(null);
let uploadController: AbortController | null = null;
let etaInterval: ReturnType<typeof setInterval> | null = null;


function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}


const uploadStats = reactive({
  totalProcessedBytes: 0,
  totalUploadedBytes: 0,
  totalFiles: 0,
  processTime: 0,
  processedBytes: 0,
  uploadTime: 0,
  uploadedBytes: 0,
  uploadedFiles: 0,
  get progress() {
    return this.totalFiles > 0
      ? this.uploadedFiles / this.totalFiles
      : 0
  },
  get progressStr() {
    return this.totalFiles > 0
      ? `${Math.round(this.progress * 100)}% (${this.uploadedFiles}/${this.totalFiles})`
      : ""
  },
  get processSpeedStr() {
    if (this.processTime === 0) {
      return "-";
    }
    const speed = this.processedBytes / (this.processTime / 1000);
    return `${formatBytes(speed)}/s`;
  },
  get uploadSpeedStr() {
    if (this.uploadTime === 0) {
      return "-";
    }
    const speed = this.uploadedBytes / (this.uploadTime / 1000);
    return `${formatBytes(speed)}/s`;
  },
  get estimatedTimeRemainingStr() {
    if (this.processedBytes === 0 || this.uploadedBytes === 0) {
      return "-";
    }
    const processSpeed = this.processedBytes / (this.processTime / 1000);
    const processRemainingBytes = this.totalProcessedBytes - this.processedBytes;
    const uploadSpeed = this.uploadedBytes / (this.uploadTime / 1000);
    const uploadRemainingBytes = this.totalUploadedBytes - this.uploadedBytes;
    const estimatedTimeRemaining = processRemainingBytes / processSpeed + uploadRemainingBytes / uploadSpeed;
    const minutes = Math.floor(estimatedTimeRemaining / 60);
    const seconds = Math.floor(estimatedTimeRemaining % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  },

  reset() {
    this.totalProcessedBytes = 0;
    this.totalUploadedBytes = 0;
    this.totalFiles = 0;
    this.processTime = 0;
    this.processedBytes = 0;
    this.uploadTime = 0;
    this.uploadedBytes = 0;
    this.uploadedFiles = 0;
  }
});


const headerFiles = computed(() => {
  return files.value?.filter(file => SUPPORTED_HEADER_EXTENSIONS.some(ext => file.name.endsWith(ext))) || [];
});

const imageFiles = computed(() => {
  return files.value?.filter(file => SUPPORTED_IMAGE_EXTENSIONS.some(ext => file.name.endsWith(ext))) || [];
});

const filesSelectionIsValid = computed(() => {
  if (!headerFiles.value || headerFiles.value.length === 0) {
    return false;
  }

  if (imageFiles.value.length !== headerFiles.value.length) {
    return false;
  }

  for (const headerFile of headerFiles.value) {
    const baseName = headerFile.name.split('.').slice(0, -1).join('.');
    const matchingImageFile = imageFiles.value.find(file => file.name.startsWith(baseName));
    if (!matchingImageFile) {
      return false;
    }
  }

  return true;
});


watch(files, async () => {
  if (filesSelectionIsValid.value) {
    enviImagesStore.loadData(headerFiles.value, imageFiles.value);
  } else {
    enviImagesStore.clearData();
  }
  selectedWavelengths.value = [];
  selectedBands.value = [];
  uploadStats.reset();
})


const headerColumns = [
  { name: 'key', label: 'Key', field: 'key', align: 'left' as const },
  { name: 'value', label: 'Value', field: 'value', align: 'left' as const },
];


const headerRows = computed(() => {
  if (!enviImagesStore.images || enviImagesStore.loading) {
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
  wavelengthsOptions.value = newWavelengths || [];
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
  const hasImages = enviImagesStore.images !== null;
  const hasWavelengths = selectedWavelengths.value.length > 0;
  const hasBands = selectedBands.value.length > 0;
  return hasImages && (hasWavelengths || hasBands) && !uploading.value;
});


async function initSession(): Promise<UploadInitResponse> {
  uploadController = new AbortController();
  const url = `${apiBaseUrl}/upload/init`;

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
  }
}


async function uploadBuffer(buffer: ArrayBuffer, filename: string) {
  const startTime = performance.now();
  uploadStats.totalUploadedBytes += buffer.byteLength;

  try {
    if (!uploadController) {
      throw 'Upload controller not initialized';
    }

    const url = `${apiBaseUrl}/upload/?session_id=${sessionIdRef.value}&filename=${filename}`;
    const formData = new FormData();
    formData.append('file', new Blob([buffer]));

    const uploadResponse = await fetch(url, {
      method: 'POST',
      headers: {
        'accept': 'application/json',
      },
      body: formData,
      signal: uploadController.signal,
    });

    if (!uploadResponse.ok) {
      throw `Failed to upload file ${filename}: ${uploadResponse.statusText}`;
    }

  } catch (error) {
    console.error('Upload failed:', error);
    return;
  } finally {
    uploadStats.uploadedFiles += 1;
    uploadStats.uploadedBytes += buffer.byteLength;
    uploadStats.uploadTime += performance.now() - startTime;
  }
}


async function uploadHeader(image: EnviImage) {
  const readBuffer = await image.headerFile.arrayBuffer();
  const filename = encodeURIComponent(image.headerFile.name);
  uploadBuffer(readBuffer, filename);
}


async function uploadImage(image: EnviImage) {
  const startTime = performance.now();
  uploadStats.totalProcessedBytes += image.bilFile.size;

  let selectedChannels: number[];

  if (selectedWavelengths.value.length > 0) {
    selectedChannels = selectedWavelengths.value.map(wavelength =>
      image.headerData["wavelength"]?.indexOf(wavelength) ?? -1
    );
  } else {
    selectedChannels = selectedBands.value.map(bandName =>
      image.headerData["band_names"]?.indexOf(bandName) ?? -1
    );
  }

  const readBuffer = (await image.getBilData(selectedChannels)).buffer as ArrayBuffer;
  uploadStats.processedBytes += image.bilFile.size;
  uploadStats.processTime += performance.now() - startTime;

  const filename = encodeURIComponent(image.bilFile.name);
  uploadBuffer(readBuffer, filename);
}


async function upload() {
  if (!enviImagesStore.images) {
    return;
  }

  try {
    const { sessionId } = await initSession();
    uploading.value = true;
    sessionIdRef.value = sessionId;
    console.log(`Upload initialized with session ID: ${sessionId}`);

    if (!etaInterval) {
    console.log('Starting ETA update interval');
      etaInterval = setInterval(() => {
        console.log(uploadStats.estimatedTimeRemainingStr);
      }, 1000);
    }
  } catch (error) {
    console.error('Failed to initialize upload session:', error);
    uploading.value = false;
    sessionIdRef.value = null;

    Notify.create({
      type: 'negative',
      message: 'Failed to initialize upload session!',
      position: 'top',
      timeout: 3000
    });

    return;
  }

  uploading.value = true;
  uploadStats.reset();
  uploadStats.totalFiles = Object.keys(enviImagesStore.images).length * 2; // headers + images

  const promises: Promise<void>[] = [];

  for (const image of Object.values(enviImagesStore.images)) {
    promises.push(uploadHeader(image));
    promises.push(uploadImage(image));
  }

  await Promise.all(promises);

  // Stop ETA update interval
  if (etaInterval) {
    clearInterval(etaInterval);
    etaInterval = null;
  }

  uploading.value = false;
  sessionIdRef.value = null;
  uploadController = null;

  Notify.create({
    type: 'positive',
    message: 'Upload completed successfully!',
    position: 'top',
    timeout: 3000
  });
}


async function cancel() {
  if (!sessionIdRef.value) {
    return;
  }

  uploadController?.abort();
  uploadController = null;
  uploading.value = false;
  sessionIdRef.value = null;

  if (etaInterval) {
    clearInterval(etaInterval);
    etaInterval = null;
  }
}


</script>
