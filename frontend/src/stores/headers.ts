import { defineStore } from 'pinia';
import { loadHeaderData } from '../envi_bil_reader/header';


export const useHeadersStore = defineStore('headers', () => {
  const data = ref<Record<string, Record<string, string>> | null>(null);
  const error = ref<string | null>(null);

  function clearData() {
    data.value = null;
    error.value = null;
  }

  async function loadData(files: File[]) {
    clearData();
    data.value = {};

    for (const file of files) {
      try {
        data.value[file.name] = await loadHeaderData(file);
      } catch (e) {
        data.value = null;
        error.value = `Failed to load header from file ${file.name}: ${e}`;
        return;
      }
    }
  }

  function getValue(filename: string, key: string): string | null {
    return data.value?.[filename]?.[key]?.trim() || null;
  }

  function getListValue(filename: string, key: string): string[] | null {
    const values = getValue(filename, key);
    if (!values) {
      return null;
    }

    return values.slice(1, -1).split(',').map(v => v.trim());
  }

  function getIntersectionListValue(key: string): string[] | null {
    if (!data.value) {
      return null;
    }

    let set = null;

    for (const filename of Object.keys(data.value)) {
      const value = getListValue(filename, key);
      if (!Array.isArray(value)) {
        error.value = `Header value for key "${key}" in file "${filename}" is not a list.`;
        return null;
      }

      if (set === null) {
        set = new Set(value);
      } else {
        set = set.intersection(new Set(value));
      }
    }

    return set ? Array.from(set) : null;
  }

  const bandNames = computed(() => getIntersectionListValue('band names'));
  const wavelengths = computed(() => getIntersectionListValue('wavelength'));

  // const lines: ComputedRef<number | null> = getDataValue<number>('lines');
  // const samples: ComputedRef<number | null> = getDataValue<number>('samples');
  // const bands: ComputedRef<number | null> = getDataValue<number>('bands');

  // const bandNames: ComputedRef<string[]> = computed(() => {
  //   if (!data.value || !data.value['band names']) {
  //     return [];
  //   }
  //   return data.value['band names'].slice(1, -1).split(',').map(b => b.trim());
  // });

  return {
    data,
    error,
    // lines,
    // samples,
    // bands,
    bandNames,
    wavelengths,
    clearData,
    loadData,
  };
});
