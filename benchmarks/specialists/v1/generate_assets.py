#!/usr/bin/env python3
"""Generate the CC0 Phase 2D.2 synthetic specialist benchmark corpus.

The corpus contains only project-authored passages and locally rendered pages.
It requires ImageMagick's ``magick`` executable to build the committed PNG
assets; benchmark loading itself has no ImageMagick dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
FONT = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
SOURCE_URL = "https://github.com/Dezire0/Mystic/tree/main/benchmarks/specialists/v1"


def passage(identifier: str, title: str, text: str, *, domain: str, language: str = "en") -> dict[str, str]:
    return {
        "document_id": identifier,
        "source_id": identifier,
        "source_type": "project_authored_cc0",
        "title": title,
        "language": language,
        "domain": domain,
        "text": text,
        "source_url": SOURCE_URL,
        "license": "CC0-1.0",
    }


PASSAGES = [
    passage("physics-newton-force", "Net force", "Newton second law states that net force equals mass multiplied by acceleration. In SI notation F = m a and force is measured in newtons.", domain="physics"),
    passage("physics-projectile-motion", "Projectile motion", "Ignoring air resistance, a projectile has constant horizontal velocity while gravity produces downward acceleration. Launch angle and speed affect range.", domain="physics"),
    passage("physics-kinetic-energy", "Kinetic energy", "Kinetic energy is one half of mass times velocity squared. Doubling velocity increases kinetic energy by a factor of four.", domain="physics"),
    passage("physics-heat-transfer", "Heat transfer", "Conduction transfers heat through material contact, convection transfers heat with moving fluid, and radiation transfers energy by electromagnetic waves.", domain="physics"),
    passage("physics-electric-circuit", "Electric circuits", "Ohm law relates voltage, current, and resistance: V = I R. A series circuit carries the same current through each component.", domain="physics"),
    passage("physics-wave-frequency", "Wave frequency", "Wave speed equals frequency times wavelength. Higher frequency means more oscillations per second when wave speed is fixed.", domain="physics"),
    passage("physics-friction", "Friction", "Friction opposes relative motion between surfaces. Kinetic friction is often modeled as coefficient times normal force.", domain="physics"),
    passage("physics-pressure-fluid", "Fluid pressure", "Pressure is force divided by area. In a static fluid, pressure increases with depth according to density, gravity, and height.", domain="physics"),
    passage("math-derivative", "Derivative", "A derivative measures instantaneous rate of change. The derivative of position with respect to time is velocity.", domain="mathematics"),
    passage("math-integral", "Integral", "A definite integral accumulates quantity over an interval. The area under a velocity versus time graph gives displacement.", domain="mathematics"),
    passage("math-matrix-transform", "Matrix transformation", "A matrix can represent a linear transformation. Multiplying a vector by a rotation matrix changes its coordinates while preserving length.", domain="mathematics"),
    passage("math-probability", "Probability", "For independent events, the probability that both occur is the product of their probabilities. A probability ranges from zero to one.", domain="mathematics"),
    passage("math-eigenvalue", "Eigenvalues", "An eigenvector keeps its direction under a linear transformation, and its eigenvalue gives the scale factor applied to that vector.", domain="mathematics"),
    passage("math-optimization", "Optimization", "Optimization selects input values that minimize or maximize an objective subject to constraints. Gradient methods use local derivatives.", domain="mathematics"),
    passage("math-error-propagation", "Uncertainty propagation", "Independent measurement uncertainties combine through the sensitivity of a result to each input. Reporting units and uncertainty is essential.", domain="mathematics"),
    passage("math-fourier", "Fourier components", "A Fourier transform represents a signal by frequency components. Filtering can attenuate high-frequency noise while retaining a lower-frequency trend.", domain="mathematics"),
    passage("eng-beam-load", "Beam load", "A loaded beam experiences bending moment and shear force. Support conditions and cross section determine deflection under a specified load.", domain="engineering"),
    passage("eng-fatigue-cycle", "Fatigue cycles", "Repeated stress can initiate and grow cracks below the static yield strength. Fatigue life depends on stress amplitude and cycle count.", domain="engineering"),
    passage("eng-feedback-control", "Feedback control", "A feedback controller compares a measured output with a setpoint and adjusts an actuator to reduce error. Excess gain can cause oscillation.", domain="engineering"),
    passage("eng-sensor-calibration", "Sensor calibration", "Calibration relates a sensor signal to a reference quantity. A calibration record should include offset, slope, units, and uncertainty.", domain="engineering"),
    passage("eng-signal-filter", "Signal filtering", "A low-pass filter suppresses rapid fluctuations above a cutoff frequency. Filter choice trades noise reduction against response delay.", domain="engineering"),
    passage("eng-pump-flow", "Pump flow", "A pump moves fluid by adding pressure head. Flow rate depends on the pump curve, pipe resistance, and fluid properties.", domain="engineering"),
    passage("eng-material-yield", "Material yield", "Yield strength is the stress at which permanent deformation begins. Engineering stress is force divided by the original cross-sectional area.", domain="engineering"),
    passage("eng-heat-exchanger", "Heat exchanger", "A heat exchanger transfers thermal energy between fluids separated by a wall. Temperature difference and surface area influence heat-transfer rate.", domain="engineering"),
    passage("bio-cell-membrane", "Cell membrane", "A cell membrane is selectively permeable and regulates movement of water, ions, and molecules between the cell and its environment.", domain="biology"),
    passage("bio-enzyme-rate", "Enzyme rate", "Enzymes lower activation energy and can speed biochemical reactions. Reaction rate can level off when enzyme active sites are saturated.", domain="biology"),
    passage("bio-dna-replication", "DNA replication", "DNA replication copies genetic information using complementary base pairing. Each original strand can serve as a template for a new strand.", domain="biology"),
    passage("bio-photosynthesis", "Photosynthesis", "Photosynthesis uses light energy to convert carbon dioxide and water into chemical energy stored in sugars, releasing oxygen.", domain="biology"),
    passage("bio-epidemiology", "Epidemiology", "Incidence counts new cases in a population over time, while prevalence counts all existing cases at a specified time.", domain="biology"),
    passage("chem-ideal-gas", "Ideal gas", "The ideal gas law is P V = n R T. At constant amount of gas, pressure and volume vary inversely when temperature is fixed.", domain="chemistry"),
    passage("chem-acid-base", "Acid and base", "A solution with lower pH has a greater hydrogen ion concentration. Buffers resist large pH changes when small amounts of acid or base are added.", domain="chemistry"),
    passage("chem-reaction-rate", "Reaction rate", "Reaction rate depends on concentration, temperature, surface area, and catalysts. A catalyst changes rate without being consumed overall.", domain="chemistry"),
    passage("chem-spectroscopy", "Spectroscopy", "Spectroscopy measures how matter absorbs, emits, or scatters light. A spectrum can identify chemical composition through characteristic features.", domain="chemistry"),
    passage("earth-water-cycle", "Water cycle", "Evaporation changes liquid water into vapor, condensation forms liquid droplets, and precipitation returns water from clouds to the surface.", domain="earth_science"),
    passage("earth-carbon-cycle", "Carbon cycle", "Carbon moves among atmosphere, oceans, organisms, and rocks. Photosynthesis removes carbon dioxide from air while respiration releases it.", domain="earth_science"),
    passage("earth-mars-atmosphere-ko", "화성의 대기", "화성의 대기는 매우 얇고 대부분 이산화탄소로 이루어져 있다. 표면 기압은 지구보다 훨씬 낮다.", domain="earth_science", language="ko"),
    passage("earth-seismic-wave", "Seismic waves", "P waves are compressional seismic waves and usually travel faster than S waves. S waves do not travel through liquid outer core.", domain="earth_science"),
    passage("comp-binary-search", "Binary search", "Binary search repeatedly halves a sorted search interval. Its time complexity grows logarithmically with the number of elements.", domain="computer_science"),
    passage("comp-graph-shortest", "Shortest path", "Dijkstra algorithm finds shortest paths with nonnegative edge weights by repeatedly selecting the unsettled node with smallest tentative distance.", domain="computer_science"),
    passage("comp-numerical-stability", "Numerical stability", "Numerical algorithms can magnify rounding error. Stable formulations avoid subtracting nearly equal floating-point numbers when possible.", domain="computer_science"),
    passage("energy-solar-cell", "Solar cell", "A photovoltaic cell converts light into electrical energy. Its output depends on illumination, temperature, and electrical load.", domain="energy"),
    passage("energy-battery", "Battery capacity", "Battery capacity is commonly expressed in ampere-hours. Internal resistance causes voltage drop under load and generates heat.", domain="energy"),
    passage("metrology-si-units", "SI units", "The newton is the SI unit of force, the pascal is the SI unit of pressure, and the kelvin is an SI unit for thermodynamic temperature.", domain="metrology"),
    passage("astronomy-transit", "Exoplanet transit", "A transit occurs when a planet passes in front of its star. The measured brightness dips slightly and can reveal planet size and orbit.", domain="astronomy"),
    passage("stat-hypothesis-test", "Hypothesis test", "A statistical hypothesis test compares observed data with a null model. A p value is not the probability that the null hypothesis is true.", domain="statistics"),
]


def ranking_case(case_id: str, query: str, relevant: dict[str, int], negatives: list[str], *, language: str = "en") -> dict[str, Any]:
    candidate_ids = list(dict.fromkeys([*relevant, *negatives]))
    if len(candidate_ids) < 8:
        raise ValueError(f"{case_id} needs at least eight candidate passages")
    return {
        "case_id": case_id,
        "query": query,
        "language": language,
        "candidate_ids": candidate_ids,
        "relevance": {identifier: relevant.get(identifier, 0) for identifier in candidate_ids},
    }


RETRIEVAL_CASES = [
    ranking_case("force-law", "Which law connects net force, mass, and acceleration?", {"physics-newton-force": 3, "metrology-si-units": 1}, ["eng-beam-load", "physics-friction", "math-derivative", "eng-material-yield", "physics-pressure-fluid", "energy-battery"]),
    ranking_case("projectile-range", "What changes the range of an ideal launched projectile?", {"physics-projectile-motion": 3}, ["physics-friction", "eng-beam-load", "physics-newton-force", "math-integral", "eng-feedback-control", "earth-seismic-wave", "energy-solar-cell"]),
    ranking_case("ohm-law", "How are voltage, current, and resistance related in a simple circuit?", {"physics-electric-circuit": 3}, ["energy-battery", "eng-signal-filter", "physics-wave-frequency", "chem-ideal-gas", "eng-sensor-calibration", "physics-newton-force", "comp-binary-search"]),
    ranking_case("wave-frequency", "What relation connects wave speed, frequency, and wavelength?", {"physics-wave-frequency": 3}, ["earth-seismic-wave", "math-fourier", "eng-signal-filter", "physics-electric-circuit", "physics-kinetic-energy", "astronomy-transit", "comp-graph-shortest"]),
    ranking_case("heat-transfer", "Which mechanisms move thermal energy through contact, fluid motion, and radiation?", {"physics-heat-transfer": 3, "eng-heat-exchanger": 1}, ["eng-pump-flow", "physics-pressure-fluid", "energy-battery", "chem-reaction-rate", "physics-wave-frequency", "earth-water-cycle"]),
    ranking_case("fluid-pressure", "Why does pressure rise deeper in a stationary liquid?", {"physics-pressure-fluid": 3, "chem-ideal-gas": 1}, ["eng-pump-flow", "eng-beam-load", "physics-newton-force", "earth-water-cycle", "energy-solar-cell", "metrology-si-units"]),
    ranking_case("derivative-rate", "Which mathematical concept gives instantaneous rate of change?", {"math-derivative": 3}, ["math-integral", "math-optimization", "physics-projectile-motion", "stat-hypothesis-test", "math-error-propagation", "comp-numerical-stability", "math-matrix-transform"]),
    ranking_case("integral-displacement", "What calculation accumulates displacement from a velocity-time curve?", {"math-integral": 3}, ["math-derivative", "physics-projectile-motion", "math-fourier", "math-probability", "eng-pump-flow", "energy-battery", "comp-graph-shortest"]),
    ranking_case("matrix-eigen", "What vector retains direction under a linear transformation?", {"math-eigenvalue": 3, "math-matrix-transform": 2}, ["math-derivative", "comp-graph-shortest", "eng-feedback-control", "stat-hypothesis-test", "physics-wave-frequency", "math-optimization"]),
    ranking_case("probability-independent", "How is the probability of two independent events calculated?", {"math-probability": 3}, ["stat-hypothesis-test", "bio-epidemiology", "math-error-propagation", "comp-binary-search", "chem-reaction-rate", "math-optimization", "astronomy-transit"]),
    ranking_case("constrained-optimization", "What method chooses values that optimize an objective subject to constraints?", {"math-optimization": 3}, ["math-derivative", "eng-feedback-control", "math-eigenvalue", "comp-graph-shortest", "eng-beam-load", "stat-hypothesis-test", "math-probability"]),
    ranking_case("measurement-uncertainty", "How should independent measurement uncertainty be propagated and reported?", {"math-error-propagation": 3, "eng-sensor-calibration": 2}, ["metrology-si-units", "comp-numerical-stability", "math-probability", "physics-kinetic-energy", "stat-hypothesis-test", "energy-battery"]),
    ranking_case("fatigue-cracks", "What repeated loading process can grow cracks below yield strength?", {"eng-fatigue-cycle": 3}, ["eng-material-yield", "eng-beam-load", "physics-friction", "physics-kinetic-energy", "earth-seismic-wave", "chem-reaction-rate", "energy-battery"]),
    ranking_case("sensor-calibration", "Which record maps a sensor signal to a reference with slope, offset, units, and uncertainty?", {"eng-sensor-calibration": 3}, ["eng-feedback-control", "math-error-propagation", "metrology-si-units", "eng-signal-filter", "physics-electric-circuit", "bio-epidemiology", "stat-hypothesis-test"]),
    ranking_case("low-pass-filter", "What processing suppresses rapid fluctuations above a cutoff frequency?", {"eng-signal-filter": 3, "math-fourier": 1}, ["physics-wave-frequency", "eng-feedback-control", "physics-electric-circuit", "comp-numerical-stability", "eng-sensor-calibration", "earth-seismic-wave"]),
    ranking_case("pump-curve", "What determines fluid flow rate through a pump and pipe system?", {"eng-pump-flow": 3}, ["physics-pressure-fluid", "eng-heat-exchanger", "chem-ideal-gas", "eng-beam-load", "earth-water-cycle", "energy-solar-cell", "physics-friction"]),
    ranking_case("yield-strength", "At what stress does permanent material deformation begin?", {"eng-material-yield": 3}, ["eng-fatigue-cycle", "physics-newton-force", "eng-beam-load", "physics-pressure-fluid", "metrology-si-units", "energy-battery", "math-error-propagation"]),
    ranking_case("cell-membrane", "What cell structure selectively regulates movement of ions and molecules?", {"bio-cell-membrane": 3}, ["bio-dna-replication", "chem-acid-base", "bio-photosynthesis", "bio-enzyme-rate", "earth-water-cycle", "physics-electric-circuit", "chem-spectroscopy"]),
    ranking_case("reaction-rate", "Which factors change chemical reaction rate without changing net consumption of a catalyst?", {"chem-reaction-rate": 3, "bio-enzyme-rate": 2}, ["chem-acid-base", "chem-spectroscopy", "physics-heat-transfer", "energy-solar-cell", "math-optimization", "bio-photosynthesis"]),
    ranking_case("mars-atmosphere-ko", "화성 대기의 주성분과 표면 기압의 특징은 무엇입니까?", {"earth-mars-atmosphere-ko": 3}, ["chem-ideal-gas", "earth-water-cycle", "astronomy-transit", "physics-pressure-fluid", "earth-carbon-cycle", "metrology-si-units", "energy-solar-cell"], language="ko"),
]


PAGES = [
    {
        "case_id": "ocr-normal-paragraph",
        "title": "Thermal Calibration Note",
        "kind": "normal",
        "regions": [
            ("heading-1", "heading", "Thermal Calibration Note", 90, 120, 48),
            ("paragraph-1", "paragraph", "A sensor was held at 25 C for 60 s before recording.", 90, 230, 30),
            ("paragraph-2", "paragraph", "The reference voltage was 2.0 V and current was 0.5 A.", 90, 300, 30),
            ("equation-1", "equation", "Power equation: P = V I", 90, 390, 34),
        ],
        "numeric_units": ["25 C", "60 s", "2.0 V", "0.5 A"],
        "table_cells": [],
    },
    {
        "case_id": "ocr-two-column", "title": "Bridge Fatigue Survey", "kind": "two_column",
        "regions": [
            ("heading-1", "heading", "Bridge Fatigue Survey", 90, 120, 48),
            ("left-1", "paragraph", "Left column: Cycles reached 120000 before inspection.", 90, 240, 24),
            ("left-2", "paragraph", "Left column: Crack length was 1.2 mm.", 90, 310, 24),
            ("right-1", "paragraph", "Right column: Stress amplitude was 180 MPa.", 780, 240, 24),
            ("right-2", "paragraph", "Right column: Interval was 30 days.", 780, 310, 24),
        ],
        "numeric_units": ["120000", "1.2 mm", "180 MPa", "30 days"], "table_cells": [],
    },
    {
        "case_id": "ocr-force-table", "title": "Force Table", "kind": "table",
        "regions": [
            ("heading-1", "heading", "Force Table", 90, 120, 48),
            ("equation-1", "equation", "Equation: F = m a", 90, 210, 34),
            ("table-header-mass", "table", "Mass", 130, 360, 30),
            ("table-header-force", "table", "Force", 500, 360, 30),
            ("table-header-acceleration", "table", "Acceleration", 850, 360, 30),
            ("table-row-1-mass", "table", "2 kg", 130, 450, 30),
            ("table-row-1-force", "table", "10 N", 500, 450, 30),
            ("table-row-1-acceleration", "table", "5 m/s2", 850, 450, 30),
            ("table-row-2-mass", "table", "5 kg", 130, 540, 30),
            ("table-row-2-force", "table", "25 N", 500, 540, 30),
            ("table-row-2-acceleration", "table", "5 m/s2", 850, 540, 30),
        ],
        "numeric_units": ["2 kg", "10 N", "5 m/s2", "5 kg", "25 N"],
        "table_cells": ["Mass", "Force", "Acceleration", "2 kg", "10 N", "5 kg", "25 N"],
    },
    {
        "case_id": "ocr-multilingual", "title": "다국어 센서 기록", "kind": "normal",
        "regions": [
            ("heading-1", "heading", "다국어 센서 기록", 90, 120, 48),
            ("paragraph-1", "paragraph", "온도 Temperature: 23 C", 90, 230, 34),
            ("paragraph-2", "paragraph", "압력 Pressure: 101.3 kPa", 90, 300, 34),
            ("paragraph-3", "paragraph", "유량 Flow rate: 4.5 L/min", 90, 370, 34),
        ],
        "numeric_units": ["23 C", "101.3 kPa", "4.5 L/min"], "table_cells": [],
    },
]


def _draw_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def render_page(page: dict[str, Any]) -> Path:
    if shutil.which("magick") is None or not FONT.is_file():
        raise RuntimeError("Generating benchmark pages requires ImageMagick and the bundled macOS font path")
    ASSETS.mkdir(parents=True, exist_ok=True)
    destination = ASSETS / f"{page['case_id']}.png"
    command = ["magick", "-size", "1400x900", "xc:white", "-font", str(FONT), "-fill", "black"]
    if page["kind"] == "two_column":
        command.extend(["-stroke", "#777777", "-strokewidth", "2", "-draw", "line 700,190 700,760"])
    if page["kind"] == "table":
        command.extend(["-stroke", "#222222", "-fill", "none", "-strokewidth", "2"])
        for y in (320, 405, 495, 585):
            command.extend(["-draw", f"line 100,{y} 1200,{y}"])
        for x in (100, 470, 820, 1200):
            command.extend(["-draw", f"line {x},320 {x},585"])
        command.extend(["-fill", "black"])
    for _, _, text, x, y, size in page["regions"]:
        command.extend(["-pointsize", str(size), "-draw", f"text {x},{y} '{_draw_text(text)}'"])
    command.append(str(destination))
    subprocess.run(command, check=True, capture_output=True)
    return destination


def ocr_case(page: dict[str, Any]) -> dict[str, Any]:
    regions = [
        {"id": identifier, "kind": kind, "text": text}
        for identifier, kind, text, _, _, _ in page["regions"]
    ]
    expected_layout: dict[str, Any] = {
        "elements": regions,
        "table_rows": 3 if page["kind"] == "table" else 0,
        "table_columns": 3 if page["kind"] == "table" else 0,
        "tables": {
            "force-table": {"rows": 3, "columns": 3, "cells": page["table_cells"]}
        } if page["kind"] == "table" else {},
    }
    return {
        "case_id": page["case_id"],
        "source_id": f"mystic-synthetic-{page['case_id']}",
        "source_type": "project_authored_synthetic_page",
        "title": page["title"],
        "page": 1,
        "language": "ko" if page["case_id"] == "ocr-multilingual" else "en",
        "asset_path": f"assets/{page['case_id']}.png",
        "expected_text": "\n".join(region["text"] for region in regions),
        "expected_numeric_units": page["numeric_units"],
        "expected_table_cells": page["table_cells"],
        "expected_layout": expected_layout,
        "expected_reading_order": [region["text"] for region in regions],
        "provenance": {"source_url": SOURCE_URL, "license": "CC0-1.0", "generation": "generate_assets.py"},
    }


def relative_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generated_files() -> list[Path]:
    return [
        ROOT / "corpus.json", ROOT / "retrieval_queries.json", ROOT / "relevance_judgments.json",
        ROOT / "ocr_ground_truth.json", ROOT / "layout_annotations.json", ROOT / "visual_judgments.json",
        ROOT / "provenance.json", ROOT / "LICENSES.md", ROOT / "records/lexical_baseline.phase2d-v1.0.1.json",
        *(ASSETS / f"{page['case_id']}.png" for page in PAGES),
    ]


def build() -> None:
    for page in PAGES:
        render_page(page)
    ocr_cases = [ocr_case(page) for page in PAGES]
    parsing_cases = [
        {"case_id": f"parse-{case['case_id']}", "source_id": case["source_id"], "page": 1, "asset_path": case["asset_path"], "expected_layout": case["expected_layout"], "expected_reading_order": [element["id"] for element in case["expected_layout"]["elements"]]}
        for case in ocr_cases
    ]
    visual_cases = [
        {"case_id": "visual-force-table", "query": "Which page contains a bordered table of mass, force, and acceleration?", "asset_paths": ["assets/ocr-force-table.png", "assets/ocr-normal-paragraph.png"], "relevance": {"ocr-force-table": 3, "ocr-normal-paragraph": 0}},
        {"case_id": "visual-two-column", "query": "Which page separates bridge observations into left and right columns?", "asset_paths": ["assets/ocr-two-column.png", "assets/ocr-force-table.png"], "relevance": {"ocr-two-column": 3, "ocr-force-table": 0}},
        {"case_id": "visual-multilingual", "query": "Which page has Korean sensor labels paired with pressure and flow units?", "asset_paths": ["assets/ocr-multilingual.png", "assets/ocr-normal-paragraph.png"], "relevance": {"ocr-multilingual": 3, "ocr-normal-paragraph": 0}},
    ]
    provenance_cases = [
        {"case_id": "text-retrieval-lineage", "required_stages": ["source", "normalize", "chunk", "embedding", "retrieval", "rerank"], "source_id": "physics-newton-force", "location": "passage:physics-newton-force"},
        {"case_id": "ocr-page-lineage", "required_stages": ["source", "page", "ocr", "region", "normalized_chunk", "embedding", "retrieval", "rerank"], "source_id": "mystic-synthetic-ocr-force-table", "location": "page:1/region:table-row-1"},
    ]
    corpus = {
        "schema_version": "mystic-specialist-corpus-v1",
        "corpus_id": "mystic-specialists-synthetic-v1",
        "version": "1.0.0",
        "dataset_manifest": "dataset_manifest.json",
        "historical_baseline_record": "records/lexical_baseline.phase2d-v1.0.1.json",
        "license": "CC0-1.0; see LICENSES.md. All passages and page images are project-authored synthetic evaluation material.",
        "governance": {"purpose": "Offline reproducible specialist evaluation; output remains observation data.", "change_policy": "Any corpus, label, or asset edit requires a version increment and regenerated dataset manifest.", "known_limitations": ["Synthetic controlled pages are activation gates, not a substitute for later field-document validation.", "Only Wave 1 live models are eligible for execution in Phase 2D.2."]},
        "documents": PASSAGES,
        "retrieval_cases": RETRIEVAL_CASES,
        "ocr_cases": ocr_cases,
        "parsing_cases": parsing_cases,
        "visual_cases": visual_cases,
        "provenance_cases": provenance_cases,
    }
    write_json(ROOT / "corpus.json", corpus)
    write_json(ROOT / "retrieval_queries.json", [{key: value for key, value in item.items() if key != "relevance"} for item in RETRIEVAL_CASES])
    write_json(ROOT / "relevance_judgments.json", {item["case_id"]: item["relevance"] for item in RETRIEVAL_CASES})
    write_json(ROOT / "ocr_ground_truth.json", {item["case_id"]: {key: item[key] for key in ("expected_text", "expected_numeric_units", "expected_table_cells", "expected_reading_order")} for item in ocr_cases})
    write_json(ROOT / "layout_annotations.json", {"parsing_cases": parsing_cases, "visual_cases": visual_cases})
    write_json(ROOT / "visual_judgments.json", {item["case_id"]: item["relevance"] for item in visual_cases})
    write_json(ROOT / "provenance.json", {"documents": [{"source_id": item["source_id"], "source_url": item["source_url"], "license": item["license"]} for item in PASSAGES], "pages": [{"source_id": item["source_id"], "asset_path": item["asset_path"], "license": "CC0-1.0", "generation": "generate_assets.py"} for item in ocr_cases], "lineage_cases": provenance_cases})
    write_json(ROOT / "records/lexical_baseline.phase2d-v1.0.1.json", {
        "record_kind": "lexical_baseline",
        "is_model_result": False,
        "execution_mode": "baseline",
        "corpus_id": "mystic-phase2d-science-v1",
        "corpus_version": "1.0.1",
        "corpus_hash": "fd1dd5c74536dfed12593c0be97e24701802add39bc33060deeead167cd15d6d",
        "metrics": {"mrr": 0.8125, "ndcg_at_10": 0.8576691395183482, "recall_at_5": 1.0},
        "notes": ["Preserved Phase 2D.2 lexical baseline record.", "This is a non-specialist lexical baseline, not a GPT or named-model result.", "It remains tied to its original corpus and must not be compared directly with the v1 synthetic corpus."],
    })
    (ROOT / "LICENSES.md").write_text("# Phase 2D.2 synthetic benchmark licence\n\nAll passages, labels, annotations, and generated page images in this directory are project-authored and dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). They contain no third-party paper text, credentials, or provider output.\n", encoding="utf-8")
    files = [{"path": path.relative_to(ROOT).as_posix(), "sha256": relative_hash(path), "artifact_type": "image/png" if path.suffix == ".png" else "application/json" if path.suffix == ".json" else "text/markdown", "schema_version": "v1", "retention": "repository_versioned", "classification": "public_cc0", "generation_stage": "synthetic_corpus_build"} for path in generated_files()]
    rows = [f"{item['sha256']}  {item['path']}" for item in files]
    write_json(ROOT / "dataset_manifest.json", {"schema_version": "mystic-specialist-dataset-manifest-v1", "dataset_id": "mystic-specialists-synthetic-v1", "version": "1.0.0", "dataset_sha256": hashlib.sha256("\n".join(sorted(rows)).encode("utf-8")).hexdigest(), "files": files})


def check() -> None:
    manifest = json.loads((ROOT / "dataset_manifest.json").read_text(encoding="utf-8"))
    rows: list[str] = []
    for item in manifest["files"]:
        path = ROOT / item["path"]
        actual = relative_hash(path)
        if actual != item["sha256"]:
            raise SystemExit(f"dataset hash mismatch: {item['path']}")
        rows.append(f"{actual}  {item['path']}")
    aggregate = hashlib.sha256("\n".join(sorted(rows)).encode("utf-8")).hexdigest()
    if aggregate != manifest["dataset_sha256"]:
        raise SystemExit("dataset aggregate hash mismatch")
    print(f"dataset valid: {manifest['dataset_id']} {manifest['version']} {aggregate}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate the generated dataset manifest without writing files")
    arguments = parser.parse_args()
    if arguments.check:
        check()
    else:
        build()


if __name__ == "__main__":
    main()
