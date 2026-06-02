<template>
  <router-view />
</template>

<script setup lang="ts">
import { useDomTranslator } from './utils/domTranslate'

useDomTranslator()
</script>
