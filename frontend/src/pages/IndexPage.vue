<template>
  <q-page class="q-pa-lg max-width">
    <div class="q-px-md">
      <h1 class="text-h4 text-bold q-mb-lg">Open Processing of Airborne<br>Imaging Spectrometry (OPAS)</h1>
      <span class="text-h5 text-primary subtitle">Creation of Automated Tie-Points<br>in overlapping flight-lines </span>
    </div>

    <instructions-card class="q-mt-lg"/>
    <upload-form class="q-mt-lg" />
  </q-page>
</template>

<script setup lang="ts">
import InstructionsCard from 'src/components/InstructionsCard.vue'
import UploadForm from 'src/components/UploadForm.vue'
</script>

<style scoped lang="scss">
.max-width {
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
}

.subtitle::before {
  content: '';
  display: block;
  width: 50px;
  border-top: 2px solid red;
  margin-bottom: 20px;
}
</style>
