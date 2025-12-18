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
          :label="`Select ${SUPPORTED_IMAGE_EXTENSIONS.join('/')} and ${SUPPORTED_HEADER_EXTENSIONS.join('/')} files`"
          :accept="[...SUPPORTED_IMAGE_EXTENSIONS, ...SUPPORTED_HEADER_EXTENSIONS].join(',')"
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
import { Notify } from 'quasar'; // Import Quasar Notify
import type { UploadInitResponse } from 'src/models';
import type { EnviImage } from '../envi_image_reader/image';
import { SUPPORTED_IMAGE_EXTENSIONS, SUPPORTED_HEADER_EXTENSIONS } from '../envi_image_reader/image';
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
  return files.value.filter(file => SUPPORTED_HEADER_EXTENSIONS.some(ext => file.name.endsWith(ext)));
});

const imageFiles = computed(() => {
  return files.value.filter(file => SUPPORTED_IMAGE_EXTENSIONS.some(ext => file.name.endsWith(ext)));
});

const filesSelectionIsValid = computed(() => {
  if (headerFiles.value.length === 0) {
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
  const hasImages = enviImagesStore.images !== null;
  const hasWavelengths = selectedWavelengths.value.length > 0;
  const hasBands = selectedBands.value.length > 0;
  return hasImages && (hasWavelengths || hasBands) && !uploading.value;
});


const concurrentUploads = 5;


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
    selectedChannels = selectedBands.value.map(bandName => image.headerData["band_names"]?.indexOf(bandName) || -1);
  }

  const readBuffer = (await image.getBilData(selectedChannels)).buffer as ArrayBuffer;
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
  uploadProgress.value = 0;

  const numImages = Object.keys(enviImagesStore.images).length;
  let uploadedImages = 0;
  const promises: Promise<void>[] = [];

  for (const image of Object.values(enviImagesStore.images)) {
    promises.push(uploadHeader(image));
    promises.push(uploadImage(image).then(() => {
      uploadedImages += 1;
      uploadProgress.value = uploadedImages / numImages;
    }));
  }

  await Promise.all(promises);

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
  uploadProgress.value = 0;
}


</script>
