import { defineStore } from 'pinia';
import type {  } from 'src/models';


export const useHeaderStore = defineStore('header', () => {
  const data = ref<Record<string, string> | null>(null);
  const error = ref<string | null>(null);

  const bandNames = computed(() => {
    if (!data.value || !data.value['band names']) {
      return [];
    }
    return data.value['band names'].slice(1, -1).split(',').map(b => b.trim());
  });

  function clearData() {
    data.value = null;
    error.value = null;
  }

  async function loadData(file: File) {
    clearData();

    try {
      const text = await file.text();
      const lines = text.split('\n');
      if (lines.length === 0) {
        data.value = null;
        error.value = 'Header file is empty.';
        return;
      }
      if (lines[0] !== "ENVI") {
        data.value = null;
        error.value = 'Invalid header file format.';
      }

      data.value = {};

      for (const line of lines.slice(1)) {
        const splitIndex = line.indexOf('=');
        const key = line.slice(0, splitIndex).trim();
        const value = line.slice(splitIndex + 1).trim();
        data.value[key] = value;
      }
    } catch (e) {
      data.value = null;
      error.value = `Failed to read header file: ${e}`;
    }
  }

  return {
    data,
    error,
    bandNames,
    clearData,
    loadData,
  };
});
