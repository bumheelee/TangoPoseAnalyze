# 동영상 관절 스켈레톤

동영상 속 사람의 관절을 점으로 찍고 선으로 연결해 보여주는 웹 페이지입니다.
서버 없이 **GitHub Pages**만으로 동작하며, 인식은 전부 사용자의 브라우저 안에서 실행됩니다.

- 실시간 뼈대 오버레이 (여러 명 동시 인식, 관절 33점)
- 재생 / 프레임 단위 이동 / **재생 속도 0.1x~3x** / **A-B 구간 반복**
- 뼈대가 그려진 화면을 **영상(webm)** 또는 **PNG**로 저장
- 모델·실행 파일이 모두 저장소 안에 들어 있어 외부 CDN이 필요 없음

## GitHub Pages로 올리는 방법

1. 이 폴더의 **모든 파일**(숨김 파일 `.nojekyll` 포함)을 GitHub 저장소에 올립니다.
   - `git push`로 올리면 그대로 됩니다. (파일당 100MB 미만이라 Git LFS는 필요 없습니다.)
   - GitHub 웹 화면에서 끌어다 놓는 방식은 **파일당 25MB 제한**이 있어 대형 모델은 업로드에 제약이 있습니다.
    이 저장소는 GitHub 업로드 제한을 고려해 `pose_landmarker_heavy.task`를 기본으로 포함하지 않습니다.
    필요하면 직접 내려받아 `models/`에 넣으세요.
2. 저장소 **Settings → Pages → Build and deployment**에서 Source를 `Deploy from a branch`,
   Branch를 `main` / `/ (root)`로 지정하고 저장합니다.
3. 1~2분 뒤 `https://<계정>.github.io/<저장소>/` 로 접속합니다.

> 이 저장소는 업로드 한도를 고려해 `pose_landmarker_heavy.task`를 기본적으로 포함하지 않습니다.
> 필요하면 공식 배포처에서 모델을 내려받아 `models/`에 추가하세요.

## 내 PC에서 먼저 확인하기

