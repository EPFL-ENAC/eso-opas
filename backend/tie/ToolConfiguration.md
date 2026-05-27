# Input files Configuration

## general pipeline

Under the hood, this tool uses the tie point matching toolbox from [Steviapp](https://github.com/french-paragon/steviapp), combined with the push-broom image module [Malahyd](https://github.com/french-paragon/PikaLTools/tree/main/tools/MalahydSteviappModule).

The processing pipeline is made of three main step:

- Tie points detection

A variant of the Harris corner detector is used to detect candidate tie points in each image.

- Feature description and matching

For each image, a rotation invariant descriptor of the patch is produced and then compared with all corners in the other images to produce a cost matrix. Assignment within each image pair is generated using the hungarian algorithm.

- Inliers selection

Ransac is used to select inliers matches. A perspective transform model is used, similar to the one used in the work of [Burkhard et. al.](https://isprs-annals.copernicus.org/articles/X-2-W2-2025/7/2025/).

## input files

The tool expect, in the input folder, the following data:

```
file_1.bil
file_1.hdr
...
file_n.bil
file_n.hdr
config.json
```

where file_1 to file_n are bil files, the name of which does not matter, only that for each name you have both a valid .bil file with the raster data, and a .hdr file with the file metadata, in [envi format](https://www.nv5geospatialsoftware.com/docs/ENVIImageFiles.html).

The config.json file contain the configuration to run the tool, in a specific json format. It should be provided with this specific name.

## configuration file

The general structure of the configuration file is as follow:

```
{
    "cornerMaxNCorners" : [string nCorners],
    "ransacIterations" : [string ransac iterations],
    "ransacThreshold" : [string ransac threshold in pixel],
    "linesStarts" : {
        "file_1" : [int line_id],
        ... ,
        "file_n" : [int line_id]
    },
    "linesEnds" : {
        "file_1" : [int line_id],
        ... ,
        "file_n" : [int line_id]
    }
}
```

The parameters cornerMaxNCorners, ransacIterations and ransacThreshold must be provided as json strings convertible to int (due to the inner working of the tool). If a parameter is not provided, sensible defaults will be used.

cornerMaxNCorners represent the maximal number of corner the tool will detect, larger value will make the tool slower, but might help detect more matches.

ransacIterations represent the number of iterations in the ransac loop to detect inliers.

ransacThreshold represent the error threshold, in pixel, for a point to be considered as inlier. As the tool uses a perspective model to control the geometry of the points (pinhole based epipolar lines does not work for push-broom images), we recommande leaving this parameter at a relatively high threshold. If your scene has a lot of depth variation (e.g. mountains) or distortion (e.g. unstable platform), you can increase this parameter to try and get more matches.

The lines start and end indices have to be provided as ints.

An example of configuration file, with input files "line3.bil" and "line5.bil" would be:

```
{
    "cornerMaxNCorners" : "100",
    "ransacIterations" : "200",
    "ransacThreshold" : "10",
    "linesStarts" : {
        "line3" : 1300,
        "line5" : 1500
    },
    "linesEnds" : {
        "line3" : 3000,
        "line5" : 3000
    }
}
```

## output files

For each image pair, the tool output two file, one is named \[file_1\]-lines\[i1\]-\[j1\] - \[file_2\]-lines\[i2\]-\[j2\] correspondence set_export.csv and contain the correspondences, encoded in Steviapp correspondences sets format. Each line has the format UVT file_1 u1 0.00 t1,UVT file_2 u2 0.00 t2, where u1 and u2 are the pixel coordinate on the push-broom line (v is always 0), and t is the timing of the line in the bil, which will be the line id if no timing info is present in the file.

The file can be parsed into any tools, or re-imported as is in a steviapp project, as long as the bil sequences in the steviapp project have the same name as the input files.

The second file in the output is named \[file_1\]-lines\[i1\]-\[j1\] - \[file_2\]-lines\[i2\]-\[j2\]-matches.pdf, and is a preview of the matches in the bil file corresponding lines.
