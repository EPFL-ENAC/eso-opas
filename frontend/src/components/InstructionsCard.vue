<template>
  <q-card flat bordered>
    <q-card-section>
      <h2 class="text-h6 q-mt-none q-mb-sm">General pipeline</h2>
      <p class="q-mb-sm">Under the hood, this tool uses the tie point matching toolbox from <a href="https://github.com/french-paragon/steviapp" target="_blank" class="text-primary">Steviapp</a>, combined with the push-broom image module <a href="https://github.com/french-paragon/PikaLTools/tree/main/tools/MalahydSteviappModule" target="_blank" class="text-primary">Malahyd</a>.</p>
      <p class="q-mb-sm">The processing pipeline is made of three main step:</p>
      <ul class="q-mb-md"><li class="q-mb-xs">Tie points detection</li></ul>
      <p class="q-mb-sm">A variant of the Harris corner detector is used to detect candidate tie points in each image.</p>
      <ul class="q-mb-md"><li class="q-mb-xs">Feature description and matching</li></ul>
      <p class="q-mb-sm">For each image, a rotation invariant descriptor of the patch is produced and then compared with all corners in the other images to produce a cost matrix. Assignment within each image pair is generated using the hungarian algorithm.</p>
      <ul class="q-mb-md"><li class="q-mb-xs">Inliers selection</li></ul>
      <p class="q-mb-sm">Ransac is used to select inliers matches. A perspective transform model is used, similar to the one used in the work of <a href="https://isprs-annals.copernicus.org/articles/X-2-W2-2025/7/2025/" target="_blank" class="text-primary">Burkhard et. al.</a>.</p>
    </q-card-section>
    <q-expansion-item expand-separator label="Input files" header-class="text-h6 text-weight-medium">
      <q-card-section>
        <p class="q-mb-sm">The tool expect, in the input folder, the following data:</p>
        <pre class="q-mb-md"><code class="bg-grey-2 q-pa-sm rounded-borders block">file_1.bil
file_1.hdr
...
file_n.bil
file_n.hdr
config.json</code></pre>
        <p class="q-mb-sm">where file_1 to file_n are bil files, the name of which does not matter, only that for each name you have both a valid .bil file with the raster data, and a .hdr file with the file metadata, in <a href="https://www.nv5geospatialsoftware.com/docs/ENVIImageFiles.html" target="_blank" class="text-primary">envi format</a>.</p>
        <p class="q-mb-sm">The config.json file contain the configuration to run the tool, in a specific json format. It should be provided with this specific name.</p>
      </q-card-section>
    </q-expansion-item>
    <q-expansion-item expand-separator label="Configuration file" header-class="text-h6 text-weight-medium">
      <q-card-section>
        <p class="q-mb-sm">The general structure of the configuration file is as follow:</p>
        <pre class="q-mb-md"><code class="bg-grey-2 q-pa-sm rounded-borders block">{
    &quot;cornerMaxNCorners&quot; : [string nCorners],
    &quot;ransacIterations&quot; : [string ransac iterations],
    &quot;ransacThreshold&quot; : [string ransac threshold in pixel],
    &quot;linesStarts&quot; : {
        &quot;file_1&quot; : [int line_id],
        ... ,
        &quot;file_n&quot; : [int line_id]
    },
    &quot;linesEnds&quot; : {
        &quot;file_1&quot; : [int line_id],
        ... ,
        &quot;file_n&quot; : [int line_id]
    }
}</code></pre>
        <p class="q-mb-sm">The parameters cornerMaxNCorners, ransacIterations and ransacThreshold must be provided as json strings convertible to int (due to the inner working of the tool). If a parameter is not provided, sensible defaults will be used.</p>
        <p class="q-mb-sm">cornerMaxNCorners represent the maximal number of corner the tool will detect, larger value will make the tool slower, but might help detect more matches.</p>
        <p class="q-mb-sm">ransacIterations represent the number of iterations in the ransac loop to detect inliers.</p>
        <p class="q-mb-sm">ransacThreshold represent the error threshold, in pixel, for a point to be considered as inlier. As the tool uses a perspective model to control the geometry of the points (pinhole based epipolar lines does not work for push-broom images), we recommande leaving this parameter at a relatively high threshold. If your scene has a lot of depth variation (e.g. mountains) or distortion (e.g. unstable platform), you can increase this parameter to try and get more matches.</p>
        <p class="q-mb-sm">The lines start and end indices have to be provided as ints.</p>
        <p class="q-mb-sm">An example of configuration file, with input files &quot;line3.bil&quot; and &quot;line5.bil&quot; would be:</p>
        <pre class="q-mb-md"><code class="bg-grey-2 q-pa-sm rounded-borders block">{
    &quot;cornerMaxNCorners&quot; : &quot;100&quot;,
    &quot;ransacIterations&quot; : &quot;200&quot;,
    &quot;ransacThreshold&quot; : &quot;10&quot;,
    &quot;linesStarts&quot; : {
        &quot;line3&quot; : 1300,
        &quot;line5&quot; : 1500
    },
    &quot;linesEnds&quot; : {
        &quot;line3&quot; : 3000,
        &quot;line5&quot; : 3000
    }
}</code></pre>
      </q-card-section>
    </q-expansion-item>
    <q-expansion-item expand-separator label="Output files" header-class="text-h6 text-weight-medium">
      <q-card-section>
        <p class="q-mb-sm">For each image pair, the tool output two file, one is named [file_1]-lines[i1]-[j1] - [file_2]-lines[i2]-[j2] correspondence set_export.csv and contain the correspondences, encoded in Steviapp correspondences sets format. Each line has the format UVT file_1 u1 0.00 t1,UVT file_2 u2 0.00 t2, where u1 and u2 are the pixel coordinate on the push-broom line (v is always 0), and t is the timing of the line in the bil, which will be the line id if no timing info is present in the file.</p>
        <p class="q-mb-sm">The file can be parsed into any tools, or re-imported as is in a steviapp project, as long as the bil sequences in the steviapp project have the same name as the input files.</p>
        <p class="q-mb-sm">The second file in the output is named [file_1]-lines[i1]-[j1] - [file_2]-lines[i2]-[j2]-matches.pdf, and is a preview of the matches in the bil file corresponding lines.</p>
      </q-card-section>
    </q-expansion-item>
  </q-card>
</template>

<script setup lang="ts">
// No script logic required — everything is static template markup.
</script>

<style scoped>
:deep(pre) { margin: 0; }
:deep(ul) { padding-left: 1.25rem; }
:deep(a) { text-decoration: none; }
</style>
