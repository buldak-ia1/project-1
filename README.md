English

---

# 🧠 MetaSort

### AI Image Metadata-Based Auto Classification System

---

## 📌 Overview

MetaSort is a system that automatically **analyzes and organizes AI-generated images** (e.g., NovelAI) using embedded metadata.

Instead of relying on file names,
👉 it structures images based on **generation data such as prompts, styles, and models**.

---

## 🚀 Features

### 🔍 Metadata Extraction

* Extracts metadata embedded in images
* Parses prompt, style, model information
* Supports AI-generated image formats (e.g., NovelAI)

---

### 🧠 Automatic Classification

* Classifies images based on metadata
* Example criteria:

  * Character-based grouping
  * Style-based grouping (Anime / Realistic)
  * NSFW / SFW classification

---

### 📁 Automatic Folder Organization

* Generates folder structure automatically
* Moves images into categorized directories

```bash
/Character_A/
    /Anime/
    /Realistic/

/NSFW/
/SFW/
```

---

### 🌐 Web Interface

* Local web server-based UI
* Upload images and view classification results

---

## 🛠️ Tech Stack

* **Language**: Python
* **Framework**: Flask (or FastAPI)
* **Image Processing**: Pillow (PIL)
* **Environment**: Windows / Local Server

---

## 🏗️ Architecture

```bash
[ Input Images ]
        ↓
[ Metadata Extraction ]
        ↓
[ Classification Logic ]
        ↓
[ Folder Structure Generator ]
        ↓
[ File Organizer ]
        ↓
[ Web UI ]
```

---

## ⚙️ Getting Started

### 1. Clone Repository

```bash
git clone https://github.com/your-repo/metasort.git
cd metasort
```

---

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Run Server

```bash
python MetaSortWeb.py
```

---

### 4. Access

```
http://localhost:5000
```

---

## 📂 Project Structure

```bash
MetaSort/
│── MetaSortWeb.py        # Web server entry point
│── core/
│   ├── parser.py        # Metadata extraction
│   ├── classifier.py    # Classification logic
│   ├── organizer.py     # File organization
│
│── static/
│── templates/
│── uploads/
│── output/
```

---

## 🧩 Challenges & Solutions

### ❗ Inconsistent Metadata Formats

* Different image formats store metadata differently
  👉 Implemented flexible parsing and exception handling

---

### ❗ Ambiguous Classification Rules

* Some cases are unclear or overlapping
  👉 Designed a rule-based classification system

---

### ❗ Performance with Large Datasets

* Handling large image sets caused slowdowns
  👉 Optimized processing and minimized unnecessary operations

---

## 📈 Future Improvements

* Image similarity clustering (ML-based)
* AI-based classification enhancements
* Database integration (currently file-based)
* React-based UI upgrade
* Cloud deployment

---

## 👨‍💻 Author

* System architecture design
* Metadata parsing implementation
* Classification logic development
* Web server setup

---

## 📄 License

MIT License (optional)

---

## 🔥 Summary

> A system that automatically organizes AI-generated images using metadata-driven classification.




한국어

---

# 🧠 MetaSort

### AI 이미지 메타데이터 기반 자동 분류 시스템

---

## 📌 Overview

MetaSort는 AI 이미지(NovelAI 등)에 포함된 **메타데이터를 분석하여 자동으로 이미지를 분류 및 정리하는 시스템**입니다.

기존의 파일명 기반 정리가 아닌,
👉 **생성 정보(prompt, style 등)를 기반으로 구조화**하는 것이 핵심입니다.

---

## 🚀 Features

### 🔍 Metadata Extraction

* 이미지 내부 메타데이터 추출
* Prompt / Style / Model 정보 파싱
* AI 생성 이미지 구조 대응

---

### 🧠 Auto Classification

* 메타데이터 기반 자동 분류
* 분류 기준 예시:

  * 캐릭터 기준
  * 스타일 기준 (Anime / Realistic 등)
  * NSFW / SFW 구분

---

### 📁 Auto Folder Organization

* 분석 결과 기반 폴더 자동 생성
* 이미지 자동 이동

```
/Character_A/
    /Anime/
    /Realistic/

/NSFW/
/SFW/
```

---

### 🌐 Web Interface

* 로컬 웹 서버 기반 UI 제공
* 이미지 업로드 및 결과 확인

---

## 🛠️ Tech Stack

* **Language**: Python
* **Framework**: Flask (or FastAPI)
* **Image Processing**: PIL (Pillow)
* **Environment**: Windows / Local Server

---

## 🏗️ Architecture

```
[ Input Images ]
        ↓
[ Metadata Extraction ]
        ↓
[ Classification Logic ]
        ↓
[ Folder Structure Generator ]
        ↓
[ File Organizer ]
        ↓
[ Web UI ]
```

---

## ⚙️ Getting Started

### 1. Clone Repository

```bash
git clone https://github.com/your-repo/metasort.git
cd metasort
```

---

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Run Server

```bash
python MetaSortWeb.py
```

---

### 4. Access

```
http://localhost:5000
```

---

## 📂 Project Structure

```
MetaSort/
│── MetaSortWeb.py        # 웹 서버 실행 파일
│── core/
│   ├── parser.py        # 메타데이터 추출
│   ├── classifier.py    # 분류 로직
│   ├── organizer.py     # 파일 이동
│
│── static/
│── templates/
│── uploads/
│── output/
```

---

## 🧩 Challenges & Solutions

### ❗ Inconsistent Metadata Format

* 다양한 이미지 포맷에서 메타데이터 구조가 다름
  👉 예외 처리 및 파싱 로직 분리

---

### ❗ Classification Ambiguity

* 기준이 모호한 경우 발생
  👉 룰 기반 분류 시스템 설계

---

### ❗ Performance with Large Files

* 대량 이미지 처리 시 속도 문제
  👉 불필요 데이터 제거 및 처리 최적화

---

## 📈 Future Improvements

* 이미지 유사도 기반 클러스터링
* 머신러닝 분류 모델 적용
* DB 연동 (현재는 파일 기반)
* React 기반 UI 개선
* 클라우드 배포

---

## 👨‍💻 Author

* 시스템 설계
* 메타데이터 분석 로직 구현
* 분류 알고리즘 설계
* 웹 서버 구성

---

## 📄 License

MIT License (optional)

---

## 🔥 Summary

> 메타데이터 기반으로 AI 이미지를 자동 분류하고 구조화하는 시스템

---

원하면 다음 단계로
👉 **GitHub 레포에 먹히는 “스타 받을 수 있는 README 디자인” (배지, GIF, 스크린샷 포함)**
👉 **면접에서 이 프로젝트로 압도하는 설명 스크립트**

까지 만들어줄게.
