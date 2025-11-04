<template>
  <q-layout view="hHh lpR fFf">
    <q-header bordered class="bg-white text-grey-10">
      <q-toolbar>
        <q-btn flat dense round icon="menu" aria-label="Menu" @click="toggleLeftDrawer" />

        <q-toolbar-title>
          <span class="text-primary text-bold on-right">{{ t('main.brand') }}</span>
        </q-toolbar-title>

        <a href="https://www.epfl.ch" target="_blank">
          <img src="EPFL.svg" height="20px" class="on-left" />
        </a>
      </q-toolbar>
      <q-separator />
      <AppToolbar />
    </q-header>

    <q-drawer v-model="leftDrawerOpen" show-if-above bordered>
      <left-drawer class="q-mt-md" />
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import AppToolbar from 'src/components/AppToolbar.vue'
import LeftDrawer from 'src/components/LeftDrawer.vue'

const { t } = useI18n()

const leftDrawerOpen = ref(false)

function toggleLeftDrawer() {
  leftDrawerOpen.value = !leftDrawerOpen.value
}
</script>
