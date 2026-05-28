<template>
  <q-layout view="hHh lpR fFf">
    <q-header bordered class="bg-white text-grey-10">
      <q-toolbar>
        <q-toolbar-title>
          <span class="text-primary on-right lab-name">{{ t('main.brand') }}</span>
        </q-toolbar-title>

        <a href="https://www.epfl.ch" target="_blank">
          <img src="EPFL.svg" height="20px" class="on-left logo" />
        </a>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">

const { t } = useI18n()
</script>

<style lang="scss">
.lab-name {
  font-size: 1.6rem;
  font-weight: 700;
}

.logo {
  transform: translateY(2px);
}
</style>