`index.html`을 더블클릭하면 동작하지 않습니다(브라우저가 file:// 에서 모듈/모델 로딩을 막음). 로컬 서버로 여세요.

```bash
cd 이_폴더
python -m http.server 8000
# 브라우저에서 http://localhost:8000
```

## 사용법

1. **동영상 열기** 또는 화면에 파일을 끌어다 놓습니다. (mp4/H.264, webm 권장)
2. 오른쪽 패널에서 모델, 최대 인원, 표시 옵션을 조정합니다.
3. 재생하면 뼈대가 실시간으로 겹쳐 그려집니다.
4. 구간 반복: 원하는 위치에서 **A 지정**, 끝 위치에서 **B 지정** → **구간 반복** 체크.
5. **뼈대 영상 녹화 · 저장**: 현재 재생 속도로 실시간 녹화합니다. A·B가 지정되어 있으면 그 구간만 저장합니다.

| 단축키 | 동작 |
|---|---|
| Space | 재생 / 일시정지 |
| ← / → | 1프레임 뒤로 / 앞으로 |
| A / B | 구간 시작 / 끝 지정 |
| L | 구간 반복 켜기 / 끄기 |

## 알아둘 점

- **속도**: PC 성능에 따라 다릅니다. 화면 상단의 "추론 ○○ms"가 영상 프레임 간격(30fps면 약 33ms)보다 크면 뼈대가 끊겨 보이니, Lite 모델을 쓰거나 재생 속도를 낮추세요. GPU 초기화에 실패하면 자동으로 CPU로 전환됩니다.
- **사람 구분**: 여러 명이 겹치거나 서로 가까이 붙으면 색(사람 번호)이 프레임마다 바뀔 수 있습니다. 사람 ID를 유지하는 추적은 하지 않습니다.
- **녹화 파일**: 브라우저가 만든 webm(또는 Safari의 mp4)이며 소리는 들어가지 않습니다. webm은 총 길이 정보가 없어 일부 플레이어에서 탐색 막대가 안 움직일 수 있습니다. 녹화 중에는 탭을 전환하지 마세요.
- **개인정보**: 영상은 업로드되지 않습니다. MediaPipe 라이브러리는 기본적으로 사용 통계를 Google 서버로 보내려고 시도하는데, `index.html`의 CSP 설정(`connect-src 'self' blob: data:`)으로 이 전송을 막아 두었습니다. (브라우저 콘솔에 "Refused to connect … odml.pa.googleapis.com" 메시지가 뜨는 것은 정상입니다.)

## 포함된 파일과 출처

| 경로 | 내용 | 라이선스 |
|---|---|---|
| `vendor/vision_bundle.mjs`, `vendor/wasm/*` | [@mediapipe/tasks-vision](https://www.npmjs.com/package/@mediapipe/tasks-vision) 1.0.1 (수정 없음) | Apache-2.0 |
| `models/pose_landmarker_{lite,full}.task` | Google MediaPipe Pose Landmarker 모델 | Apache-2.0 |

모델 파일은 공식 배포 주소(`storage.googleapis.com/mediapipe-models/pose_landmarker/…`)가 아니라,
같은 모델을 담고 있는 npm 패키지에서 꺼내 왔습니다. 공식 파일과 같은지 확인하려면 SHA-256을 비교하세요.

```
59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a  pose_landmarker_lite.task
4eaa5eb7a98365221087693fcc286334cf0858e2eb6e15b506aa4a7ecdcec4ad  pose_landmarker_full.task
 
```

공식 주소에서 직접 받아 교체해도 됩니다.
예: `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task`

## 성능 개선 및 UI 변경

- 성능: 변환 모드에서 대형 프레임은 내부적으로 감지 입력을 낮은 해상도로 축소하고,
  사람 감지는 매 프레임이 아닌 일정 간격(`DETECT_INTERVAL`)으로 실행하여 연산을 줄입니다.
  또한 각 사람 크롭은 최대 한 변(`POSE_MAX_SIDE`)으로 축소해 포즈 추론 속도를 높입니다.
- 정확도가 더 필요하면 변환 탭의 "사람별 개별 포즈 추출 (정확도↑, 느림↑)" 옵션을 켜세요.
  이 옵션은 사람 탐지 후 각 사람별로 개별 포즈 추론을 수행합니다(느리지만 정확도 향상).
- 추가 설정: 감지 간격(`detectInterval`), 크롭 최대 사이즈(`poseMax`)와 포즈 재사용 시간(`poseReuse`)을
  오른쪽 패널에서 조정할 수 있습니다. 각 값은 브라우저 `localStorage`에 저장되어 다음 방문 시에도 유지됩니다.
  - 감지 간격을 늘리면 CPU 사용량이 줄고 정확도는 느슨해집니다.
  - 크롭 최대 사이즈는 포즈 모델 입력 크기 한도를 결정합니다(작게하면 빨라짐).
  - 포즈 재사용(ms): 최근 계산된 포즈를 일정 시간 재사용해 같은 사람에 대해 연속 추론을 건너뜁니다.
- UI 로고: 프로젝트 루트에 `maximo_tango_b.png` 파일을 두면 변환 탭 상단에 로고가 표시됩니다.
- Offscreen preprocessing: 브라우저가 지원하면 내부적으로 OffscreenCanvas 워커를 이용해
  다운스케일 전처리를 수행합니다(메인 스레드 부담 감소). 워커를 지원하지 않는 환경에서는
  기존 캔버스 기반 전처리로 자동으로 폴백됩니다.

추가로 성능을 더 개선하려면 GPU(가능한 경우), 더 가벼운 모델, 또는 프레임 간 트래킹(박스 재사용) 수준을
더 높이는 방법을 고려해보세요.

## 웹(브라우저) 성능 최적화

- 브라우저 쪽 성능: 대형 비디오를 직접 매 프레임 전체 해상도로 추론하면 느립니다. 이 저장소의
  `index.html`은 몇 가지 클라이언트 최적화를 적용했습니다:
  - 추론 주기 제한: 프레임마다 모두 추론하지 않고 `DETECT_INTERVAL_MS` 간격(기본 150ms)으로 추론을 실행합니다.
  - 감지 입력 축소: 내부적으로 감지용 입력은 최대 한 변(`DETECT_MAX_SIDE`)으로 축소해서 모델 입력 크기를 줄입니다.
  - 크롭 축소: (내부적으로 사람별 크롭을 사용할 때) 각 크롭은 `POSE_MAX_SIDE`로 축소해 포즈 추론 비용을 낮춥니다.
  이러한 변화로 실시간 재생 중인지 여부에 따라 CPU/GPU 사용량과 전반적인 반응성이 크게 좋아집니다.

## UI 로고

- 프로젝트 루트에 `maximo_tango_b.png`를 두면 `index.html` 상단 헤더에 로고가 자동 표시됩니다.
  파일이 없으면 자동으로 숨깁니다(404로 인한 빈 이미지 표시 방지).

## ObjectDetector (선택)

- 브라우저에서 `사람별 개별 포즈 추출` 옵션을 사용하려면 ObjectDetector 모델 파일이 필요합니다:
  `models/object_detector.task`.
- 이 리포에 모델 파일을 직접 추가하지 않은 경우, 제공된 스크립트로 원하는 URL에서 내려받을 수 있습니다:

```bash
python scripts/download_model.py --url https://example.com/path/to/object_detector.task
```

- 모델을 다운로드하면 `index.html`의 `사람별 개별 포즈 추출` 옵션이 로컬 모델을 사용해 바운딩박스 기반 분리 후
  각 크롭에 대해 포즈 추론을 실행합니다. 모델을 추가하지 않으면 자동으로 기존 `PoseLandmarker.detectForVideo()` 경로를 사용합니다.
