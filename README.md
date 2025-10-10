# Wharf-Injury-Risk-Monitoring
**A YOLOv5-based system for mechanical injury risk monitoring in wharf yard construction, integrating fuzzy logic and object detection.**

## 📘 Project Overview
This repository provides the code used in the paper:
> *"Based on Fuzzy Logic and Object Identification of Wharf Yard Construction Mechanical Injury Risk Monitoring and Warning"*

The system combines **YOLOv5-based object detection** and **fuzzy logic-based risk reasoning** to monitor and warn of potential mechanical injury risks during wharf construction.

## 🧩 Main Files
| File | Function |
|------|-----------|
| `data_gen.py` | Generate and convert VOC-format dataset to YOLO format. |
| `detect.py` | Perform object detection on images/videos using YOLOv5. |
| `export.py` | Export trained YOLOv5 model to ONNX / TorchScript / CoreML formats. |
| `hubconf.py` | Register YOLOv5 models for PyTorch Hub. |

## 🔧 Environment Setup
```bash
conda create -n wharf python=3.8
conda activate wharf
pip install -r requirements.txt
