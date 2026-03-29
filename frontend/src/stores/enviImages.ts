import { defineStore } from 'pinia'
import { EnviImage } from 'envi-image-reader/image'

export const useEnviImagesStore = defineStore('enviImages', () => {
  const images = ref<Record<string, EnviImage> | null>(null)
  const loading = ref<boolean>(false)
  const error = ref<string | null>(null)

  function clearData() {
    images.value = null
    error.value = null
  }

  async function loadData(headerFiles: File[], bilFiles: File[]) {
    loading.value = true
    clearData()
    images.value = {}

    for (const headerFile of headerFiles) {
      const baseName = headerFile.name.slice(0, -4)
      const bilFile = bilFiles.find((f) => f.name.slice(0, -4) === baseName)
      if (!bilFile) {
        images.value = null
        error.value = `No matching BIL file found for header file ${headerFile.name}`
        loading.value = false
        return
      }

      try {
        images.value[baseName] = new EnviImage(headerFile, bilFile)
        await images.value[baseName].loading
      } catch (e) {
        images.value = null
        error.value = `Failed to load image ${baseName}: ${e}`
        loading.value = false
        return
      }
    }

    loading.value = false
  }

  function getHeaderValue(baseName: string, key: string): string | string[] | null {
    return images.value?.[baseName]?.headerData[key] || null
  }

  function getHeaderIntersectionListValue(key: string): string[] | null {
    if (!images.value || loading.value) {
      return null
    }

    let set = null

    for (const baseName of Object.keys(images.value)) {
      const value = getHeaderValue(baseName, key)
      if (!Array.isArray(value)) {
        return null
      }

      if (set === null) {
        set = new Set(value)
      } else {
        set = set.intersection(new Set(value))
      }
    }

    return set ? Array.from(set) : null
  }

  const bandNames = computed(() => getHeaderIntersectionListValue('band_names'))
  const wavelengths = computed(() => getHeaderIntersectionListValue('wavelength'))

  // const lines: ComputedRef<number | null> = getDataValue<number>('lines');
  // const samples: ComputedRef<number | null> = getDataValue<number>('samples');
  // const bands: ComputedRef<number | null> = getDataValue<number>('bands');

  // const bandNames: ComputedRef<string[]> = computed(() => {
  //   if (!data.value || !data.value['band_names']) {
  //     return [];
  //   }
  //   return data.value['band names'].slice(1, -1).split(',').map(b => b.trim());
  // });

  return {
    images,
    loading,
    error,
    // lines,
    // samples,
    // bands,
    bandNames,
    wavelengths,
    clearData,
    loadData,
  }
})
