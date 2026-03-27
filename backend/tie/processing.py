import glob
import itertools as it
import json
import os
import re

import pysteviapp

inFolder = "/headlessIn/"
outFolder = "/headlessOut/"


def write_progress(step: int, total: int, message: str) -> None:
    with open(os.path.join(outFolder, "progress.json"), "w") as f:
        json.dump({"step": step, "total": total, "message": message}, f)


# list import files
bilFiles = glob.glob(os.path.join(inFolder, "*.bil"))
bilNames = [re.sub(r"\s+", "_", os.path.splitext(os.path.basename(f))[0]) for f in bilFiles]
configFile = os.path.join(inFolder, "config.json")

n_pairs = len(list(it.combinations(bilNames, 2)))
total_steps = 3 + n_pairs + 1  # load + init + N pairs + export

write_progress(1, total_steps, f"Found {len(bilFiles)} image(s), loading configuration")

# load configuration
with open(configFile) as configF:
    config = json.load(configF)

write_progress(2, total_steps, "Initializing project and loading sequences")

# get the app instance
app = pysteviapp.AppInstance()

# create a project
app.newProject()

# load the files
for bilFile, bilName in zip(bilFiles, bilNames):
    addSequenceArgs = [bilFile]
    addSequenceKwArgs = {"name": bilName}
    app.callAction("PikaLTools", "addBilSequence", addSequenceArgs, addSequenceKwArgs)

autoDetectTiePointsKwArgs = {
    "cornerMaxNCorners": "100",
    "ransacIterations": "200",
    "ransacThreshold": "10",
    "outFile": "",
}

if "cornerMaxNCorners" in config:
    autoDetectTiePointsKwArgs["cornerMaxNCorners"] = str(config["cornerMaxNCorners"])
if "ransacIterations" in config:
    autoDetectTiePointsKwArgs["ransacIterations"] = str(config["ransacIterations"])
if "ransacThreshold" in config:
    autoDetectTiePointsKwArgs["ransacThreshold"] = str(config["ransacThreshold"])

pairs = list(it.combinations(bilNames, 2))
for pair_idx, (bilName1, bilName2) in enumerate(pairs):
    current_step = 3 + pair_idx
    write_progress(
        current_step, total_steps, f"Running TIE detection for pair {pair_idx + 1}/{n_pairs}: {bilName1} ↔ {bilName2}"
    )

    seq1 = app.getDatablockByName(bilName1)
    seq2 = app.getDatablockByName(bilName2)

    lineStartSeq1 = "0"
    lineEndSeq1 = "-1"

    lineStartSeq2 = "0"
    lineEndSeq2 = "-1"

    if "linesStarts" in config:
        if bilName1 in config["linesStarts"]:
            lineStartSeq1 = str(config["linesStarts"][bilName1])
        if bilName2 in config["linesStarts"]:
            lineStartSeq2 = str(config["linesStarts"][bilName2])

    if "linesEnds" in config:
        if bilName1 in config["linesEnds"]:
            lineEndSeq1 = str(config["linesEnds"][bilName1])
        if bilName2 in config["linesEnds"]:
            lineEndSeq2 = str(config["linesEnds"][bilName2])

    outFilePath = os.path.join(
        outFolder,
        bilName1
        + "_l"
        + lineStartSeq1
        + "-l"
        + lineEndSeq1
        + "-"
        + bilName2
        + "_l"
        + lineStartSeq2
        + "-l"
        + lineEndSeq2
        + "-"
        + "matches.pdf",
    )

    autoDetectTiePointsArgs = [seq1.reference, seq2.reference, lineStartSeq1, lineEndSeq1, lineStartSeq2, lineEndSeq2]
    autoDetectTiePointsKwArgs["outFile"] = outFilePath
    app.callAction("PikaLTools", "autoDetectBilSequencesTiePoints", autoDetectTiePointsArgs, autoDetectTiePointsKwArgs)

write_progress(total_steps - 1, total_steps, "Exporting correspondence sets")

correspondencesSets = app.listDatablocks("StereoVisionApp::CorrespondencesSet")

for correspSet in correspondencesSets:
    exportSetArgs = [correspSet.reference, os.path.join(outFolder, correspSet.name + "_export.csv")]
    exportSetKwArgs: dict[str, str] = {}
    app.callAction("CorrespondencesSet", "exportSet", exportSetArgs, exportSetKwArgs)

write_progress(total_steps, total_steps, "Done")
