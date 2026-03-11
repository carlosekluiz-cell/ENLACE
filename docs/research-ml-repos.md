# ML/DL Open-Source Repos for Telecom/ISP Intelligence Integration

**Research Date:** 2026-03-11
**Platform:** Enlace (Python FastAPI + Rust RF Engine + Next.js + PostgreSQL/PostGIS)
**Existing Stack:** XGBoost scoring, Rust gRPC RF propagation (ITU-R models), Sentinel-2 imagery, 12M+ records

---

## Table of Contents

1. [Network/Coverage Prediction ML](#1-networkcoverage-prediction-ml)
2. [Satellite Imagery / Computer Vision](#2-satellite-imagery--computer-vision)
3. [Geospatial ML](#3-geospatial-ml)
4. [Network Anomaly Detection](#4-network-anomaly-detection)
5. [Priority Integration Recommendations](#5-priority-integration-recommendations)

---

## 1. Network/Coverage Prediction ML

### 1.1 RadioUNet - CNN Radio Map Estimation

- **URL:** https://github.com/RonLevie/RadioUNet
- **Stars:** ~105
- **Last Updated:** 2023
- **License:** Not specified (academic)
- **Language/Framework:** Python, PyTorch
- **What it does:** Convolutional neural network that estimates RF propagation pathloss from a transmitter to all points on a 2D plane in urban environments with buildings. Generates radio maps 2-3 orders of magnitude faster than ray-tracing simulations.
- **Enlace Integration:** Could augment the existing Rust RF engine by providing ML-accelerated coverage maps for urban areas. Feed building footprint data + terrain into the CNN for instant coverage prediction, then validate against ITU-R model outputs.
- **Integration Effort:** 2-3 weeks. Requires adapting to Brazilian city layouts and retraining on Enlace's existing propagation data.

### 1.2 PMNet / RadioMapEstimation - ICASSP 2023 Winner

- **URL:** https://github.com/GeoAICenter/RadioMapEstimation
- **Stars:** ~50
- **Last Updated:** 2024
- **License:** Academic/Research
- **Language/Framework:** Python, PyTorch
- **What it does:** Won 1st place in ICASSP 2023 Pathloss Radio Map Prediction Challenge. Uses ResNet encoder with parallel atrous convolutions (DeepLabv3-inspired) for pathloss map prediction from 3D city models. Achieves RMSE of 0.026 on RadioMap3Dseer dataset.
- **Enlace Integration:** Direct complement to the Rust RF engine. Train on Enlace's existing SRTM terrain data + building footprints to generate coverage predictions. Can serve as a fast pre-screening tool before running full ITU-R propagation models.
- **Integration Effort:** 2-3 weeks. Needs Brazilian terrain/building training data generation.

### 1.3 Sionna - NVIDIA Wireless Channel Simulation

- **URL:** https://github.com/NVlabs/sionna
- **Stars:** ~1,300
- **Last Updated:** 2025 (v1.2.1)
- **License:** Apache-2.0
- **Language/Framework:** Python, TensorFlow, Mitsuba 3
- **What it does:** GPU-accelerated, differentiable library for wireless communication system research. Includes Sionna RT (ray tracer for radio propagation), Sionna PHY (link-level simulator), and Sionna SYS (system-level simulation). Supports neural network integration via automatic differentiation.
- **Enlace Integration:** Could replace or augment ray-tracing components for urban propagation modeling. The differentiable nature enables ML-optimized network planning. GPU acceleration provides real-time coverage estimation for the design endpoint.
- **Integration Effort:** 3-4 weeks. Heavy dependency (TensorFlow + Mitsuba 3). Best used as a complementary service alongside the Rust engine.

### 1.4 RFML - Radio Frequency Machine Learning

- **URL:** https://github.com/brysef/rfml
- **Stars:** ~120
- **Last Updated:** 2022
- **License:** BSD 3-Clause
- **Language/Framework:** Python, PyTorch
- **What it does:** PyTorch implementations of common RFML networks for signal classification, dataset wrappers for open-source signal datasets (RadioML), and adversarial evasion/training methods. Includes CNN and CLDNN models for modulation recognition.
- **Enlace Integration:** Could be used to classify RF signal types detected by spectrum monitoring equipment. Useful for the spectrum license compliance module and interference detection in the health/quality endpoints.
- **Integration Effort:** 1-2 weeks for signal classification. Requires I/Q sample data feeds.

### 1.5 PathLossML_Prediction - Classical ML Path Loss

- **URL:** https://github.com/wick19/PathLossML_Prediction
- **Stars:** ~30
- **Last Updated:** 2023
- **License:** Not specified
- **Language/Framework:** Python, scikit-learn
- **What it does:** Integrates Okumura-Hata urban propagation models with machine learning methods (Random Forest, ANN, KNN) for path loss prediction. Trained on wireless communication measurement data.
- **Enlace Integration:** Lightweight alternative to neural approaches. Can be used to calibrate the existing Hata model in the Rust engine using real measurement data, improving prediction accuracy for Brazilian urban environments.
- **Integration Effort:** 1 week. Simple scikit-learn models, easy to wrap in FastAPI.

---

## 2. Satellite Imagery / Computer Vision

### 2.1 TorchGeo - PyTorch Geospatial Deep Learning (HIGH PRIORITY)

- **URL:** https://github.com/torchgeo/torchgeo
- **Stars:** ~3,300
- **Last Updated:** January 2026 (v0.9.0)
- **License:** MIT
- **Language/Framework:** Python, PyTorch
- **What it does:** PyTorch domain library providing datasets, samplers, transforms, and pre-trained models for geospatial data. First library to provide pretrained models for multispectral Sentinel-2 imagery (all bands). Supports classification, regression, segmentation, object detection, change detection, and more.
- **Enlace Integration:** Core framework for all satellite ML tasks. Directly compatible with Enlace's existing Sentinel-2 pipeline. Pre-trained Sentinel-2 models enable transfer learning for Brazilian urban/rural classification, infrastructure detection, and land use analysis with minimal training data.
- **Integration Effort:** 1-2 weeks for base integration. Ongoing for model development.

### 2.2 segment-geospatial (SamGeo) - SAM for Geospatial Data (HIGH PRIORITY)

- **URL:** https://github.com/opengeos/segment-geospatial
- **Stars:** ~3,400
- **Last Updated:** December 2025
- **License:** MIT
- **Language/Framework:** Python, PyTorch (Meta SAM)
- **What it does:** Wraps Meta's Segment Anything Model (SAM) for geospatial data analysis. Supports automatic mask generation, box/text/point prompts, batch segmentation on satellite imagery. Zero-shot segmentation capability works without task-specific training.
- **Enlace Integration:** Apply to Sentinel-2 imagery to detect buildings, roads, towers, cleared land, and other infrastructure without training. Use text prompts like "cell tower" or "building" to identify features. Directly feeds into expansion opportunity scoring.
- **Integration Effort:** 1 week for basic integration. Requires GPU for inference.

### 2.3 Microsoft South America Building Footprints (HIGH PRIORITY)

- **URL:** https://github.com/microsoft/SouthAmericaBuildingFootprints
- **Stars:** ~200
- **Last Updated:** 2023
- **License:** ODbL (Open Data Commons)
- **Language/Framework:** GeoJSON data (Python tooling)
- **What it does:** 44.5 million building footprint polygons for South America extracted via deep neural network semantic segmentation from Bing Maps satellite imagery. Includes Brazil coverage with ~1.5% false positive rate. No training labels needed - uses unsupervised style-transfer.
- **Enlace Integration:** Direct import into PostGIS as a new buildings table. Correlate with broadband subscriber data, tower locations, and municipality boundaries to improve demand estimation and coverage gap analysis. Critical for rural expansion scoring.
- **Integration Effort:** 3-5 days for data import and PostGIS indexing. Already in GeoJSON format.

### 2.4 Microsoft Global ML Building Footprints

- **URL:** https://github.com/microsoft/GlobalMLBuildingFootprints
- **Stars:** ~1,600
- **Last Updated:** 2024
- **License:** ODbL
- **Language/Framework:** GeoJSON data, Python utilities
- **What it does:** 1.4 billion building footprints worldwide from satellite imagery (2014-2024). Includes height estimates for some regions. Uses DNN semantic segmentation + polygonization. Recently added building height data for Brazil.
- **Enlace Integration:** Superset of South America footprints with more recent imagery and height data. Building height data enables better RF propagation modeling (urban clutter loss). Pair with the Rust engine for more accurate coverage simulations.
- **Integration Effort:** 3-5 days for selective Brazil import. Large dataset requires filtering.

### 2.5 Raster Vision - Geospatial Deep Learning Framework

- **URL:** https://github.com/azavea/raster-vision
- **Stars:** ~2,000
- **Last Updated:** 2025
- **License:** Apache-2.0
- **Language/Framework:** Python, PyTorch
- **What it does:** End-to-end framework for deep learning on satellite/aerial imagery. Supports chip classification, object detection, and semantic segmentation. Includes data tiling, model training, prediction, evaluation, and deployment pipeline. CLI and Python API.
- **Enlace Integration:** Production-ready pipeline for satellite analysis tasks. Use for land-use classification from Sentinel-2, building detection, and infrastructure mapping. The CLI enables automated batch processing integrated with the existing pipeline scheduler.
- **Integration Effort:** 2-3 weeks for pipeline integration. Well-documented with tutorials.

### 2.6 MMSegmentation - Semantic Segmentation Toolbox

- **URL:** https://github.com/open-mmlab/mmsegmentation
- **Stars:** ~9,300
- **Last Updated:** December 2025 (v1.2.2)
- **License:** Apache-2.0
- **Language/Framework:** Python, PyTorch (OpenMMLab)
- **What it does:** Comprehensive semantic segmentation toolbox with 50+ architectures (DeepLabV3+, PSPNet, SegFormer, etc.). Supports remote sensing datasets (LoveDA, Potsdam, iSAID). Includes training, inference, and evaluation for land cover, building, and infrastructure segmentation.
- **Enlace Integration:** Use pre-built architectures for satellite image segmentation. Train on Brazilian land cover data for urban/rural classification. SegFormer models provide efficient inference for real-time analysis of Sentinel-2 tiles.
- **Integration Effort:** 2-3 weeks. Extensive model zoo reduces training effort.

### 2.7 Open-CD - Change Detection Toolbox

- **URL:** https://github.com/likyoo/open-cd
- **Stars:** ~811
- **Last Updated:** February 2024 (v1.1.0)
- **License:** Apache-2.0
- **Language/Framework:** Python, PyTorch (OpenMMLab ecosystem)
- **What it does:** Comprehensive change detection toolbox supporting multiple architectures (BIT, BAN, TTP, LightCDNet). Detects changes between bi-temporal satellite images for urban expansion, building changes, and land use transitions. Built on MMSegmentation.
- **Enlace Integration:** Feed pairs of Sentinel-2 images (different dates) to detect urban expansion, new construction, and infrastructure changes. Directly supports the expansion opportunity scoring by identifying growing municipalities.
- **Integration Effort:** 2-3 weeks. Requires bi-temporal Sentinel-2 image pairs.

### 2.8 BIT_CD - Transformer Change Detection

- **URL:** https://github.com/justchenhao/BIT_CD
- **Stars:** ~500
- **Last Updated:** 2023
- **License:** Non-commercial/Research only
- **Language/Framework:** Python, PyTorch
- **What it does:** Bitemporal Image Transformer for remote sensing change detection. Outperforms CNN baselines with 3x lower computational cost. Uses transformer attention to model spatial-temporal context in image pairs.
- **Enlace Integration:** Detect urban growth patterns from historical Sentinel-2 imagery. Feed results into expansion scoring to identify municipalities with accelerating development. Note: research-only license limits commercial use.
- **Integration Effort:** 1-2 weeks. License restricts commercial deployment.

### 2.9 SAM-Road - Road Network Extraction

- **URL:** https://github.com/htcr/sam_road
- **Stars:** ~200
- **Last Updated:** 2024 (CVPRW 2024)
- **License:** Not specified (academic)
- **Language/Framework:** Python, PyTorch (SAM-based)
- **What it does:** Adapts SAM for vectorized road network graph extraction from aerial imagery. 40x faster than state-of-the-art (RNGDet++) while matching accuracy. Produces road graphs with vertices and edges spanning multiple square kilometers in seconds.
- **Enlace Integration:** Validate and update Enlace's 6.4M road segment database from OSM. Detect new roads in rural areas not yet mapped. Compare ML-extracted roads with OSM data to identify coverage gaps for fiber route planning.
- **Integration Effort:** 2-3 weeks. Requires high-resolution imagery (aerial preferred over Sentinel-2 10m).

### 2.10 SIMRDWN / YOLT - Satellite Object Detection

- **URL:** https://github.com/CosmiQ/simrdwn (SIMRDWN) / https://github.com/CosmiQ/yolt (YOLT)
- **Stars:** ~500 (SIMRDWN) / ~900 (YOLT)
- **Last Updated:** 2021
- **License:** Apache-2.0
- **Language/Framework:** Python, TensorFlow, Darknet (YOLO)
- **What it does:** Unified framework for object detection in satellite imagery combining YOLO v2/v3, Faster R-CNN, SSD, and R-FCN. Handles arbitrary image sizes. Detects vehicles, buildings, airports, and infrastructure at ~50 FPS.
- **Enlace Integration:** Detect cell towers, substations, and telecom infrastructure from satellite imagery. Validate tower database against aerial observations. Could identify competitor infrastructure not in Anatel records.
- **Integration Effort:** 2-3 weeks. Older codebase may need updating for current PyTorch/TF versions.

### 2.11 Solaris - CosmiQ Geospatial ML Toolkit

- **URL:** https://github.com/CosmiQ/solaris
- **Stars:** ~400
- **Last Updated:** 2022
- **License:** Apache-2.0
- **Language/Framework:** Python, PyTorch/TensorFlow
- **What it does:** End-to-end geospatial ML toolkit for tiling large imagery, converting between geospatial and ML formats, semantic/instance segmentation, object detection, and evaluation. Includes building footprint, road network, and multi-class mask creation.
- **Enlace Integration:** Preprocessing pipeline for satellite imagery ML tasks. Handles the tiling and format conversion needed to feed Sentinel-2 tiles into any deep learning model. Useful as a utility layer under TorchGeo or Raster Vision.
- **Integration Effort:** 1 week as a utility library. Integrates with existing pipelines.

### 2.12 D-LinkNet - Road Extraction (DeepGlobe Winner)

- **URL:** https://github.com/zlckanata/DeepGlobe-Road-Extraction-Challenge
- **Stars:** ~400
- **Last Updated:** 2020
- **License:** Not specified
- **Language/Framework:** Python, PyTorch
- **What it does:** 1st place solution in DeepGlobe Road Extraction Challenge. Uses LinkNet with pretrained encoder and dilated convolutions for high-resolution satellite road extraction. Produces binary road segmentation masks.
- **Enlace Integration:** Extract road networks from high-resolution imagery to validate/update OSM road data. Could detect unpaved roads in rural Brazil not in OSM, improving fiber route planning accuracy.
- **Integration Effort:** 1-2 weeks. Older code but well-documented architecture.

---

## 3. Geospatial ML

### 3.1 H3 (Uber Hexagonal Indexing) + ML (HIGH PRIORITY)

- **URL:** https://github.com/uber/h3 (core) / https://github.com/uber/h3-py (Python)
- **Stars:** ~5,000 (core) / ~900 (Python)
- **Last Updated:** 2025
- **License:** Apache-2.0
- **Language/Framework:** C (core), Python bindings, also Rust bindings available
- **What it does:** Hexagonal hierarchical geospatial indexing system. Partitions the world into hexagonal cells at multiple resolutions. Uber reduced ETA prediction errors by 22% using H3-based ML models.
- **Enlace Integration:** Index all municipality data, broadband subscribers, tower locations, and opportunity scores into H3 hexagons. Enables spatial aggregation at multiple resolutions for ML feature engineering. Feed H3-indexed features into XGBoost for improved opportunity scoring. Rust bindings available for RF engine integration.
- **Integration Effort:** 1-2 weeks for indexing + feature engineering. High ROI.

### 3.2 POPCORN - Population Maps from Sentinel (HIGH PRIORITY)

- **URL:** https://github.com/prs-eth/Popcorn
- **Stars:** ~100
- **Last Updated:** January 2026 (Bourbon follow-up released)
- **License:** Academic/Research
- **Language/Framework:** Python, PyTorch
- **What it does:** Generates high-resolution (100m) population maps from Sentinel-1 and Sentinel-2 imagery using only coarse census counts for calibration. Achieves R2=66% in urban areas with average error of 10 inhabitants/ha. Only needs ~400 regional census counts for training.
- **Enlace Integration:** Generate fine-grained population density maps for all 5,570 Brazilian municipalities using existing Sentinel-2 pipeline + IBGE census data. Output directly improves demand estimation for broadband expansion planning. Could identify underserved populations not visible in census aggregates.
- **Integration Effort:** 2-3 weeks. Already uses Sentinel-2 + census data, which Enlace has.

### 3.3 GeoMLA - ML for Spatial/Spatiotemporal Data

- **URL:** https://github.com/thengl/GeoMLA
- **Stars:** ~200
- **Last Updated:** 2022
- **License:** GPL-3.0
- **Language/Framework:** R, Python
- **What it does:** Machine learning algorithms for spatial and spatiotemporal data. Implements Random Forest Spatial Prediction (RFsp) with benchmark comparisons against kriging. Handles spatial autocorrelation in training data.
- **Enlace Integration:** Improve spatial interpolation of broadband quality metrics between measurement points. Predict QoS scores for municipalities with sparse data using spatial ML models that account for geographic correlation patterns.
- **Integration Effort:** 1-2 weeks. R dependency may require wrapper service.

### 3.4 RFSI - Random Forest Spatial Interpolation

- **URL:** https://github.com/AleksandarSekulic/RFSI
- **Stars:** ~50
- **Last Updated:** 2023
- **License:** Not specified
- **Language/Framework:** R
- **What it does:** Novel spatial interpolation using Random Forest with observations at n nearest locations and distances as spatial covariates. Outperforms ordinary kriging for irregularly sampled geospatial data.
- **Enlace Integration:** Interpolate signal quality measurements across regions where direct data is sparse. Use spatial RF to predict broadband performance metrics (speed, latency) between known measurement points.
- **Integration Effort:** 1-2 weeks. Needs R-to-Python bridge or reimplementation.

### 3.5 NeuralProphet - Time Series Forecasting

- **URL:** https://github.com/ourownstory/neural_prophet
- **Stars:** ~3,800
- **Last Updated:** 2025
- **License:** MIT
- **Language/Framework:** Python, PyTorch
- **What it does:** Interpretable time series forecasting framework combining neural networks with traditional time-series algorithms. Extension of Facebook Prophet with AR-Net. Handles seasonality, holidays, and external regressors.
- **Enlace Integration:** Forecast broadband subscriber growth per municipality, predict seasonal demand patterns, and project infrastructure capacity needs. Feed 37 months of Anatel broadband history as training data for per-municipality growth forecasting.
- **Integration Effort:** 1 week. Drop-in replacement for simple trend analysis. Excellent documentation.

### 3.6 deepVector Geospatial ML Resources (Meta-Resource)

- **URL:** https://github.com/deepVector/geospatial-machine-learning
- **Stars:** ~700
- **Last Updated:** 2024
- **License:** N/A (curated list)
- **Language/Framework:** N/A
- **What it does:** Curated list of resources focused on Machine Learning in Geospatial Data Science. Covers spatial statistics, deep learning for remote sensing, GeoAI frameworks, and geospatial feature engineering.
- **Enlace Integration:** Reference guide for identifying additional tools and techniques. Not a direct integration but a valuable resource for the development team.
- **Integration Effort:** N/A (reference material).

---

## 4. Network Anomaly Detection

### 4.1 PyOD - Outlier & Anomaly Detection Library (HIGH PRIORITY)

- **URL:** https://github.com/yzhao062/pyod
- **Stars:** ~8,500
- **Last Updated:** 2025 (PyOD v2)
- **License:** BSD 2-Clause
- **Language/Framework:** Python, PyTorch (v2), scikit-learn API
- **What it does:** Comprehensive library with 50+ outlier detection algorithms spanning classical (LOF, Isolation Forest) and deep learning (AutoEncoder, VAE, ECOD) methods. PyOD v2 adds 12 modern neural models in a unified PyTorch framework. 26M+ downloads.
- **Enlace Integration:** Detect anomalous broadband metrics (subscriber drops, unusual growth spikes, quality degradation). Apply to the 4.1M broadband subscriber records to flag data quality issues. Use for competitor behavior anomaly detection in the concorrencia module.
- **Integration Effort:** 3-5 days. scikit-learn-compatible API. Minimal code needed.

### 4.2 DeepOD - Deep Learning Anomaly Detection

- **URL:** https://github.com/xuhongzuo/DeepOD
- **Stars:** ~500
- **Last Updated:** 2025
- **License:** BSD 3-Clause
- **Language/Framework:** Python, PyTorch
- **What it does:** 27 deep outlier detection algorithms for tabular and time-series data. Includes reconstruction-based, representation-learning, and self-supervised approaches. scikit-learn/PyOD-compatible API.
- **Enlace Integration:** Specialized deep learning anomaly detection for time-series network metrics. Apply to broadband subscriber time series (37 months) to detect market disruptions, regulatory impacts, or data pipeline errors.
- **Integration Effort:** 3-5 days. Same API as PyOD.

### 4.3 Anomaly Transformer - Time Series Anomaly Detection

- **URL:** https://github.com/thuml/Anomaly-Transformer
- **Stars:** ~1,500
- **Last Updated:** 2023
- **License:** Not specified (ICLR 2022 Spotlight paper)
- **Language/Framework:** Python, PyTorch
- **What it does:** Transformer-based anomaly detection using "Association Discrepancy" to distinguish anomalies from normal patterns. Minimax strategy amplifies normal-abnormal distinguishability. State-of-the-art on multiple benchmarks.
- **Enlace Integration:** Monitor broadband subscriber trends for anomalous patterns indicating market events (ISP exits, regulatory changes, infrastructure failures). Apply to per-municipality time series for early warning of market shifts relevant to M&A and expansion modules.
- **Integration Effort:** 1-2 weeks. Requires adapting to telecom time series format.

### 4.4 GNN-Communication-Networks - Graph Neural Networks for Telecom

- **URL:** https://github.com/jwwthu/GNN-Communication-Networks
- **Stars:** ~300
- **Last Updated:** 2024
- **License:** Not specified (meta-resource)
- **Language/Framework:** N/A (collection of papers + code)
- **What it does:** Curated collection of graph-based deep learning methods for communication networks. Covers QoS prediction, network optimization, traffic forecasting, fault detection, and resource allocation using GNNs.
- **Enlace Integration:** Reference for implementing graph neural networks on the telecom infrastructure graph (towers, fiber routes, municipalities). GNN approaches can model network topology for better coverage prediction and failure propagation analysis.
- **Integration Effort:** N/A (reference). Individual implementations: 2-4 weeks each.

### 4.5 CATCH - Channel-Aware Time Series Anomaly Detection (ICLR 2025)

- **URL:** https://github.com/decisionintelligence/CATCH
- **Stars:** ~50
- **Last Updated:** 2025
- **License:** Not specified
- **Language/Framework:** Python, PyTorch
- **What it does:** State-of-the-art multivariate time series anomaly detection via frequency patching. ICLR 2025 paper. Handles channel-aware detection for complex multivariate systems.
- **Enlace Integration:** Multi-metric anomaly detection across broadband dimensions (subscribers, speed, latency, availability) per municipality. Detects correlated anomalies across metrics that single-channel methods miss.
- **Integration Effort:** 1-2 weeks. Recent paper, cutting-edge approach.

---

## 5. Priority Integration Recommendations

### Tier 1: Integrate Within 2 Weeks (Highest Impact, Lowest Effort)

| # | Repository | Category | Why |
|---|-----------|----------|-----|
| 1 | **Microsoft South America Building Footprints** | Satellite/Data | 44.5M building polygons for Brazil. Direct PostGIS import. Improves demand estimation immediately. |
| 2 | **H3 (uber/h3)** | Geospatial ML | Hexagonal indexing for all spatial data. Enables ML feature engineering. Rust bindings exist. |
| 3 | **PyOD** | Anomaly Detection | 50+ algorithms, scikit-learn API, 3-5 days integration. Immediate value for data quality. |
| 4 | **NeuralProphet** | Geospatial ML | Subscriber growth forecasting from 37 months of data. Drop-in, 1 week. |
| 5 | **TorchGeo** | Satellite/CV | Foundation for all satellite ML. Pre-trained Sentinel-2 models. MIT license. |

### Tier 2: Integrate Within 1 Month (High Impact, Moderate Effort)

| # | Repository | Category | Why |
|---|-----------|----------|-----|
| 6 | **segment-geospatial (SamGeo)** | Satellite/CV | Zero-shot infrastructure detection from Sentinel-2. No training needed. |
| 7 | **POPCORN** | Geospatial ML | Population density at 100m from Sentinel + census. Uses data Enlace already has. |
| 8 | **Open-CD** | Satellite/CV | Urban expansion change detection. Directly feeds expansion scoring. |
| 9 | **RadioUNet / PMNet** | Coverage Prediction | ML-accelerated coverage maps to complement Rust RF engine. |
| 10 | **Anomaly Transformer** | Anomaly Detection | Market event detection from subscriber time series. |

### Tier 3: Integrate Within 2-3 Months (Strategic, Higher Effort)

| # | Repository | Category | Why |
|---|-----------|----------|-----|
| 11 | **Sionna (NVIDIA)** | Coverage Prediction | GPU-accelerated, differentiable propagation. Heavy but powerful. |
| 12 | **Raster Vision** | Satellite/CV | Production pipeline for satellite ML. CLI automation. |
| 13 | **MMSegmentation** | Satellite/CV | 50+ segmentation architectures. Best model zoo available. |
| 14 | **SAM-Road** | Satellite/CV | Road network extraction to validate/extend OSM data. |
| 15 | **DeepOD** | Anomaly Detection | Deep learning time-series anomaly detection. Complements PyOD. |

### Recommended Integration Architecture

```
                    +------------------+
                    |  Sentinel-2 GEE  |
                    +--------+---------+
                             |
                    +--------v---------+
                    |    TorchGeo       |  <-- Foundation layer
                    | (datasets/models) |
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
  +-------v------+  +-------v------+  +--------v-------+
  |  SamGeo      |  |  Open-CD     |  |  POPCORN       |
  | (detection)  |  | (change det) |  | (population)   |
  +--------------+  +--------------+  +----------------+
          |                  |                  |
          +------------------+------------------+
                             |
                    +--------v---------+
                    |   H3 Indexing     |  <-- Spatial aggregation
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
  +-------v------+  +-------v------+  +--------v-------+
  |  XGBoost     |  | NeuralProphet|  |  PyOD          |
  | (scoring)    |  | (forecasting)|  | (anomalies)    |
  +--------------+  +--------------+  +----------------+
          |                  |                  |
          +------------------+------------------+
                             |
                    +--------v---------+
                    | FastAPI Endpoints |
                    +------------------+
```

### Data Flow for Building Footprint Integration

```
Microsoft Building Footprints (GeoJSON)
  --> ogr2ogr / Python loader
    --> PostGIS: buildings table (44.5M polygons)
      --> Spatial join with municipalities (admin_level_2)
        --> Building density per H3 hex (resolution 7-9)
          --> Feature for XGBoost opportunity scoring
          --> Demand estimation improvement
          --> RF propagation urban clutter input
```

### Estimated Total Integration Cost

- **Tier 1 (5 repos):** 3-4 weeks developer time
- **Tier 2 (5 repos):** 4-6 weeks developer time
- **Tier 3 (5 repos):** 6-10 weeks developer time
- **Full stack:** ~4-5 months with 1 ML engineer

### License Compatibility Summary

| License | Repos | Commercial Use |
|---------|-------|----------------|
| MIT | TorchGeo, SamGeo, NeuralProphet | Yes |
| Apache-2.0 | Sionna, Raster Vision, MMSeg, Open-CD, H3, SIMRDWN | Yes |
| BSD 2/3-Clause | PyOD, DeepOD, RFML | Yes |
| ODbL | Microsoft Building Footprints | Yes (attribution) |
| Academic/Research | RadioUNet, PMNet, BIT_CD, POPCORN | Restricted - check terms |
| Not specified | Several smaller repos | Contact authors |

---

## Appendix: Curated Resource Lists (Meta-Repositories)

These repositories are not tools themselves but curated lists of papers, datasets, and implementations that serve as ongoing references:

| Repository | URL | Stars | Focus |
|-----------|-----|-------|-------|
| awesome-remote-sensing-change-detection | https://github.com/wenhwu/awesome-remote-sensing-change-detection | ~1,900 | Change detection methods, datasets, competitions |
| satellite-image-deep-learning/techniques | https://github.com/satellite-image-deep-learning/techniques | ~7,000 | Comprehensive DL techniques for satellite imagery |
| satellite-image-deep-learning/datasets | https://github.com/satellite-image-deep-learning/datasets | ~2,000 | Datasets for satellite ML |
| GNN-Communication-Networks | https://github.com/jwwthu/GNN-Communication-Networks | ~300 | Graph neural networks for telecom |
| anomaly-detection-resources | https://github.com/yzhao062/anomaly-detection-resources | ~1,200 | Anomaly detection papers, tools, videos |
| deepVector/geospatial-machine-learning | https://github.com/deepVector/geospatial-machine-learning | ~700 | ML in geospatial data science |
| time-series-transformers-review | https://github.com/qingsongedu/time-series-transformers-review | ~1,500 | Transformers for time series |
